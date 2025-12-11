from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import numpy as np
import redis
import random
import llama_cpp
import os
import threading
import time
import json
import pickle
import pandas as pd
from sqlmodel import Session, select, func
from app.schemas import RecommendRequest
from app.models import User
from app.database import engine
from app.models import ObjectiveQuestion, Reading, UserTopicLink, Topic, ParagraphAuthor, HistoryGenerateQuestion
from app.models import ReadingEmbedding
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from sentence_transformers import SentenceTransformer
from app.services.readmepp import predict_cefr 
from app.config import settings
from app.services.history_generate_question import insert_history_generate_question
from redis_client import r
from app.services.item_embeddings import create_embedding_from_reading
MAX_CANDIDATES = 8 
Q_DIM = 384
TOP_K = 5
MODEL_PATH = "./ai_models/ppo_question_rec.zip"
ppo_model = PPO.load(MODEL_PATH, device="cpu")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
# khởi tạo model llama
model = llama_cpp.Llama(
    model_path="ai_models/llama-3.2-3B-Instruct-f8.gguf",
    #seed = -1,
    n_ctx=5000,
    chat_fomat = "llama-3"
)

def get_session(session_id: str):
    raw = r.get(f"session:{session_id}")
    if raw:
        return json.loads(raw)
    return None

def save_session(session_id:str, data: dict):
    r.set(f"session:{session_id}", json.dumps(data))

# Hàm tạo input đầu vào cho model PPO
def build_observation(user_emb: np.ndarray, passage_emb: np.ndarray, cand_embs: np.ndarray):
    """
    Concatenate into observation vector shape (OBS_DIM,)
    cand_embs should be shape (k, Q_DIM) where k == MAX_CANDIDATES (padded if needed)
    """
    if cand_embs.shape[0] != MAX_CANDIDATES:
        # pad with zeros
        padded = np.zeros((MAX_CANDIDATES, Q_DIM), dtype=np.float32)
        padded[:cand_embs.shape[0], :] = cand_embs
        cand_embs = padded
    return np.concatenate([user_emb, passage_emb, cand_embs.flatten()]).astype(np.float32)

# Hàm generate question bằng llama
def generate_question_by_llama(passage: str, num_questions: int):
    prompt = f"""
    You are an expert English reading comprehension test creator.

    Your task:
    1. Read the passage below.
    2. Infer:
    - **title**: a short meaningful headline (5–10 words)
    - **topic**: the main subject (must follow the topic constraint below)
    3. Then **generate EXACTLY {num_questions} high-quality multiple-choice questions (MCQs)** based strictly on the passage.

    TOPIC CONSTRAINTS:
    - The "topic" MUST be chosen from the following fixed list:
    ["environment", "education", "health", "technology", "science", "history",
    "culture", "business", "economy", "society", "art", "travel"]
    - You MUST select exactly one topic.
    - The topic MUST be lowercase exactly as written in the list.
    - Do NOT create new topics or subtopics.

    Each question MUST include:
    - "question_text": the question itself
    - "option_a", "option_b", "option_c", "option_d": four answer choices
    - "answer": the correct option letter (A/B/C/D)
    - "explanation": 1–3 sentences explaining the correct answer

    CRITICAL RULES:
    - You MUST generate all {num_questions} questions. Do NOT output JSON unless the questions list is fully completed.
    - The output MUST be **strictly valid JSON**.
    - NO trailing commas.
    - NO duplicated keys.
    - Each question MUST be inside its own object in the list.
    - Do NOT omit the questions section.
    - Do NOT shorten or summarize the output.
    Your final answer MUST be a JSON object in this EXACT structure:

    {{
    "title": "<inferred title>",
    "topic": "<inferred topic>",
    "questions": [
        {{
        "question_text": "<question text>",
        "option_a": "<option A>",
        "option_b": "<option B>",
        "option_c": "<option C>",
        "option_d": "<option D>",
        "answer": "<correct option letter>",
        "explanation": "<why it is correct>"
        }}
    ]
    }}

    Before producing the final JSON:
    - Double-check that you generated exactly {num_questions} question objects.
    - Ensure the JSON can be parsed successfully.

    Passage:
    \"\"\"{passage}\"\"\"
    """

    result = model.create_chat_completion(
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2400,
        response_format = { "type": "json_object" }
    )
    return result["choices"][0]["message"]["content"]

