import json

import numpy as np
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from numpy.typing import NDArray
from sqlmodel import Session, or_, select, text

from config import logger, settings
from constants import SEMANTIC_EMB_DIM
from database import Brick, YouTubeSubtitle
from schemas import BrickContextSearch


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
        WHERE to_tsvector('simple', target_text || ' ' || native_text) @@ websearch_to_tsquery('simple', :val)
        ORDER BY ts_rank(to_tsvector('simple', target_text), websearch_to_tsquery('simple', :val)) DESC
    """)

    results = session.exec(statement, params={"val": keyword})
    rows = results.mappings().all()
    return [BrickContextSearch.model_validate(row) for row in rows]


class ContextSearchService:
    def __init__(self):
        self.embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")
        self.stores = {
            "subtitles": PGVector(
                embeddings=self.embeddings,
                embedding_length=SEMANTIC_EMB_DIM,
                collection_name="youtubesubtitle",
                connection=settings.database_url,
                use_jsonb=True,
            ),
            "bricks": PGVector(
                embeddings=self.embeddings,
                embedding_length=SEMANTIC_EMB_DIM,
                collection_name="brick",
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

    def search_bricks_semantic(
        self, text: str, mmr: bool = True
    ) -> list[BrickContextSearch]:
        docs = self._fetch_docs("bricks", text, mmr)
        logger.info(f"brick semantic: {len(docs)}")
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
        filters = [Brick.is_private]

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

    def get_embedding(self, session: Session, brick_id: int) -> NDArray | None:

        doc_id = f"Brick_{brick_id}"

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
        logger.debug(f"Found {len(existing_ids)} existing IDs in DB.")
    except Exception as e:
        logger.warning(
            f"Note: Could not fetch existing IDs, will try to sync all. Error: {e}"
        )

    batch_size = 256
    total = len(items)
    logger.info(
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
            logger.info(
                f"[{store_key}] Added {len(documents)} new items. "
                f"Progress: {min(i + batch_size, total)}/{total}"
            )
        else:
            logger.info(
                f"[{store_key}] Batch {i // batch_size + 1}: Skipping (all exist)."
            )


def create_vector_indexes(session: Session):
    logger.info("Creating HNSW indexes for semantic search...")
    # Lưu ý: LangChain lưu vector trong bảng 'langchain_pg_embedding'
    # và cột chứa vector tên là 'embedding'
    session.exec(
        text("""
        CREATE INDEX IF NOT EXISTS idx_langchain_hnsw 
        ON langchain_pg_embedding USING hnsw (embedding vector_cosine_ops);
    """)
    )
    session.commit()
    logger.info("Indexes created successfully!")


def initialize_embeddings(
    session: Session, search_service: ContextSearchService
):
    create_vector_indexes(session)

    # 1. Bricks: (brick_id, native_text)
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

    # 2. Subtitles: (video_id, start, duration)
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

    logger.info("All data synced with custom metadata!")


def add_item_to_vector_store(
    search_service: ContextSearchService,
    item,  # This is a Brick instance
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
    logger.info(f"[{store_key}] Successfully embedded item ID: {doc_id}")


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
        logger.info(
            f"[{store_key}] Successfully deleted embedding for ID: {doc_id}"
        )
    except Exception as e:
        logger.error(f"[{store_key}] Error deleting ID {doc_id}: {e}")
