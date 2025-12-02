from sqlmodel import Session, select
from app.models import Reading, ReadingEmbedding
from app.database import engine
from sentence_transformers import SentenceTransformer
import numpy as np
import pickle

# Khởi tạo model embedding
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# Hàm encode với overlap
def encode_with_overlap(text: str, segment_len: int = 200, overlap_ratio: float = 0.3):
    text = " ".join(text.split())  # normalize whitespace
    if len(text) <= segment_len:
        return embedder.encode([text], convert_to_numpy=True)[0]

    overlap = int(segment_len * overlap_ratio)
    embeddings = []
    start = 0
    while start < len(text):
        end = start + segment_len
        chunk = text[start:end]
        emb = embedder.encode([chunk], convert_to_numpy=True)[0]
        embeddings.append(emb)
        if end >= len(text):
            break
        start = end - overlap  # shift start cho đoạn tiếp theo

    final_emb = np.mean(embeddings, axis=0)
    return final_emb

# Lấy tất cả readings
with Session(engine) as session:
    readings = session.exec(select(Reading)).all()
    session.commit()
    for reading in readings:
        # Chuẩn hóa text
        text = f"{reading.content_text}"
        text = " ".join(text.split())

        # Tạo embedding với overlap
        vector = encode_with_overlap(text, segment_len=200, overlap_ratio=0.3)

        # Chuyển embedding thành bytes để lưu vào DB
        vector_blob = pickle.dumps(vector)

        # Kiểm tra xem đã có embedding chưa
        existing = session.exec(
            select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading.id)
        ).first()

        existing.optional_vector = vector_blob

    # Commit tất cả thay đổi
    session.commit()

print("Đã tạo xong embedding cho tất cả readings và lưu vào reading_embeddings")