# Hàm kiểm tra xem Llama có generate ra kết quả hợp lệ ko
def has_required_fields(data: dict):
    required = {"title", "topic", "questions"}
    return required.issubset(data.keys())

# Hàm chuẩn hóa questions do llama sinh ra
def convert_answer_letter_to_value(question_obj: Dict):
    letter_map = {
        "a": "option_a",
        "b": "option_b",
        "c": "option_c",
        "d": "option_d"
    }
    print(f"input cua ham chuan hoa answer la: {question_obj}")
    anwer_letter = question_obj.get("answer", "").lower()
    if anwer_letter not in letter_map:
        return question_obj
    correct_value = question_obj.get(letter_map[anwer_letter])
    question_obj["answer"] = correct_value
    return question_obj

# Hàm chuẩn hóa object_question  
def convert_object_question_format(q: ObjectiveQuestion):
    idx_to_letter = {
        0: "option_a",
        1: "option_b",
        2: "option_c",
        3: "option_d"
    }
    correct_field = idx_to_letter.get(q.correct_option)
    correct_text = getattr(q, correct_field)
    output = {
        "question_text": q.question_text,
        "option_a": q.option_a,
        "option_b": q.option_b,
        "option_c": q.option_c,
        "option_d": q.option_d,
        "answer": correct_text,
        "explanation": q.explanation
    }

    return output

# embedding user, reading, candicate question 
def encode_with_overlap(text: str, segment_len: int = 200, overlap_ratio: float = 0.3):
    """
    Encode a long text into a single embedding using sliding window with overlap.

    Args:
        text: str, văn bản cần encode
        segment_len: int, số ký tự mỗi đoạn
        overlap_ratio: float, tỉ lệ chồng lấp giữa các đoạn liên tiếp (0..1)

    Returns:
        np.ndarray: embedding cuối cùng (có thể gộp mean các đoạn)
    """
    text = " ".join(text.split())  # normalize whitespace
    if len(text) <= segment_len:
        # text ngắn, encode trực tiếp
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

    # gộp các đoạn thành 1 embedding: mean pooling
    final_emb = np.mean(embeddings, axis=0)
    return final_emb

# Tìm bài đọc tương đồng, giống với input nhất
def find_nearest_passage(passage_text_emb: np.ndarray, passage_embs: np.ndarray):
    # cosine similarity
    dot = np.dot(passage_embs, passage_text_emb)
    norm_passages = np.linalg.norm(passage_embs, axis=1)
    norm_input = np.linalg.norm(passage_text_emb) + 1e-8
    cos_sims = dot / (norm_passages * norm_input + 1e-8)
    nearest_idx = np.argmax(cos_sims)
    nearest_passage_emb = passage_embs[nearest_idx]
    return nearest_passage_emb, cos_sims[nearest_idx]

# Hàm lấy embedding reading và chuyển thành matrix
def get_all_reading_embedding():
    with Session(engine) as session:
        statement = select(ReadingEmbedding.optional_vector)
        reading_embedding = session.exec(statement).all()
        return reading_embedding
def load_reading_embeddings_as_matrix():
    blobs = get_all_reading_embedding()
    vectors = []
    for blob in blobs:
        vec = pickle.loads(blob)
        vectors.append(vec)
    return np.vstack(vectors)

def get_all_reading_text():
    with Session(engine) as session:
        statement = select(Reading.content_text)
        reading_text = session.exec(statement).all()
        return reading_text

def build_reading_embedding_matrix():
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    reading_texts = get_all_reading_text()
    embeddings = embedder.encode_with_overlap(reading_texts)
    emb_matrix = np.vstack(embeddings)
    print("Done. Matrix shape:", emb_matrix.shape)
    return emb_matrix

