from fastapi import HTTPException, status
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from numpy.typing import NDArray
from sqlmodel import Session, select, text

from app.config import settings
from app.database import Brick, Snippet
from app.schemas import (
    BrickContextSearch,
    LearnerRead,
    SnippetRead,
    VideoContextSearchResult,
)


def search_subtitles_literal(
    session: Session, keyword: str
) -> list[VideoContextSearchResult]:
    fts_expression = f"NEAR({keyword}*, 3)"

    statement = text("""
        SELECT video_id AS ytb_video_id, start, duration, text 
        FROM subtitle_search 
        WHERE text MATCH :val 
        ORDER BY rank
    """)

    raw_rows = session.exec(statement, params={"val": fts_expression}).all()
    return [VideoContextSearchResult.model_validate(row) for row in raw_rows]


def search_bricks_literal(
    session: Session, keyword: str
) -> list[BrickContextSearch]:
    fts_expression = f"NEAR({keyword}*, 3)"

    # Join with the main 'brick' table to get the full metadata (audio, cefr, etc)
    statement = text("""
        SELECT 
            b.id as brick_id,
            b.native_text,
            b.target_text, 
            b.target_audio_path, 
            b.cefr_level, 
            b.is_public
        FROM brick b
        JOIN brick_search bs ON b.id = bs.brick_id
        WHERE brick_search MATCH :val
        ORDER BY rank
    """)

    results = session.exec(statement, params={"val": fts_expression})
    rows = results.mappings().all()
    return [BrickContextSearch.model_validate(row) for row in rows]


