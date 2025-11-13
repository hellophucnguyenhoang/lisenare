from typing import List, Optional
import numpy as np
from sqlmodel import Session, func, select
from sentence_transformers import SentenceTransformer
import torch
from app.models import Reading, ReadingEmbedding
from sklearn.decomposition import PCA

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


def get_embedding_by_reading_id(session: Session, reading_id: int) -> Optional[np.ndarray]:
    """Retrieve the embedding for a reading_id as a NumPy array (dtype float32)."""
    emb_row = session.exec(
        select(ReadingEmbedding).where(ReadingEmbedding.reading_id == reading_id)
    ).first()
    if not emb_row:
        return None

    arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
    return arr


def get_embeddings_by_reading_ids(session: Session, reading_ids: list[int]) -> list[np.ndarray]:
    """Lấy danh sách embedding cho nhiều reading_id."""
    if not reading_ids:
        return []

    stmt = select(ReadingEmbedding).where(ReadingEmbedding.reading_id.in_(reading_ids))
    rows = session.exec(stmt).all()

    embeddings = []
    for r in rows:
        arr = np.frombuffer(r.vector_blob, dtype=np.float32).copy()
        embeddings.append(arr)
    return embeddings


def get_random_embedding(session: Session) -> Optional[np.ndarray]:
    """Retrieve the embedding for a reading_id as a NumPy array (dtype float32)."""
    emb_row = session.exec(
        select(ReadingEmbedding).order_by(func.random()).limit(1)
    ).first()
    if not emb_row:
        return None

    arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
    return arr

def get_random_embeddings(session: Session, num_items: int, embed_dim: int) -> torch.Tensor:
    """
    Load up to num_items unique item embeddings randomly from the database.

    Args:
        session: SQLAlchemy/SQLModel session
        num_items: number of embeddings to sample
        embed_dim: embedding dimension

    Returns:
        item_embeddings: torch.Tensor of shape (num_items_loaded, embed_dim)
    """
    # Lấy tất cả embeddings có trong DB
    all_emb_rows = session.exec(select(ReadingEmbedding)).all()
    total_items = len(all_emb_rows)

    if total_items == 0:
        raise ValueError("No embeddings found in the database.")

    if num_items > total_items:
        print(f"Warning: Requested NUM_ITEMS={num_items} exceeds available={total_items}. Using {total_items} instead.")
        num_items = total_items

    # Lấy sample ngẫu nhiên, không trùng
    sampled_rows = np.random.choice(all_emb_rows, size=num_items, replace=False)

    item_embeddings = torch.zeros((num_items, embed_dim), dtype=torch.float32)

    for i, row in enumerate(sampled_rows):
        emb_arr = np.frombuffer(row.vector_blob, dtype=np.float32)
        # đảm bảo đúng shape
        if emb_arr.shape[0] != embed_dim:
            print("Warning: Embedding dimension mismatch for reading_id "
                  f"{row.reading_id}: expected {embed_dim}, got {emb_arr.shape[0]}. Skipping.")
            continue
        item_embeddings[i] = torch.from_numpy(emb_arr).float()

    return item_embeddings

def get_all_item_embeddings(session: Session):
    """
    Load all item embeddings from the database.

    Args:
        session: SQLAlchemy/SQLModel session
    Returns:
        item_embeddings: torch.Tensor of shape (num_items, embed_dim)
    """
    all_emb_rows = session.exec(select(ReadingEmbedding)).all()
    total_items = len(all_emb_rows)

    if total_items == 0:
        raise ValueError("No embeddings found in the database.")

    item_embeddings = []
    item_ids = []
    for i, row in enumerate(all_emb_rows):
        emb_arr = np.frombuffer(row.vector_blob, dtype=np.float32).copy()
        item_embeddings.append(emb_arr)
        item_ids.append(row.reading_id)
    item_embeddings = np.array(item_embeddings, dtype=np.float32)
    return item_embeddings, item_ids

def get_reduced_item_embeddings(session: Session, n_components: int = 50):
    """
    Load all item embeddings from the database and reduce dimensionality using PCA.

    Args:
        session: SQLAlchemy/SQLModel session
        n_components (int): number of PCA components to keep

    Returns:
        reduced_embeddings: torch.Tensor of shape (num_items, n_components)
        item_ids: list of reading_id
        pca_model: trained PCA model (can be reused for transforming new data)
    """
    # --- Load từ database ---
    all_emb_rows = session.exec(select(ReadingEmbedding)).all()
    total_items = len(all_emb_rows)
    if total_items == 0:
        raise ValueError("No embeddings found in the database.")

    item_embeddings = []
    item_ids = []
    for row in all_emb_rows:
        emb_arr = np.frombuffer(row.vector_blob, dtype=np.float32).copy()
        item_embeddings.append(emb_arr)
        item_ids.append(row.reading_id)

    item_embeddings = np.array(item_embeddings, dtype=np.float32)
    print(f"Loaded {total_items} embeddings of shape {item_embeddings.shape}")

    # --- PCA reduction ---
    print(f"🔹 Reducing dimension from {item_embeddings.shape[1]} → {n_components} using PCA...")
    pca = PCA(n_components=n_components)
    reduced = pca.fit_transform(item_embeddings)
    print(f"   → Giữ lại {pca.explained_variance_ratio_.sum():.2%} thông tin")
    # reduced_embeddings = torch.tensor(reduced, dtype=torch.float32)

    return reduced, item_ids, pca