# Hàm tìm id bài reading bằng text embedding
def find_reading_id_by_embedding(reading_embedding: np.ndarray):
    blob = pickle.dumps(reading_embedding)
    with Session(engine) as session:
        statement = (select(ReadingEmbedding.reading_id, Reading.content_text)
                     .join(Reading, Reading.id == ReadingEmbedding.reading_id)
                     .where(ReadingEmbedding.optional_vector == blob))
        reading_content_text = session.exec(statement).all()
        return reading_content_text

# Hàm thêm embeding dạng đầy đủ vào bảng reading_embedding
def insert_reading_embedding(reading_embedding: ReadingEmbedding):
    with Session(engine) as session:
        try:
            session.add(reading_embedding)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
# Hàm lấy các câu hỏi theo Id của bài đọc
def find_question_by_reading_id(reading_id: int):
    with Session(engine) as session:
        statement = select(ObjectiveQuestion).where(ObjectiveQuestion.reading_id == reading_id)
        object_questions = session.exec(statement).all()
        return object_questions

# Hàm tìm user_info từ user_name
def find_user_by_user_name(user_name: str):
    with Session(engine) as session:
        statement = (select(User.username, User.goal_type, Topic.name, User.id)
                     .join(UserTopicLink, UserTopicLink.user_id == User.id)
                     .join(Topic, Topic.id == UserTopicLink.topic_id)
                     .where(User.username == user_name))
        user_info = session.exec(statement).all()
        return user_info
# Tìm kiếm các câu hỏi ứng viên
def prepare_candidate_list_from_passage_text(passage_text: str, max_cand=MAX_CANDIDATES):
    """
    Nhận passage_text mới từ client, tìm passage gần nhất bằng embedding,
    trả candidate question indices.
    """
    try:
        # --- normalize input passage ---
        print(f"input là: {passage_text}")
        passage_text_clean = " ".join(passage_text.replace("\n", " ").split()).strip()

        # embedding passage input
        passage_emb_new = encode_with_overlap(passage_text_clean)

        # --- tìm passage gần nhất ---
        passage_embs = load_reading_embeddings_as_matrix()
        nearest_passage_emb, sim = find_nearest_passage(passage_emb_new, passage_embs)
        print(sim)
        result = find_reading_id_by_embedding(nearest_passage_emb)
        nearest_passage_text = result[0][1]
        print(f"passage giong nhat {nearest_passage_text}")
        # nếu similarity quá thấp -> fallback random
        if sim < 0.9:
            print("Low similarity -> fallback random questions")
            return None, None
        # lấy candidates từ nearest passage
        candidates = find_question_by_reading_id(result[0][0])
        print(f"candicate là: {candidates}")
        #print(f"Passage_text_clean: {passage_text_clean}")
        # giới hạn max_cand
        if len(candidates) > max_cand:
            candidates = random.sample(candidates, max_cand)
    
        random.shuffle(candidates)
        return candidates, nearest_passage_emb

    except Exception as e:
        print(f"ERROR in prepare_candidate_list_from_passage_text: {e}")
        return None, None
    
# Hàm thêm Reading
def insert_reading(reading: Reading, session: Session = Depends(get_session)):
    try:
        session.add(reading)
        session.commit()
        session.refresh(reading)
        return reading
    except Exception as e:
        session.rollback()
        raise e
    
# Hàm thêm question Object 
def insert_question_object(object_questions: list[ObjectiveQuestion]):
    with Session(engine) as session:
        try:
            for question in object_questions:
                session.add(question)
            session.commit()
            object_question_ids = [question.id for question in object_questions]
            return object_question_ids
        except Exception as e:
            session.rollback()
            raise e
    
# Hàm thêm ParagraphAuthor
def insert_paragraph_author(paragraph_author: ParagraphAuthor, session: Session):
    try: 
        session.add(paragraph_author)
        session.commit()
        return paragraph_author
    except Exception as e:
        session.rollback()
        raise e

