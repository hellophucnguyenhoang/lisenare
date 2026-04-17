from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from sqlmodel import Session, text

from app.config import settings
from app.schemas import BrickContextSearch, VideoContextSearchResult


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
    print(f"{rows = }")
    return [BrickContextSearch.model_validate(row) for row in rows]


class ContextSearchService:
    def __init__(self, persist_directory: str = settings.chroma_db_path):
        self.embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")

        self.stores = {
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

    def _fetch_docs(self, collection_name: str, query: str, mmr: bool) -> list:
        """Generic helper to fetch docs from Chroma."""
        store = self.stores[collection_name]
        if mmr:
            return store.max_marginal_relevance_search(
                query, k=10, fetch_k=20, lambda_mult=0.5
            )
        return store.similarity_search(query, k=10)

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
                brick_id=d.metadata["brick_id"],
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


context_search_service = ContextSearchService()
