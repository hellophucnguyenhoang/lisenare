import hashlib

import numpy as np
from numpy.typing import NDArray
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, or_, select

from config import logger
from database import Brick, TextEmbedding
from schemas import BrickContextSearch
from utils import text_utils

# ---------------------------------------------------------------------------
# Model identifiers – stored as model_version in text_embedding rows.
# ---------------------------------------------------------------------------
_EN_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_JA_MODEL_NAME = "cl-nagoya/ruri-v3-70m"


def _model_version_for(lang: str) -> str:
    """Return model_version identifier for the given language code."""
    if lang == "ja":
        return _JA_MODEL_NAME
    return _EN_MODEL_NAME


def _embed_document(source_text: str, lang: str) -> tuple[list[float], str]:
    """Embed a brick's canonical text for storage via inference service."""
    return text_utils.get_embedding(source_text, lang=lang, is_query=False)


def _embed_query(query: str, lang: str) -> list[float]:
    """Embed a user search query via inference service."""
    vec, _ = text_utils.get_embedding(query, lang=lang, is_query=True)
    return vec


def _canonical_text(brick: Brick) -> str:
    """Single string used as canonical embedding source for a brick."""
    return brick.target_text.strip()


def _content_hash(text_: str) -> bytes:
    """SHA-256 digest of the canonical text."""
    return hashlib.sha256(text_.encode("utf-8")).digest()


# ---------------------------------------------------------------------------
# Core embedding persistence helpers
# ---------------------------------------------------------------------------


def get_or_create_embedding(
    session: Session,
    canonical: str,
    lang: str,
) -> TextEmbedding:
    """
    Return an existing TextEmbedding matching (target_lang, model_version,
    content_hash) or create a new one. Handles concurrent INSERT races via
    the unique constraint.
    """
    model_version = _model_version_for(lang)
    chash = _content_hash(canonical)

    existing = session.exec(
        select(TextEmbedding).where(
            TextEmbedding.target_lang == lang,
            TextEmbedding.model_version == model_version,
            TextEmbedding.content_hash == chash,
        )
    ).first()
    if existing:
        return existing

    vector, retrieved_model_version = _embed_document(canonical, lang)
    version_to_use = retrieved_model_version or model_version

    row = TextEmbedding(
        target_lang=lang,
        model_version=version_to_use,
        content_hash=chash,
        source_text=canonical,
        embedding=vector,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(TextEmbedding).where(
                TextEmbedding.target_lang == lang,
                TextEmbedding.model_version == version_to_use,
                TextEmbedding.content_hash == chash,
            )
        ).first()
        if existing is None:
            raise
        return existing

    session.refresh(row)
    return row


def attach_embedding(session: Session, brick: Brick) -> None:
    """
    Ensure brick.embedding_id points to the correct TextEmbedding for its
    current text. Creates an embedding row only if none exists for that
    canonical text; other bricks sharing the previous embedding are unaffected.
    """
    canonical = _canonical_text(brick)
    emb = get_or_create_embedding(session, canonical, brick.target_lang)
    brick.embedding_id = emb.id


def get_embedding(session: Session, brick_id: int) -> NDArray | None:
    """Return the embedding vector for a brick, or None if not embedded."""
    stmt = (
        select(TextEmbedding.embedding)
        .join(Brick, Brick.embedding_id == TextEmbedding.id)
        .where(Brick.id == brick_id)
    )
    result = session.exec(stmt).first()
    if result is None:
        return None
    return np.array(result, dtype=np.float32)


# ---------------------------------------------------------------------------
# Semantic search with SQLAlchemy / pgvector
# ---------------------------------------------------------------------------


def _mmr(
    query_vec: NDArray,
    rows: list,
    k: int,
    lambda_mult: float = 0.5,
) -> list:
    """Maximal Marginal Relevance re-ranking."""
    if not rows:
        return []
    vecs = np.array([np.array(r.embedding, dtype=np.float32) for r in rows])
    relevance = vecs @ query_vec
    selected: list[int] = []
    remaining = list(range(len(rows)))

    while remaining and len(selected) < k:
        if not selected:
            best = max(remaining, key=lambda i: relevance[i])
        else:
            sel_vecs = vecs[selected]
            scores = [
                lambda_mult * relevance[i]
                - (1 - lambda_mult) * float(np.max(vecs[i] @ sel_vecs.T))
                for i in remaining
            ]
            best = remaining[int(np.argmax(scores))]
        selected.append(best)
        remaining.remove(best)

    return [rows[i] for i in selected]