# Hàm chọn questions trong candicates để gợi ý nếu số lượng candicates đủ, nếu ko đủ dùng LLM để sinh
def generate_question_from_passage(req: RecommendRequest, session: Session):
    info_answers = {"a":0, "b":1, "c": 2, "d": 3}
    print(f"Ten cua nguoi dung la:{req.user_name}")
    user_info = find_user_by_user_name(user_name=req.user_name)
    questions_list, nearest_passage_emb = prepare_candidate_list_from_passage_text(req.passage_text)
    
    if questions_list is None or nearest_passage_emb is None:
        print(f"Phai gen moi hoan toan")
        question_objects_norm = {}
        for i in range(10):
            question_objects = generate_question_by_llama(req.passage_text, req.top_k)
            question_objects_norm = json.loads(question_objects)
            if has_required_fields(question_objects_norm):
                break
        avg_diff = predict_cefr(str(req.passage_text) + " " + question_objects_norm.get("title"))
        print("===== CHECK PASSAGE INFO =====")
        print(f"title: {question_objects_norm.get('title')}")
        print(f"content_text: {req.passage_text}")
        print(f"difficulty (avg_diff): {avg_diff}")
        print(f"num_questions (req.top_k): {req.top_k}")

        topic_raw = question_objects_norm.get("topic")
        topic_id_found = find_topic_id_by_topic(topic_raw)

        print(f"topic_raw: {topic_raw}")
        print(f"topic_id_found: {topic_id_found}")   # Bạn xem thử có phải list không
        print(f"topic_id (first element): {topic_id_found}")

        print("================================\n")

        new_reading = Reading(
            title=question_objects_norm.get("title"),
            content_text=req.passage_text,
            difficulty=avg_diff,
            num_questions=req.top_k,
            topic_id=find_topic_id_by_topic(question_objects_norm.get("topic"))
        )
        reading = insert_reading(new_reading, session)
        print(f"Them doan van moi thanh cong")
        new_reading_embedding = ReadingEmbedding(
            reading_id=reading.id,
            vector_blob=create_embedding_from_reading(reading),
            optional_vector=json.dumps(encode_with_overlap(req.passage_text))
        )
        insert_reading_embedding(new_reading_embedding)
        new_paragraph_author = ParagraphAuthor(
            passage_text=req.passage_text,
            user_id=user_info[0][3]
        )
        paragraph_author = insert_paragraph_author(new_paragraph_author, session)   
        print(f"Them tac gia cua bai doc moi thanh cong")
        final_question_object = question_objects_norm.get("questions")
        list_object_questions = []
        for i in range(len(final_question_object)):
            print("===== CHECK QUESTION INDEX", i, "=====")
            print(f"reading_id: {reading.id}")
            print(f"question_text: {final_question_object[i].get('question_text')}")
            print(f"option_a: {final_question_object[i].get('option_a')}")
            print(f"option_b: {final_question_object[i].get('option_b')}")
            print(f"option_c: {final_question_object[i].get('option_c')}")
            print(f"option_d: {final_question_object[i].get('option_d')}")
            # Kiểm tra answer
            ans_raw = question_objects_norm.get("questions")[i].get("answer")
            ans_mapped = info_answers.get(ans_raw.lower())
            print(f"raw_answer: {ans_raw}")
            print(f"mapped_correct_option: {ans_mapped}")
            print(f"explanation: {final_question_object[i].get('explanation')}")
            print("====================================\n")
            object_question = ObjectiveQuestion(
                reading_id=reading.id,
                question_text=final_question_object[i].get("question_text"),
                option_a=final_question_object[i].get("option_a"),
                option_b=final_question_object[i].get("option_b"),
                option_c=final_question_object[i].get("option_c"),
                option_d=final_question_object[i].get("option_d"),
                correct_option=info_answers.get(question_objects_norm.get("questions")[i].get("answer").lower()),
                explanation=final_question_object[i].get("explanation")
            )
            list_object_questions.append(object_question)
        object_question_ids = insert_question_object(list_object_questions)
        # Them history
        list_history_generate_question = []
        for i in range(len(final_question_object)):
            history_generate_question = HistoryGenerateQuestion(
                user_id=user_info[0][3],
                lession_id=req.session_id,
                object_question_id=object_question_ids[i]
            )
            list_history_generate_question.append(history_generate_question)
        insert_history_generate_question(list_history_generate_question)
        print(f"Them lich su tao cau hoi thanh cong/ lich su nay cho truong hop reading moi hoan toan")
        final_question_object_norm = [convert_answer_letter_to_value(q) for q in question_objects_norm.get("questions")]
        s = {
            "user_name": req.user_name,
            "passage_text": req.passage_text,
            "reject_list": [],
            "recommend_so_far": [q.get("question_text") for q in final_question_object_norm],
            "candidate_list":[]
        }
        save_session(req.session_id, s)
        return final_question_object_norm
    else: 
        print("chi can gen them hoac xai tiep")
        candidates = [q.question_text for q in questions_list]
        reading_id = find_reading_id_by_embedding(nearest_passage_emb)[0][0]
        s = get_session(req.session_id)
        if s is None:
            s = {
                "user_name": req.user_name,
                "passage_text": req.passage_text,
                "reject_list": [],
                "recommend_so_far": [],
                "candidate_list": candidates
            }
            save_session(req.session_id, s)
        else:
            if s["passage_text"] != req.passage_text:
                s["reject_list"] = []
                s["recommend_so_far"] = []
                s["candidate_list"] = candidates
                s["passage_text"] = req.passage_text
        reject = set(s["reject_list"])
        shown = set(s["recommend_so_far"])
        avail = [c for c in s["candidate_list"] if c not in reject and c not in shown]

        if len(avail) == 0:
            print("so luong cau hoi ung vien = 0 nen phai gen them")
            # generate question
            question_objects_norm = {}
            for i in range(10):
                question_objects = generate_question_by_llama(req.passage_text, req.top_k)
                question_objects_norm = json.loads(question_objects)
                if has_required_fields(question_objects_norm):
                    break
            final_question_object = question_objects_norm.get("questions")
            print("cau hoi do llama gen ra la:", question_objects_norm)
            print("correct answer do llama sinh ra la:", info_answers.get(question_objects_norm.get("questions")[0].get("answer")))
            list_object_questions = []
            for i in range(len(final_question_object)):
                object_question = ObjectiveQuestion(
                    reading_id=reading_id,
                    question_text=final_question_object[i].get("question_text"),
                    option_a=final_question_object[i].get("option_a"),
                    option_b=final_question_object[i].get("option_b"),
                    option_c=final_question_object[i].get("option_c"),
                    option_d=final_question_object[i].get("option_d"),
                    correct_option=info_answers.get(question_objects_norm.get("questions")[i].get("answer").lower()),
                    explanation=final_question_object[i].get("explanation")
                )
                list_object_questions.append(object_question)
                print(f"them cau hoi moi thu {i} thanh cong")
            object_question_ids = insert_question_object(list_object_questions)

            # Them history
            list_history_generate_question = []
            for i in range(len(final_question_object)):
                history_generate_question = HistoryGenerateQuestion(
                    user_id=user_info[0][3],
                    lession_id=req.session_id,
                    object_question_id=object_question_ids[i]
                )
                list_history_generate_question.append(history_generate_question)
            insert_history_generate_question(list_history_generate_question)
            print(f"them lich su generate cau hoi thanh cong/ lich su nay cho truong hop so luong cau hoi ung vien = 0")
            final_question_object_norm = [convert_answer_letter_to_value(q) for q in question_objects_norm.get("questions")]
            s["candidate_list"].extend(q["question_text"] for q in final_add_question_norm)
            save_session(req.session_id, s)
            return final_question_object_norm
        else:
            cand_embs = np.array([encode_with_overlap(p) for p in avail])
            print(f"Thong tin Nguoi dung la: {user_info} ")
            print(f"loai du lieu la: {type(user_info)}")
            user_goal = user_info[0][1]
            print(f"muc tieu hoc la:{user_goal}")
            favorite_topics = [topic for _, _, topic, _ in user_info]
            print(f"chay duoc favorite topic:{favorite_topics}")
            user_pre_emb = f"name: {req.user_name}.goal: {user_goal}. favorite topics:{','.join(favorite_topics)}"
            user_emb = encode_with_overlap(user_pre_emb)
            obs = build_observation(user_emb, nearest_passage_emb, cand_embs).reshape(1, -1)
            draws = 16
            picks = []
            for _ in range(draws):
                act, _ = ppo_model.predict(obs, deterministic=False)
                picks.append(int(act[0]))

            counts = {}
            for p in picks:
                counts[p] = counts.get(p, 0) + 1
            print(f"Cac cau hoi duoc chon la:{picks}")
            # highlight: lọc chỉ các pos hợp lệ, tránh IndexError
            ranked_pos = sorted(counts.keys(), key=lambda x: counts[x], reverse=True)
            top_pos = [pos for pos in ranked_pos if pos < len(avail)][:req.top_k]  
            chosen_qidxs = [avail[int(pos)] for pos in top_pos]
            list_question_chonsen = [q for q in questions_list if q.question_text in chosen_qidxs]
            list_history_candicadate_question = []
            for i in range(len(list_question_chonsen)):
                history_candidate_question = HistoryGenerateQuestion(
                    user_id=user_info[0][3],
                    lession_id=req.session_id,
                    object_question_id=list_question_chonsen[i].id
                )
                list_history_candicadate_question.append(history_candidate_question)
            insert_history_generate_question(list_history_candicadate_question)
            print(f"them lich su generate cau hoi thanh cong/ truong hop nay cho cac cau hoi ung vien co san")

            question_candidates = [convert_object_question_format(q) for q in questions_list if q.question_text in chosen_qidxs]
            print(f"cau hoi ung vien la: {question_candidates}")
            if len(chosen_qidxs) < req.top_k:
                print("Do so luong cau hoi ung vien < k nen phai gen bo sung")
                add_len = req.top_k - len(chosen_qidxs)
                print(f"So luong cau hoi can gen them la:{add_len}")
                add_question = ""
                process_add_question = {}
                for i in range(10):
                    add_question = generate_question_by_llama(req.passage_text, add_len)
                    process_add_question = json.loads(add_question)
                    #print(f"gen lan thu {i}")
                    if has_required_fields(process_add_question):
                        break
                print(f"cau hoi do llama gen ra la:{add_question}")
                print(f"dinh dang cua process_add_question la: {type(process_add_question)}")
                print(f"cac cau hoi dc llama gen ra la:{process_add_question}")
                add_question_norm = process_add_question.get("questions")
                print(f"dinh dang cua 1 phan tu cau hoi them vao la: {type(add_question_norm[0])}")
                list_object_questions = []
                for i in range(len(add_question_norm)):
                    print("=== DEBUG ADD QUESTION ===")
                    print("reading_id:", reading_id)
                    print("question_text:", add_question_norm[i].get("question_text"))
                    print("option_a:", add_question_norm[i].get("option_a"))
                    print("option_b:", add_question_norm[i].get("option_b"))
                    print("option_c:", add_question_norm[i].get("option_c"))
                    print("option_d:", add_question_norm[i].get("option_d"))
                    print("explanation:", add_question_norm[i].get("explanation"))
                    print("correct_option from info_answers:",info_answers.get(process_add_question.get("questions")[i].get("answer").lower()))
                    print("==========================")

                    object_question = ObjectiveQuestion(
                        reading_id=reading_id,
                        question_text=add_question_norm[i].get("question_text"),
                        option_a=add_question_norm[i].get("option_a"),
                        option_b=add_question_norm[i].get("option_b"),
                        option_c=add_question_norm[i].get("option_c"),
                        option_d=add_question_norm[i].get("option_d"),
                        correct_option=info_answers.get(process_add_question.get("questions")[i].get("answer").lower()),
                        explanation=add_question_norm[i].get("explanation"),
                        order_index=i
                    )
                    print(f"question duoc them vao la: {object_question}")
                    list_object_questions.append(object_question)
                object_question_ids = insert_question_object(list_object_questions)
                # Them history
                list_history_generate_question = []
                for i in range(len(add_question_norm)):
                    history_generate_question = HistoryGenerateQuestion(
                        user_id=user_info[0][3],
                        lession_id=req.session_id,
                        object_question_id=object_question_ids[i]
                    )
                    list_history_generate_question.append(history_generate_question)
                insert_history_generate_question(list_history_generate_question)
                print(f"Them lich su generate cau hoi thanh cong/ truong hop nay cho cac cau hoi ung vien ko du so luong")
                final_add_question_norm = [convert_answer_letter_to_value(q) for q in process_add_question.get("questions")]
                print(f"cac cau hoi sau khi chuan hoa la:{type(final_add_question_norm)}")
                print(final_add_question_norm)
                print(f"danh sach cau hoi ung vien la: {question_candidates}")
                try:
                    question_candidates.extend(final_add_question_norm)
                except Exception as e:
                    print("hop nhat 2 file ko thanh cong")
                    raise e
                print("tao dang kiem tra")
                text = question_candidates[0].get("question_text")
                print(f"Kiem tra xem out ra cai gi: {text}")
                print(f"dinh dang cua 1 phan tu trong danh sach cau hoi ung vien la:{type(question_candidates[0])}")
                s["candidate_list"].extend([q.get("question_text") for q in question_candidates])
                save_session(req.session_id, s)
                print(f"Danh sach cau hoi mang di goi y la: {question_candidates}, /n dinh dang la: {type(question_candidates[0])}")
                test = [q.get("question_text") for q in question_candidates]
                print(f"dinh dang cua test la:{test}")
                print(test)
            print("CHAY DUOC ROI")
            return question_candidates
        
