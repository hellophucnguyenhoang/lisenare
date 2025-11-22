from sqlmodel import Session, create_engine
from app.services import readings as reading_service
from app.services import users as user_service
from app.services import study_sessions as study_session_services
from app.config import settings
import numpy as np
from reading_env import Reader
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------
# Chuẩn bị environment
# ------------------------
def reading_vector(reading):
    return np.frombuffer(reading.reading_embedding.vector_blob, dtype=np.float32).copy()

# Kết nối database
engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    user_recent_history = study_session_services.get_user_recent_history(session, user_id=1)
    for h in user_recent_history:
        print(h)
        print()
