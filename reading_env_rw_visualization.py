import reading_env
from app.config import settings

reader = reading_env.Reader(emb_dim=settings.item_embedding_dim)