def find_topic_id_by_topic(topic: str):
    topic = topic.strip()

    with Session(engine) as session:
        # 1. Tìm topic khớp chính xác (case-insensitive)
        statement = select(Topic).where(func.lower(Topic.name) == topic.lower())
        result = session.exec(statement).first()

        if result:
            return result.id  # tìm thấy thì trả về luôn

        # 2. Không có -> lấy tất cả topic để so sánh
        all_topics = session.exec(select(Topic)).all()
        if not all_topics:
            return None

        topic_names = [t.name for t in all_topics]

        # 3. Encode topic input
        input_emb = encode_with_overlap(topic)

        # 4. Encode tất cả Topic.name -> matrix
        topic_embs = []
        for name in topic_names:
            emb = encode_with_overlap(name)
            topic_embs.append(emb)
        topic_embs = np.vstack(topic_embs)  # shape (N, D)

        # 5. Tìm topic giống nhất
        nearest_emb, sim = find_nearest_passage(input_emb, topic_embs)
        nearest_idx = np.argmax([
            np.dot(topic_embs[i], input_emb) /
            ((np.linalg.norm(topic_embs[i]) * np.linalg.norm(input_emb)) + 1e-8)
            for i in range(len(topic_embs))
        ])

        best_topic = all_topics[nearest_idx]
        return best_topic.id
     

