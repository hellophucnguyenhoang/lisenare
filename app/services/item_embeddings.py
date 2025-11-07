from typing import List, Optional
import numpy as np
from sqlmodel import Session, select
from sentence_transformers import SentenceTransformer

from app.models import Reading, ObjectiveQuestion  # adjust import paths if needed
from app.models import ReadingEmbedding  # your SQLModel table for embeddings


def _reading_to_text(reading: Reading, include_questions: bool = True) -> str:
    """Concatenate title, content_text and optionally question text into one string."""
    parts = []
    if getattr(reading, "title", None):
        parts.append(reading.title)
    if getattr(reading, "content_text", None):
        parts.append(reading.content_text)
    if include_questions and getattr(reading, "questions", None):
        q_texts = []
        for q in reading.questions:
            # combine question and options to provide richer context to the embedder
            q_parts = [q.question_text]
            if getattr(q, "option_a", None):
                q_parts.append(str(q.option_a))
            if getattr(q, "option_b", None):
                q_parts.append(str(q.option_b))
            if getattr(q, "option_c", None):
                q_parts.append(str(q.option_c))
            if getattr(q, "option_d", None):
                q_parts.append(str(q.option_d))
            q_texts.append(" | ".join([p for p in q_parts if p]))
        if q_texts:
            parts.append("\n".join(q_texts))
    return "\n\n".join([p for p in parts if p])


def create_item_embeddings(
    session: Session,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    include_questions: bool = True,
) -> None:
    """
    Compute embeddings for all Readings and upsert them into ReadingEmbedding.vector_blob.

    - session: active sqlmodel Session
    - model_name: sentence-transformers model identifier
    - batch_size: encode batch size
    - include_questions: include the reading.questions text in embedding text
    """
    # 1) Load readings (eager-load questions to avoid N+1 if your relation is lazy)
    # If you want to load questions in the same query, you can use selectinload as discussed earlier.
    readings: List[Reading] = session.exec(select(Reading)).all()
    if not readings:
        return

    # 2) Prepare texts in same order as readings
    texts = [ _reading_to_text(r, include_questions=include_questions) for r in readings ]

    # 3) Load model and compute embeddings (returns numpy array)
    model = SentenceTransformer(model_name)
    embeddings = model.encode(texts, convert_to_numpy=True, batch_size=batch_size, show_progress_bar=True)

    # Ensure dtype float32 for compact storage and consistent reconstruction
    if embeddings.dtype != np.float32:
        embeddings = embeddings.astype(np.float32)

    # 4) Upsert embeddings into the DB
    for reading, emb in zip(readings, embeddings):
        # Try to find an existing embedding row for this reading
        existing = session.exec(
            select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading.id)
        ).first()

        if existing:
            # update the blob
            existing.vector_blob = emb.tobytes()
            # SQLModel will detect attribute change; no need to session.add(existing)
        else:
            new_row = ReadingEmbedding(
                reading_id=reading.id,
                vector_blob=emb.tobytes()
            )
            session.add(new_row)

    session.commit()


def get_item_embedding_by_reading_id(session: Session, reading_id: int) -> Optional[np.ndarray]:
    """
    Retrieve the embedding for a reading_id as a NumPy array (dtype float32).
    Returns None if not found.
    """
    emb_row = session.exec(
        select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading_id)
    ).first()
    if not emb_row:
        return None

    # Convert bytes back to numpy array
    arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
    # .copy() ensures the array owns its memory (safer if DB-backed buffer lifecycle)
    return arr