def search_bricks_semantic(
    session: Session,
    query: str,
    lang: str = "en",
    limit: int = 20,
    fetch_k: int = 50,
) -> list[BrickContextSearch]:
    """
    Nearest-neighbour lookup via pgvector cosine distance, then MMR
    re-ranking for relevance + diversity.
    """
    query_vec = _embed_query(query, lang)

    nn_stmt = (
        select(
            Brick.id,
            Brick.native_text,
            Brick.target_text,
            Brick.target_audio_path,
            Brick.is_private,
            TextEmbedding.embedding,
        )
        .join(TextEmbedding, Brick.embedding_id == TextEmbedding.id)
        .where(TextEmbedding.target_lang == lang)
        .order_by(TextEmbedding.embedding.op("<->")(query_vec))
        .limit(fetch_k)
    )
    rows = session.exec(nn_stmt).all()
    if not rows:
        return []

    # Deduplicate on target_text before MMR to prevent crowding
    seen: set[str] = set()
    unique_rows = []
    for row in rows:
        if row.target_text not in seen:
            seen.add(row.target_text)
            unique_rows.append(row)

    results = _mmr(np.array(query_vec, dtype=np.float32), unique_rows, k=limit)
    return [
        BrickContextSearch(
            brick_id=r.id,
            native_text=r.native_text,
            target_text=r.target_text,
            target_audio_path=r.target_audio_path,
            is_private=r.is_private,
        )
        for r in results
    ]


def get_relevant_bricks(
    session: Session,
    profile_vector: list[float],
    limit: int = 5,
    exclude_ids: list[int] | None = None,
    fetch_k: int = 20,
    lambda_mult: float = 0.5,
    lang: str | None = None,
) -> list[int]:
    """Returns brick IDs closest to a learner profile vector with MMR."""
    pv = np.array(profile_vector, dtype=np.float32)

    stmt = (
        select(Brick.id, TextEmbedding.embedding)
        .join(TextEmbedding, Brick.embedding_id == TextEmbedding.id)
        .where(Brick.is_private.is_(False))
        .order_by(TextEmbedding.embedding.op("<->")(pv.tolist()))
        .limit(fetch_k)
    )
    if exclude_ids:
        stmt = stmt.where(Brick.id.notin_(exclude_ids))
    if lang:
        stmt = stmt.where(Brick.target_lang == lang)

    rows = session.exec(stmt).all()
    if not rows:
        return []

    vecs = np.array([np.array(r.embedding, dtype=np.float32) for r in rows])
    relevance = vecs @ pv
    selected: list[int] = []
    remaining = list(range(len(rows)))

    while remaining and len(selected) < limit:
        if not selected:
            best = max(remaining, key=lambda i: relevance[i])
        else:
            sel_vecs = vecs[selected]
            scores = [
                lambda_mult * relevance[i]
                - (1 - lambda_mult) * float(np.max(vecs[i] @ sel_vecs.T))
                for i in remaining
            ]
            best = remaining[int(np.argmax(scores))]
        selected.append(best)
        remaining.remove(best)

    return [rows[i].id for i in selected]


# ---------------------------------------------------------------------------
# Literal search (pgroonga)
# ---------------------------------------------------------------------------


def search_bricks_literal(
    session: Session, keyword: str
) -> list[BrickContextSearch]:
    statement = text("""
        SELECT 
            id as brick_id,
            native_text,
            target_text, 
            target_audio_path, 
            is_private
        FROM brick
        WHERE (target_text || ' ' || native_text) &@ :val
        ORDER BY pgroonga_score(tableoid, ctid) DESC
    """)
    results = session.exec(statement, params={"val": keyword})
    rows = results.mappings().all()
    return [BrickContextSearch.model_validate(row) for row in rows]


# ---------------------------------------------------------------------------
# Combined brick search (main search function)
# ---------------------------------------------------------------------------