################################################# Test ###########################

# passage = f"""
# The rain had continued for a week and the flood had created a big river which were running by Nancy Brown's farm. As she tried to gather her cows to a higher ground, she slipped and hit her head on a fallen tree trunk. The fall made her unconscious for a moment or two. When she came to, Lizzie, one of her oldest and favorite cows, was licking her face. 
# At that time, the water level on the farm was still rising. Nancy gathered all her strength to get up and began walking slowly with Lizzie. The rain had become much heavier, and the water in the field was now waist high. Nancy's pace got slower and slower because she felt a great pain in her head. Finally, all she could do was to throw her arm around Lizzie's neck and try to hang on. About 20 minutes later, Lizzie managed to pull herself and Nancy out of the rising water and onto a bit of high land, which seemed like a small island in the middle of a lake of white water. 
# Even though it was about noon, the sky was so dark and the rain and lightning was so bad that it took rescuers more than two hours to discover Nancy. A man from a helicopter  lowered a rope, but Nancy couldn't catch it. A moment later, two men landed on the small island from a ladder in the helicopter. They raised her into the helicopter and took her to the school gym, where the Red Cross had set up an emergency shelter. 
# When the flood disappeared two days later, Nancy immediately went back to the "island." Lizzie was gone. She was one of 19 cows that Nancy had lost in the flood. "I owe my life to her," said Nancy with tears.
# """
# req = RecommendRequest(
#     session_id="kk",
#     user_name="ky",
#     passage_text=passage,
#     top_k=5
# )
# output = ""
# for i in range(10):
#     output = generate_question_by_llama(passage, 6)
#     print(f"lan thu thu {i}")
#     result = json.loads(output)
#     if has_required_fields(result):
#         break
# print(output)
# result = json.loads(output)
# questions = result.get("questions")
# info_answers = {"a":0, "b":1, "c": 2, "d": 3}
# for i in questions:
#     object_question = ObjectiveQuestion(
#         reading_id=1,
#         question_text=i.get("question_text"),
#         option_a=i.get("option_a"),
#         option_b=i.get("option_b"),
#         option_c=i.get("option_c"),
#         option_d=i.get("option_d"),
#         correct_option=info_answers.get(i.get("answer")),
#         explanation=i.get("explanation"),
#         order_index=2
#     )
#     with Session(engine) as session:
#         session.add(object_question)
#         session.commit()
#         print("Inserted ID:", object_question.id)



