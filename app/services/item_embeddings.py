from typing import List, Optional
import numpy as np
from sqlmodel import Session, func, select
from sentence_transformers import SentenceTransformer
from app.models import Reading, ReadingEmbedding
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from app.config import settings
from typing import List, Tuple
import random
from np_utils import *
import spacy
import joblib

nlp = spacy.load("en_core_web_sm")

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

def embed_long_text_by_sentences(model: SentenceTransformer, text: str, batch_size: int) -> np.ndarray:
    """
    Encode văn bản dài bằng cách tách câu bằng spaCy,
    sau đó mean-pool các sentence embeddings.
    """
    model_max_length = model.max_seq_length
    # print(f"Max SEQ LENG: {model.max_seq_length}")

    doc = nlp(text)

    # Lọc câu rỗng
    sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

    for s in sentences:
        s_len = len(model.tokenizer(s)["input_ids"])
        if s_len > model_max_length:
            print("WARNING: TRUNCATED")

    if not sentences:
        return model.encode([""], convert_to_numpy=True)[0]

    # Encode từng câu
    sent_embeddings = model.encode(
        sentences,
        convert_to_numpy=True,
        batch_size=batch_size,
        show_progress_bar=False
    ).astype(np.float32)

    # Mean pooling embedding cuối cùng
    final_emb = sent_embeddings.mean(axis=0)

    return final_emb

def create_item_embeddings(
    session: Session,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    include_questions: bool = False,
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
    
    text_embeddings = np.array([
        embed_long_text_by_sentences(model, txt, batch_size)
        for txt in texts
    ], dtype=np.float32)

    # 4️⃣ Add extra metadata: difficulty, num_words, num_questions
    combined_embeddings = []
    for reading, text_emb in zip(readings, text_embeddings):
        # Difficulty (0–5 one-hot)
        diff_onehot = np.zeros(6, dtype=np.float32)
        if 0 <= reading.difficulty <= 5:
            diff_onehot[reading.difficulty] = 1.0

        # Normalized numeric features
        numeric_features = np.array([reading.num_words, reading.num_questions], dtype=np.float32)

        combined_emb = np.concatenate([text_emb, diff_onehot, numeric_features], axis=0)
        combined_embeddings.append(combined_emb)
        
    combined_embeddings = np.array(combined_embeddings, np.float32)
    pca = PCA(n_components=settings.item_embedding_dim)
    print(f"🔹 Reducing dimension from {combined_embeddings.shape[1]} → {settings.item_embedding_dim} using PCA...")

    reduced_embeddings = pca.fit_transform(combined_embeddings)
    print(f"   → Giữ lại {pca.explained_variance_ratio_.sum():.2%} thông tin")

    # 5️⃣ Upsert embeddings
    for reading, emb in zip(readings, reduced_embeddings):
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
        f"(only text dim={text_embeddings.shape[1] + 6 + 2})"
    )

def refresh_item_embeddings(
    session: Session,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    include_questions: bool = False,
) -> None:
    """
    Compute embeddings for all Readings and upsert them into ReadingEmbedding.vector_blob.
    Combines semantic text + metadata (difficulty, num_words, num_questions).
    """
    # 1️⃣ Load readings
    readings: List[Reading] = session.exec(select(Reading)).all()

    # 2️⃣ Prepare text inputs (topic name + title + content)
    texts = [_reading_to_text(r, include_questions=include_questions) for r in readings]

    # 3️⃣ Encode texts with SentenceTransformer
    model = SentenceTransformer(model_name)
    
    text_embeddings = np.array([
        embed_long_text_by_sentences(model, txt, batch_size)
        for txt in texts
    ], dtype=np.float32)

    # 4️⃣ Add extra metadata: difficulty, num_words, num_questions
    combined_embeddings = []
    for reading, text_emb in zip(readings, text_embeddings):
        # Difficulty (0–5 one-hot)
        diff_onehot = np.zeros(6, dtype=np.float32)
        if 0 <= reading.difficulty <= 5:
            diff_onehot[reading.difficulty] = 1.0

        numeric_features = np.array([reading.num_words, reading.num_questions], dtype=np.float32)
        combined_emb = np.concatenate([text_emb, diff_onehot, numeric_features], axis=0)
        combined_embeddings.append(combined_emb)

    embeddings_raw = np.array(combined_embeddings, np.float32)

    scaler_raw = StandardScaler().fit(embeddings_raw)
    joblib.dump(scaler_raw, "scaler_raw.pkl")
    embeddings_std = scaler_raw.transform(embeddings_raw)


    pca = PCA(n_components=settings.item_embedding_dim).fit(embeddings_std)
    joblib.dump(pca, "pca.pkl")
    embeddings_reduced = pca.transform(embeddings_raw)
    print(f"Reduced dimension from {embeddings_std.shape[1]} → {settings.item_embedding_dim} using PCA...")
    print(f"Giữ lại {pca.explained_variance_ratio_.sum():.2%} thông tin")

    scaler_pca = StandardScaler().fit(embeddings_reduced)
    joblib.dump(scaler_pca, "scaler_pca.pkl")
    embeddings_reduced_std = scaler_pca.transform(embeddings_reduced)

    # 5️⃣ Upsert embeddings
    for reading, emb in zip(readings, embeddings_reduced_std):
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
        f"(only text dim={text_embeddings.shape[1] + 6 + 2})"
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


