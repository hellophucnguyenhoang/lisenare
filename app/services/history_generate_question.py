from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
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
from sqlmodel import Session, select
from app.schemas import RecommendRequest
from app.models import User
from app.database import engine
from app.models import ObjectiveQuestion, Reading, UserTopicLink, Topic, ParagraphAuthor, HistoryGenerateQuestion
from app.models import ReadingEmbedding
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
from sentence_transformers import SentenceTransformer
from app.services.readmepp import predict_cefr 
def get_all_history_generate_question():
    with Session(engine) as session:
        statement = select(HistoryGenerateQuestion)
        all_history_generate_question = session.exec(statement).all()
        return all_history_generate_question
def find_history_generate_question_by_user_id(user_id: int):
    with Session(engine) as session:
        statement = select(HistoryGenerateQuestion).where(HistoryGenerateQuestion.user_id == user_id)
        try:
            history_generate_question = session.exec(statement).all()
            return history_generate_question
        except Exception as e:
            session.rollback()
            raise e
def insert_history_generate_question(histories: list[HistoryGenerateQuestion]):
    with Session(engine) as session:
        try: 
            for i in histories:
                session.add(i)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
def get_reading_question_history_by_user_id(user_id: int):
    with Session(engine) as session:
        statement = (select(HistoryGenerateQuestion, Reading.content_text, Reading.title,ObjectiveQuestion)
                     .where(HistoryGenerateQuestion.user_id == user_id)
                     .join(ObjectiveQuestion, ObjectiveQuestion.id == HistoryGenerateQuestion.object_question_id)
                     .join(Reading, Reading.id == ObjectiveQuestion.reading_id)
                     )
        result = session.exec(statement).all()
        return result
def group_history_output(raw_data):
    grouped = {}

    for history, passage, title, question in raw_data:
        lession_id = history.lession_id
        reading_id = question.reading_id

        # Tạo nhóm lesson nếu chưa có
        if lession_id not in grouped:
            grouped[lession_id] = {}

        # Tạo nhóm reading nếu chưa có
        if reading_id not in grouped[lession_id]:
            grouped[lession_id][reading_id] = {
                "user_id": history.user_id,
                "reading_id": reading_id,
                "lession_id": lession_id,
                "passage": passage,
                "title": title,
                "list_question": []
            }

        # Tạo object question đúng format
        question_obj = {
            "id": question.id,
            "text": question.question_text,
            "options": {
                "A": question.option_a,
                "B": question.option_b,
                "C": question.option_c,
                "D": question.option_d,
            },
            "correct": question.correct_option,
            "explanation": question.explanation
        }

        # Push vào list_question
        if not any(q["id"] == question.id for q in grouped[lession_id][reading_id]["list_question"]):
            grouped[lession_id][reading_id]["list_question"].append(question_obj)

    return grouped

# history = get_reading_question_history_by_user_id(2)[:20]
# data = group_history_output(history)
# print(type(history))
# print(f"data sau khi chuan hoa: {data}")
# with open("history_log.txt", "w", encoding="utf-8") as f:
#     f.write(f"{history}")