def search_bricks(
    session: Session,
    query: str,
    searcher_id: int | None = None,
    kind: str | None = None,
    limit: int = 30,
    offset: int = 0,
    retrieval_lang: str | None = None,
) -> list[BrickContextSearch]:
    """Combines literal and semantic search with visibility filters and pagination."""
    lang = retrieval_lang or "en"
    literal_results = search_bricks_literal(session, query)
    semantic_results = search_bricks_semantic(
        session, query, lang=lang, limit=20, fetch_k=60
    )
    logger.info(
        f"literal brick: {len(literal_results)}, "
        f"semantic brick: {len(semantic_results)}"
    )

    filters = [Brick.is_private == False]  # noqa: E712
    if searcher_id is not None:
        filters.append(Brick.creator_id == searcher_id)

    candidate_ids = {
        res.brick_id for res in literal_results + semantic_results
    }
    if not candidate_ids:
        return []

    from sqlmodel import select as sm_select

    stmt = sm_select(Brick.id, Brick.creator_id).where(
        Brick.id.in_(candidate_ids),
        or_(*filters),
    )
    if kind:
        stmt = stmt.where(Brick.kind == kind)
    if retrieval_lang:
        stmt = stmt.where(Brick.target_lang == retrieval_lang)

    visible_rows = session.exec(stmt).all()
    visible_brick_ids = {row[0] for row in visible_rows}
    own_brick_ids = (
        {row[0] for row in visible_rows if row[1] == searcher_id}
        if searcher_id
        else set()
    )

    seen: set[str] = set()
    combined: list[BrickContextSearch] = []
    for res in literal_results + semantic_results:
        if res.target_text not in seen and res.brick_id in visible_brick_ids:
            res.is_own = res.brick_id in own_brick_ids
            combined.append(res)
            seen.add(res.target_text)

    return combined[offset : offset + limit]


# ---------------------------------------------------------------------------
# Bulk initialisation
# ---------------------------------------------------------------------------


def create_vector_indexes(session: Session) -> None:
    logger.info("Creating HNSW index on text_embedding(embedding)...")
    session.exec(
        text("""
        CREATE INDEX IF NOT EXISTS idx_text_embedding_hnsw
        ON text_embedding USING hnsw (embedding vector_cosine_ops);
        """)
    )
    logger.info("Creating PGroonga index for literal text search...")
    session.exec(
        text("""
        CREATE INDEX IF NOT EXISTS idx_brick_literal_search 
        ON brick USING pgroonga ((target_text || ' ' || native_text));
        """)
    )
    session.commit()


def initialize_embeddings(session: Session) -> None:
    """Embed all bricks that have no embedding yet. Safe to re-run."""
    create_vector_indexes(session)

    stmt = select(Brick).where(Brick.embedding_id.is_(None))
    bricks = session.exec(stmt).all()
    if not bricks:
        logger.info("No bricks without embeddings.")
        return

    logger.info(f"Embedding {len(bricks)} bricks without embeddings...")
    for i, brick in enumerate(bricks):
        try:
            attach_embedding(session, brick)
            session.add(brick)
            if (i + 1) % 50 == 0:
                session.commit()
                logger.info(f"  ...committed {i + 1}/{len(bricks)}")
        except Exception as e:
            logger.error(f"Failed to embed brick ID: {e}", exc_info=True)
    session.commit()
    logger.info("All bricks embedded.")


# ---------------------------------------------------------------------------
# Brick embedding lifecycle helpers
# ---------------------------------------------------------------------------


def add_brick_embedding(session: Session, brick: Brick) -> None:
    """Compute and attach embedding for a newly created/copied/updated brick."""
    try:
        attach_embedding(session, brick)
        session.add(brick)
        session.commit()
        logger.info(f"Attached embedding to brick ID: {brick.id}")
    except Exception as e:
        logger.error(
            f"Failed to attach embedding for brick ID {brick.id}: {e}",
            exc_info=True,
        )


def remove_brick_embedding(session: Session, brick: Brick) -> None:
    """
    Detach embedding from a brick being deleted. The TextEmbedding row is
    kept so other bricks sharing the same canonical text are unaffected.
    """
    if brick.embedding_id is not None:
        brick.embedding_id = None
        session.add(brick)
