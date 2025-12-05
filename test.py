import chromadb
from chromadb.utils import embedding_functions
from app.config import settings
from app.models import Topic
from app.database import engine
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
from app.services.generate_question import find_topic_id_by_topic
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-mpnet-base-v2")


ielts_topics = [
    "Work",
    "Health",
    "Technology",
    "Culture",
    "Media and Advertising",
    "Family and Relationships",
    "Science and Research",
    "Urbanization and City Life",
    "Crime and Law",
    "Globalization",
    "Language and Communication",
    "Arts, Music and Literature",
]

