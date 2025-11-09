from typing import List, Optional
import numpy as np
from sqlmodel import Session, select
from sentence_transformers import SentenceTransformer

from app.models import Reading, ReadingEmbedding


def _reading_to_text(reading: Reading, include_questions: bool = True) -> str:
    """Combine topic name, title, content_text, and optionally questions into one text string."""
    parts = []

    # ✅ Include topic name at the top for semantic context
    if getattr(reading, "topic", None) and getattr(reading.topic, "name", None):
        parts.append(f"Topic: {reading.topic.name}")

    if getattr(reading, "title", None):
        parts.append(f"Title: {reading.title}")

    if getattr(reading, "content_text", None):
        parts.append(reading.content_text)

    # Optionally include questions and options
    if include_questions and getattr(reading, "questions", None):
        q_texts = []
        for q in reading.questions:
            q_parts = [q.question_text]
            for opt in ["option_a", "option_b", "option_c", "option_d"]:
                val = getattr(q, opt, None)
                if val:
                    q_parts.append(str(val))
            q_texts.append(" | ".join(q_parts))
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
    Combines semantic text + metadata (difficulty, num_words, num_questions).
    """
    # 1️⃣ Load readings
    readings: List[Reading] = session.exec(select(Reading)).all()
    if not readings:
        print("⚠️ No readings found — skipping embedding creation.")
        return

    # 2️⃣ Prepare text inputs (topic name + title + content)
    texts = [_reading_to_text(r, include_questions=include_questions) for r in readings]

    # 3️⃣ Encode texts with SentenceTransformer
    model = SentenceTransformer(model_name)
    text_embeddings = model.encode(
        texts, convert_to_numpy=True, batch_size=batch_size, show_progress_bar=True
    ).astype(np.float32)

    # 4️⃣ Add extra metadata: difficulty, num_words, num_questions
    final_embeddings = []
    for reading, text_emb in zip(readings, text_embeddings):
        # Difficulty (0–5 one-hot)
        diff_onehot = np.zeros(6, dtype=np.float32)
        if 0 <= reading.difficulty <= 5:
            diff_onehot[reading.difficulty] = 1.0

        # Normalized numeric features
        num_words_norm = np.log1p(reading.num_words) / 10.0
        num_questions_norm = min(reading.num_questions / 10.0, 1.0)
        numeric_features = np.array([num_words_norm, num_questions_norm], dtype=np.float32)

        combined_emb = np.concatenate([text_emb, diff_onehot, numeric_features], axis=0)
        final_embeddings.append(combined_emb)

    # 5️⃣ Upsert embeddings
    for reading, emb in zip(readings, final_embeddings):
        existing = session.exec(
            select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading.id)
        ).first()

        if existing:
            existing.vector_blob = emb.tobytes()
        else:
            session.add(
                ReadingEmbedding(
                    reading_id=reading.id,
                    vector_blob=emb.tobytes(),
                )
            )

    session.commit()
    print(
        f"✅ Created {len(readings)} embeddings with metadata "
        f"(dim={text_embeddings.shape[1] + 6 + 2})"
    )


def get_item_embedding_by_reading_id(session: Session, reading_id: int) -> Optional[np.ndarray]:
    """Retrieve the embedding for a reading_id as a NumPy array (dtype float32)."""
    emb_row = session.exec(
        select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading_id)
    ).first()
    if not emb_row:
        return None

    arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
    return arr
