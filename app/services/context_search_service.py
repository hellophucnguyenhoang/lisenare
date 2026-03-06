from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

from app.schemas import VideoContextSearchResult, BrickContextSearch, CEFRLevel


class ContextSearchService:
    def __init__(self):
        embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")
        subtitle_vector_store = Chroma(
            collection_name="subtitles",
            embedding_function=embeddings,
            persist_directory="./chroma_ytb_subtitles_db",
        )
        brick_vector_store = Chroma(
            collection_name="bricks",
            embedding_function=embeddings,
            persist_directory="./chroma_bricks",
        )
        self.subtitle_retriever = subtitle_vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k": 10, "lambda_mult": 0.25}
        )
        self.brick_retriever = brick_vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k": 10, "lambda_mult": 0.25}
        )

    def search_context_videos(
        self, text: str
    ) -> list[VideoContextSearchResult]:
        docs = self.subtitle_retriever.invoke(text)
        search_results = []
        for doc in docs:
            meta_data = doc.metadata
            subtitle = doc.page_content
            context_search_result = VideoContextSearchResult(
                ytb_video_id=meta_data["video_id"],
                text=subtitle,
                start=float(meta_data["start"]),
                duration=float(meta_data["duration"]),
            )
            search_results.append(context_search_result)
        return search_results

    def search_context_bricks(self, text: str) -> list[BrickContextSearch]:
        docs = self.brick_retriever.invoke(text)
        search_results = []
        for doc in docs:
            meta_data = doc.metadata
            target_text = doc.page_content
            brick_read = BrickContextSearch(
                native_text=meta_data["vi_translation"],
                target_text=target_text,
                target_audio_uri=meta_data["source_audio_path"],
                cefr_level=CEFRLevel(meta_data["cefr_level"]),
                creator_id=1,  # TODO: Add true data
            )
            search_results.append(brick_read)
        return search_results


context_search_service = ContextSearchService()