def init_user_embedding(session: Session, noise_scale: float = 0.2) -> Optional[np.ndarray]:
    """Retrieve the embedding for a reading_id as a NumPy array (dtype float32)."""
    emb_row = session.exec(
        select(ReadingEmbedding).order_by(func.random()).limit(1)
    ).first()
    if not emb_row:
        return None

    arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
    noise = np.random.normal(loc=0.0, scale=noise_scale, size=arr.shape).astype(np.float32)
    final = (arr + noise)
    return final

def init_user_embedding_by_level(session: Session, user_level: int, noise_scale: float = 0.01) -> Optional[np.ndarray]:
    """Retrieve the embedding for a reading_id as a NumPy array (dtype float32)."""
    # Try to find embeddings for this level or lower levels
    while user_level >= 0:
        emb_rows = session.exec(
            select(ReadingEmbedding).join(Reading).where(Reading.difficulty == user_level)
        ).all()

        if emb_rows:  # if we found any embeddings
            emb_row = np.random.choice(emb_rows)  # choose one randomly
            arr = np.frombuffer(emb_row.vector_blob, dtype=np.float32).copy()
            noise = np.random.normal(loc=0.0, scale=noise_scale, size=arr.shape).astype(np.float32)
            return arr + noise

        user_level -= 1

    # If no embedding found at all
    return None


def get_all_embeddings(session: Session):
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



def get_candidate_embeddings(
    session: Session, 
    preferred_topic_ids: List[int], 
    recent_item_ids: List[int],
    recent_embs: List[np.ndarray],
    per_topic_limit: int = 2,
    nearest_k: int = 8,
    random_k: int = 5
) -> Tuple[List[np.ndarray], List[int]]:

    # Get readings from preferred topics (e.g. 2 per topic)
    topic_readings_ids = []
    
    for topic_id in preferred_topic_ids:
        result = (
            session.exec(
                select(Reading)
                .where(Reading.topic_id == topic_id)
                .where(Reading.id.notin_(recent_item_ids))
                .order_by(func.random())
                .limit(per_topic_limit)
            )
            .all()
        )
        topic_readings_ids.extend([r.id for r in result])

    # Get ALL embeddings except recent ones
    all_embeddings = (
        session.exec(
            select(ReadingEmbedding)
            .where(ReadingEmbedding.reading_id.notin_(recent_item_ids))
        )
        .all()
    )

    # Convert blob vectors into a matrix
    ids = np.array([emb.reading_id for emb in all_embeddings])
    vecs = np.stack([blob_to_vector(emb.vector_blob) for emb in all_embeddings]).astype(np.float32)

    # Compute nearest K neighbors to user embedding
    if len(recent_embs) == 0:
        mean_recent_embs = np.zeros(settings.item_embedding_dim)
    else:
        temp_arr = np.asarray(recent_embs, dtype=np.float32)
        mean_recent_embs = np.mean(temp_arr, axis=0).astype(np.float32)

    # Get top K indices
    topk_idxs = top_k_l2_nearest_idx(vecs, mean_recent_embs, k=nearest_k)

    # Map back to IDs
    nearest_ids = ids[topk_idxs].tolist()

    # Random sampling (exclude chosen ones)
    used_ids = set(topic_readings_ids + nearest_ids)
    remaining_ids = [id for id in ids if id not in used_ids]
    random_ids = random.sample(
        remaining_ids, 
        min(random_k, len(remaining_ids))
    )

    # Combine final IDs and load vectors
    final_ids = list(set(topic_readings_ids + nearest_ids + random_ids))
    final_ids = [int(x) for x in final_ids]
    
    # Map reading_id --> vector for fast lookup
    id_to_vec = {id: vec for id, vec in zip(ids, vecs)}
    item_embeddings = [id_to_vec[id] for id in final_ids]

    return item_embeddings, final_ids

def create_embedding_from_reading(
    reading: Reading,
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    batch_size: int = 64,
    include_questions: bool = True
) -> np.ndarray:
    """
    Tạo embedding cho 1 Reading, giống hệt giá trị vector_blob trong DB.
    """
    # 1️⃣ Chuẩn hóa text từ Reading
    text = _reading_to_text(reading, include_questions=include_questions)

    # 2️⃣ Encode text
    model = SentenceTransformer(model_name)
    text_emb = embed_long_text_by_sentences(model, text, batch_size)

    # 3️⃣ Thêm metadata
    diff_onehot = np.zeros(6, dtype=np.float32)
    if 0 <= getattr(reading, "difficulty", 0) <= 5:
        diff_onehot[reading.difficulty] = 1.0

    numeric_features = np.array([
        getattr(reading, "num_words", 0),
        getattr(reading, "num_questions", 0)
    ], dtype=np.float32)

    combined_emb = np.concatenate([text_emb, diff_onehot, numeric_features], axis=0).reshape(1, -1)

    # 4️⃣ Load các scaler và PCA đã fit trên toàn bộ dataset
    scaler_raw = joblib.load("scaler_raw.pkl")
    pca = joblib.load("pca.pkl")
    scaler_pca = joblib.load("scaler_pca.pkl")

    # 5️⃣ Chuẩn hóa và giảm chiều giống DB
    emb_std = scaler_raw.transform(combined_emb)
    emb_reduced = pca.transform(emb_std)
    emb_final = scaler_pca.transform(emb_reduced)

    return emb_final[0]  # trả về 1D vector