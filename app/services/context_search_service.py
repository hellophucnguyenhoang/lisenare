import json

import numpy as np
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from numpy.typing import NDArray
from sqlmodel import Session, or_, select, text

from app.config import settings
from app.database import Brick, Snippet, YouTubeSubtitle
from app.schemas import (
    BrickContextSearch,
    LearnerRead,
    SnippetRead,
    VideoContextSearchResult,
)


def search_subtitles_literal(
    session: Session, keyword: str
) -> list[VideoContextSearchResult]:
    statement = text("""
        SELECT video_id AS ytb_video_id, start, duration, transcript
        FROM youtubesubtitle
        WHERE to_tsvector('simple', transcript) @@ websearch_to_tsquery('simple', :val)
        ORDER BY ts_rank(to_tsvector('simple', transcript), websearch_to_tsquery('simple', :val)) DESC
    """)

    results = session.exec(statement, params={"val": keyword})
    rows = results.mappings().all()
    return [VideoContextSearchResult.model_validate(row) for row in rows]


def search_bricks_literal(
    session: Session, keyword: str
) -> list[BrickContextSearch]:
    statement = text("""
        SELECT 
            id as brick_id,
            native_text,
            target_text, 
            target_audio_path, 
            cefr_level, 
            is_public
        FROM brick
        WHERE to_tsvector('simple', target_text || ' ' || native_text) @@ websearch_to_tsquery('simple', :val)
        ORDER BY ts_rank(to_tsvector('simple', target_text), websearch_to_tsquery('simple', :val)) DESC
    """)

    results = session.exec(statement, params={"val": keyword})
    rows = results.mappings().all()
    return [BrickContextSearch.model_validate(row) for row in rows]


def search_snippets_literal(
    session: Session,
    keyword: str,
) -> list[SnippetRead]:
    statement = text("""
        SELECT 
            s.id,
            s.content,
            s.translation, 
            s.audio_path, 
            s.created_at, 
            l.id as creator_id, 
            l.full_name 
        FROM snippet s
        JOIN learner l ON s.creator_id = l.id 
        WHERE to_tsvector('simple', s.content) @@ websearch_to_tsquery('simple', :val)
        ORDER BY ts_rank(to_tsvector('simple', s.content), websearch_to_tsquery('simple', :val)) DESC
    """)

    raw_rows = session.exec(statement, params={"val": keyword}).all()
    items = []
    for raw_row in raw_rows:
        creator = LearnerRead(
            id=raw_row.creator_id,
            full_name=raw_row.full_name,
        )
        snippet_read = SnippetRead(
            id=raw_row.id,
            content=raw_row.content,
            translation=raw_row.translation,
            audio_path=raw_row.audio_path,
            created_at=raw_row.created_at,
            creator=creator,
        )
        items.append(snippet_read)

    return items