# candidates = generate_question_from_passage(input)
# print(candidates)

# candidates, nearest_passage_emb = prepare_candidate_list_from_passage_text(passage)
# print("type cua ung vien la:",type(candidates))
# print("type cua doan van gan nhat la:", type(nearest_passage_emb))
# user_info = find_user_by_user_name("ky")
# print(user_info)

# ---------------------------------Kiem tra ham them cau hoi ----------------------


# add_question = ""
# process_add_question = {}
# reading_id = 1
# for i in range(10):
#     add_question = generate_question_by_llama(req.passage_text, 5)
#     process_add_question = json.loads(add_question)
#     #print(f"gen lan thu {i}")
#     if has_required_fields(process_add_question):
#         break
# print(f"cau hoi do llama gen ra la:{add_question}")
# print(f"dinh dang cua process_add_question la: {type(process_add_question)}")
# print(f"cac cau hoi dc llama gen ra la:{process_add_question}")
# add_question_norm = process_add_question.get("questions")
# print(f"dinh dang cua 1 phan tu cau hoi them vao la: {type(add_question_norm[0])}")
# list_object_questions = []
# for i in range(len(add_question_norm)):
#     print("=== DEBUG ADD QUESTION ===")
#     print("reading_id:", reading_id)
#     print("question_text:", add_question_norm[i].get("question_text"))
#     print("option_a:", add_question_norm[i].get("option_a"))
#     print("option_b:", add_question_norm[i].get("option_b"))
#     print("option_c:", add_question_norm[i].get("option_c"))
#     print("option_d:", add_question_norm[i].get("option_d"))
#     print("explanation:", add_question_norm[i].get("explanation"))
#     print("correct_option from info_answers:",info_answers.get(process_add_question.get("questions")[i].get("answer").lower()))
#     print("==========================")

#     object_question = ObjectiveQuestion(
#         reading_id=reading_id,
#         question_text=add_question_norm[i].get("question_text"),
#         option_a=add_question_norm[i].get("option_a"),
#         option_b=add_question_norm[i].get("option_b"),
#         option_c=add_question_norm[i].get("option_c"),
#         option_d=add_question_norm[i].get("option_d"),
#         correct_option=info_answers.get(process_add_question.get("questions")[i].get("answer").lower()),
#         explanation=add_question_norm[i].get("explanation"),
#         order_index=i
#     )
#     list_object_questions.append(object_question)
#     print(f"question duoc them vao la: {object_question}")
# insert_question_object(list_object_questions)
# final_add_question_norm = [convert_answer_letter_to_value(q) for q in process_add_question.get("questions")]