def search_snippets_literal(
    session: Session,
    keyword: str,
) -> list[SnippetRead]:
    fts_expression = f"NEAR({keyword}*, 3)"

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
        JOIN snippet_search ss ON s.id = ss.snippet_id 
        JOIN learner l ON s.creator_id = l.id 
        WHERE snippet_search MATCH :val
        ORDER BY rank
    """)

    raw_rows = session.exec(statement, params={"val": fts_expression}).all()
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
    def __init__(self, persist_directory: str = settings.chroma_context_path):
        self.embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")

        self.stores = {
            "snippets": Chroma(
                collection_name="snippets",
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            ),
            "subtitles": Chroma(
                collection_name="subtitles",
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            ),
            "bricks": Chroma(
                collection_name="bricks",
                embedding_function=self.embeddings,
                persist_directory=persist_directory,
            ),
        }

    def _update_docs(
        self,
        collection_name: str,
        docs: list[str],
        doc_ids: list[str],
        doc_metas: list[dict] | None = None,
    ):
        store = self.stores[collection_name]

        # Access the underlying Chroma collection directly for upsert
        if doc_metas:
            store._collection.upsert(
                ids=doc_ids, documents=docs, metadatas=doc_metas
            )
        else:
            store._collection.upsert(ids=doc_ids, documents=docs)

        print(f"Upserted {len(doc_ids)} docs to {collection_name} collection.")

    def upsert_context_snippet(self, session: Session, snippet_id: int):
        content = session.exec(
            select(Snippet.content).where(Snippet.id == snippet_id)
        ).first()

        if not content:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"data for snippet_id {snippet_id} does not exists",
            )

        self._update_docs(
            "snippets",
            [content],
            [str(snippet_id)],
            [{"snippet_id": str(snippet_id)}],
        )
        print("Done upserting the snippet into collection")

    def upsert_context_brick(self, session: Session, brick_id: int):
        brick_text = session.exec(
            select(Brick.native_text, Brick.target_text).where(
                Brick.id == brick_id
            )
        ).first()

        if not brick_text:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"data for brick_id {brick_id} does not exists",
            )

        native_text, target_text = brick_text
        self._update_docs(
            "bricks",
            [target_text],
            [str(brick_id)],
            [{"native_text": native_text}],
        )
        print("Done upserting the brick into collection")

    def upsert_context_all_snippets(self, session: Session):
        snippet_contents = session.exec(
            select(Snippet.id, Snippet.content)
        ).all()
        print(f"{len(snippet_contents)} snippets to upsert")
        batch_docs = []
        batch_ids = []
        batch_metas = []
        batch_size = 256

        for snippet_id, snippet_content in snippet_contents:
            batch_docs.append(snippet_content)
            batch_ids.append(str(snippet_id))
            batch_metas.append({"snippet_id": str(snippet_id)})

            if len(batch_ids) >= batch_size:
                self._update_docs(
                    "snippets", batch_docs, batch_ids, batch_metas
                )
                batch_docs = []
                batch_ids = []
                batch_metas = []

        if batch_docs:
            self._update_docs("snippets", batch_docs, batch_ids, batch_metas)

        print("Done upserting snippets collection")

    def upsert_context_all_bricks(self, session: Session):
        brick_texts = session.exec(
            select(Brick.id, Brick.native_text, Brick.target_text)
        ).all()
        print(f"{len(brick_texts)} bricks to upsert")
        batch_docs = []
        batch_ids = []
        batch_metas = []
        batch_size = 256

        for brick_id, native_text, target_text in brick_texts:
            batch_docs.append(target_text)
            batch_ids.append(str(brick_id))
            meta = {"brick_id": str(brick_id), "native_text": native_text}
            batch_metas.append(meta)

            if len(batch_ids) >= batch_size:
                self._update_docs("bricks", batch_docs, batch_ids, batch_metas)
                batch_docs = []
                batch_ids = []
                batch_metas = []

        if batch_docs:
            self._update_docs("bricks", batch_docs, batch_ids, batch_metas)

        print("Done upserting bricks collection")

    def _fetch_docs(self, collection_name: str, query: str, mmr: bool) -> list:
        """Generic helper to fetch docs from Chroma."""
        store = self.stores[collection_name]
        if mmr:
            return store.max_marginal_relevance_search(
                query, k=10, fetch_k=20, lambda_mult=0.5
            )
        return store.similarity_search(query, k=10)

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

        return [int(doc.id) for doc in results if doc.id is not None]

    def search_context_videos(
        self, text: str, mmr: bool = True
    ) -> list[VideoContextSearchResult]:
        docs = self._fetch_docs("subtitles", text, mmr)
        return [
            VideoContextSearchResult(
                ytb_video_id=d.metadata["video_id"],
                text=d.page_content,
                start=float(d.metadata["start"]),
                duration=float(d.metadata["duration"]),
            )
            for d in docs
        ]

    def search_videos_hybrid(
        self, session: Session, query: str
    ) -> list[VideoContextSearchResult]:
        # 1. Get Literal Results (FTS5)
        literal_results = search_subtitles_literal(session, query)

        # 2. Get Semantic Results (MMR)
        semantic_results = self.search_context_videos(query, mmr=True)

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

    def search_context_bricks(
        self, text: str, mmr: bool = True
    ) -> list[BrickContextSearch]:
        docs = self._fetch_docs("bricks", text, mmr)
        return [
            BrickContextSearch(
                brick_id=d.id,
                native_text=d.metadata["native_text"],
                target_text=d.page_content,
            )
            for d in docs
        ]

    def search_bricks_hybrid(
        self, session: Session, query: str
    ) -> list[BrickContextSearch]:
        literal_results = search_bricks_literal(session, query)
        semantic_results = self.search_context_bricks(query, mmr=True)
        seen = set()
        combined = []

        for res in literal_results + semantic_results:
            identifier = f"{res.target_text}"
            if identifier not in seen:
                combined.append(res)
                seen.add(identifier)

        return combined

    def get_embedding(self, snippet_id: int) -> NDArray | None:
        target_id = str(snippet_id)
        result = self.stores["snippets"]._collection.get(
            ids=[target_id], include=["embeddings"]
        )

        embeddings = result.get("embeddings")
        if len(embeddings) > 0:
            return embeddings[0]
        return None


context_search_service = ContextSearchService()