class ContextSearchService:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")
        self.stores = {
            "subtitles": PGVector(
                embeddings=self.embeddings,
                embedding_length=settings.semantic_emb_dim,
                collection_name="youtubesubtitle",
                connection=settings.database_url,
                use_jsonb=True,
            ),
            "bricks": PGVector(
                embeddings=self.embeddings,
                embedding_length=settings.semantic_emb_dim,
                collection_name="brick",
                connection=settings.database_url,
                use_jsonb=True,
            ),
            "snippets": PGVector(
                embeddings=self.embeddings,
                embedding_length=settings.semantic_emb_dim,
                collection_name="snippet",
                connection=settings.database_url,
                use_jsonb=True,
            ),
        }

    def _fetch_docs(self, collection_name: str, query: str, mmr: bool) -> list:
        """Generic helper to fetch docs from vector store."""
        store = self.stores[collection_name]
        if mmr:
            return store.max_marginal_relevance_search(
                query, k=10, fetch_k=20, lambda_mult=0.5
            )
        return store.similarity_search(query, k=10)

    def search_videos_semantic(
        self, text: str, mmr: bool = True
    ) -> list[VideoContextSearchResult]:
        docs = self._fetch_docs("subtitles", text, mmr)
        return [
            VideoContextSearchResult(
                ytb_video_id=d.metadata["video_id"],
                transcript=d.page_content,
                start=float(d.metadata["start"]),
                duration=float(d.metadata["duration"]),
            )
            for d in docs
        ]

    def search_videos(
        self, session: Session, query: str
    ) -> list[VideoContextSearchResult]:
        # 1. Get Literal Results
        literal_results = search_subtitles_literal(session, query)

        # 2. Get Semantic Results (MMR)
        semantic_results = self.search_videos_semantic(query, mmr=True)

        # 3. Combine and Deduplicate
        # We use a set of keys to ensure we don't show the same clip twice
        seen_clips = set()
        combined = []

        # Prioritize literal matches, then fill with semantic matches
        for res in literal_results + semantic_results:
            identifier = f"{res.ytb_video_id}_{res.start}_{res.duration}"
            if identifier not in seen_clips:
                combined.append(res)
                seen_clips.add(identifier)

        return combined

    def search_bricks_semantic(
        self, text: str, mmr: bool = True
    ) -> list[BrickContextSearch]:
        docs = self._fetch_docs("bricks", text, mmr)
        print(f"brick semantic: {len(docs)}")
        return [
            BrickContextSearch(
                brick_id=d.metadata["brick_id"],
                native_text=d.metadata["native_text"],
                target_text=d.metadata["target_text"],
            )
            for d in docs
        ]

    def search_bricks(
        self, session: Session, query: str, searcher_id: int | None = None
    ) -> list[BrickContextSearch]:
        literal_results = search_bricks_literal(session, query)
        semantic_results = self.search_bricks_semantic(query, mmr=True)

        # Build the visibility filter
        # Everyone sees public bricks
        filters = [Brick.is_public]

        # Logged-in users also see their own private bricks
        if searcher_id is not None:
            filters.append(Brick.creator_id == searcher_id)

        # Using or_ (*) unpacks the list into: (is_public) OR (creator_id == searcher_id)
        visible_brick_ids = set(
            session.exec(select(Brick.id).where(or_(*filters))).all()
        )

        seen = set()
        combined = []

        for res in literal_results + semantic_results:
            if (
                res.target_text not in seen
                and res.brick_id in visible_brick_ids
            ):
                combined.append(res)
                seen.add(res.target_text)

        return combined

    def search_snippets_semantic(
        self, session: Session, text: str, mmr: bool = True
    ):
        docs = self._fetch_docs("snippets", text, mmr=False)
        print(f"Semantic search number: {len(docs) = }")
        snippet_ids = [d.metadata["snippet_id"] for d in docs]
        snippets = session.exec(
            select(Snippet).where(Snippet.id.in_(snippet_ids))
        ).all()
        snippets = sorted(snippets, key=lambda s: snippet_ids.index(s.id))
        return [SnippetRead.model_validate(s) for s in snippets]

    def search_snippets(self, session: Session, query: str):
        literal_results = search_snippets_literal(session, query)
        semantic_results = self.search_snippets_semantic(
            session, query, mmr=True
        )
        seen = set()
        combined = []

        for res in literal_results + semantic_results:
            if res.id not in seen:
                combined.append(res)
                seen.add(res.id)

        return combined

    def get_relevant_snippets(
        self,
        profile_vector: list[float],
        limit: int = 5,
        exclude_ids: list[int] = [],
        mmr: bool = True,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
    ) -> list[int]:
        """Returns a list of snippet IDs closest to the profile vector."""
        filter_ = None
        if exclude_ids:
            filter_ = {"snippet_id": {"$nin": [str(i) for i in exclude_ids]}}

        if mmr:
            results = self.stores[
                "snippets"
            ].max_marginal_relevance_search_by_vector(
                embedding=profile_vector,
                k=limit,
                fetch_k=fetch_k,
                lambda_mult=lambda_mult,
                filter=filter_,
            )
        else:
            results = self.stores["snippets"].similarity_search_by_vector(
                embedding=profile_vector,
                k=limit,
                filter=filter_,
            )

        return [
            doc.metadata["snippet_id"] for doc in results if doc.id is not None
        ]

    def get_embedding(
        self, session: Session, snippet_id: int
    ) -> NDArray | None:

        doc_id = f"Snippet_{snippet_id}"

        query = text("""
            SELECT embedding FROM langchain_pg_embedding 
            WHERE id = :doc_id
            LIMIT 1
        """)

        result = session.exec(query, params={"doc_id": doc_id}).first()

        if result is not None:
            vector_str = result[0]
            vector = json.loads(vector_str)
            return np.array(vector, dtype=np.float32)

        return None


context_search_service = ContextSearchService()


