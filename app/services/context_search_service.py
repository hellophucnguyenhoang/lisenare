from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from app.schemas import ContextSearchResult

class ContextSearchService():
    def __init__(self):
        embeddings = OllamaEmbeddings(model="mahonzhan/all-MiniLM-L6-v2")
        vector_store = Chroma(
            collection_name="subtitles",
            embedding_function=embeddings,
            persist_directory="./chroma_subtitles"
        )
        self.retriever = vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k": 6, "lambda_mult": 0.25}
        )
    
    def search_context(self, text: str) -> list[ContextSearchResult]:
        docs = self.retriever.invoke(text)
        search_results = []
        for doc in docs:
            meta_data = doc.metadata
            subtitle = doc.page_content
            context_search_result = ContextSearchResult(
                ytb_video_id=meta_data['video_id'],
                text=subtitle,
                start=float(meta_data['start']),
                duration=float(meta_data['duration'])
            )
            search_results.append(context_search_result)
        return search_results

context_search_service = ContextSearchService()
