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
from redis_client import r
from app.services.generate_question import find_user_by_user_name, find_nearest_passage, encode_with_overlap, load_reading_embeddings_as_matrix, find_reading_id_by_embedding

def find_reading_by_user_id(user_id: int):
    try:
        with Session(engine) as session:
            statement = select(ParagraphAuthor.passage_text).where(ParagraphAuthor.user_id == user_id)
            list_reading = session.exec(statement).all()
            list_reading_id = [find_reading_id_by_embedding(encode_with_overlap(reading)) for reading in list_reading]
            return list_reading_id
    except Exception as e:
        raise e
    

def find_reading_question(list_reading_id: list):
    with Session(engine) as session:
        statement = (select(Reading.title, Reading.content_text, ObjectiveQuestion)
                    .join(ObjectiveQuestion, ObjectiveQuestion.reading_id == Reading.id)
                    .where(Reading.id.in_(list_reading_id)))
        result = session.exec(statement).all()
        return result
    
def format_reading_data(raw_data):
    formatted = {}
    for title, passage, q in raw_data:
        rid = q.reading_id
        if rid not in formatted:
            formatted[rid] = {
                "title": title,
                "passage": passage,
                "list_question": []
            }
        formatted[rid]["list_question"].append({
            "id": q.id,
            "text": q.question_text,
            "options": {
                "A": q.option_a,
                "B": q.option_b,
                "C": q.option_c,
                "D": q.option_d,
            },
            "correct": q.correct_option,
            "explanation": q.explanation
        })
    return list(formatted.values())