def sync_model_to_langchain(
    session: Session,
    search_service: ContextSearchService,
    model,
    store_key: str,
    text_getter,
    metadata_getter,
    id_getter,
):
    items = session.exec(select(model)).all()
    if not items:
        return

    store = search_service.stores[store_key]

    existing_ids = set()
    try:
        result = session.exec(
            text("SELECT id FROM langchain_pg_embedding")
        ).all()
        existing_ids = {row[0] for row in result if row[0]}
        print(f"DEBUG: Found {len(existing_ids)} existing IDs in DB.")
    except Exception as e:
        print(
            f"Note: Could not fetch existing IDs, will try to sync all. Error: {e}"
        )

    batch_size = 256
    total = len(items)
    print(
        f"Syncing {total} {model.__name__}s to LangChain in batches of {batch_size}..."
    )

    for i in range(0, total, batch_size):
        batch_items = items[i : i + batch_size]

        documents = []
        ids = []
        for item in batch_items:
            doc_id = f"{model.__name__}_{id_getter(item)}"
            if doc_id not in existing_ids:
                documents.append(
                    Document(
                        page_content=text_getter(item),
                        metadata=metadata_getter(item),
                    )
                )
                ids.append(doc_id)

        if documents:
            store.add_documents(documents, ids=ids)
            print(
                f"[{store_key}] Added {len(documents)} new items. \
                    Progress: {min(i + batch_size, total)}/{total}"
            )
        else:
            print(
                f"[{store_key}] Batch {i // batch_size + 1}: Skipping (all exist)."
            )


def create_vector_indexes(session: Session):
    print("Creating HNSW indexes for semantic search...")
    # Lưu ý: LangChain lưu vector trong bảng 'langchain_pg_embedding'
    # và cột chứa vector tên là 'embedding'
    session.exec(
        text("""
        CREATE INDEX IF NOT EXISTS idx_langchain_hnsw 
        ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops);
    """)
    )
    session.commit()
    print("Indexes created successfully!")


def initialize_embeddings(
    session: Session, search_service: ContextSearchService
):
    # 1. Subtitles: (video_id, start, duration)
    sync_model_to_langchain(
        session,
        search_service,
        YouTubeSubtitle,
        "subtitles",
        lambda s: s.transcript,
        lambda s: {
            "video_id": s.video_id,
            "start": s.start,
            "duration": s.duration,
        },
        lambda s: f"{s.video_id}_{s.start}_{s.duration}",
    )

    # 2. Bricks: (brick_id, native_text)
    sync_model_to_langchain(
        session,
        search_service,
        Brick,
        "bricks",
        lambda b: f"{b.target_text} {b.native_text}",
        lambda b: {
            "brick_id": b.id,
            "target_text": b.target_text,
            "native_text": b.native_text,
        },
        lambda b: b.id,
    )

    # 3. Snippets: (snippet_id)
    sync_model_to_langchain(
        session,
        search_service,
        Snippet,
        "snippets",
        lambda s: s.content,
        lambda s: {"snippet_id": s.id},
        lambda s: s.id,
    )

    print("All data synced with custom metadata!")
    create_vector_indexes(session)


def add_item_to_vector_store(
    search_service: ContextSearchService,
    item,  # This is a Brick or Snippet instance
    store_key: str,
    text_getter,
    metadata_getter,
    id_prefix: str,
):
    """Adds a single model instance to the LangChain vector store."""
    store = search_service.stores[store_key]

    # Generate the ID exactly like the sync_model_to_langchain function
    doc_id = f"{id_prefix}_{item.id}"

    document = Document(
        page_content=text_getter(item),
        metadata=metadata_getter(item),
    )

    # Add to the store
    store.add_documents([document], ids=[doc_id])
    print(f"[{store_key}] Successfully embedded item ID: {doc_id}")


def delete_item_from_vector_store(
    search_service: ContextSearchService,
    item_id: int,
    store_key: str,
    id_prefix: str,
):
    """Removes a single item from the LangChain vector store."""
    store = search_service.stores[store_key]

    # Reconstruct the ID exactly as it was stored
    doc_id = f"{id_prefix}_{item_id}"

    try:
        # LangChain stores usually provide a .delete() method for IDs
        store.delete(ids=[doc_id])
        print(f"[{store_key}] Successfully deleted embedding for ID: {doc_id}")
    except Exception as e:
        print(f"[{store_key}] Error deleting ID {doc_id}: {e}")
