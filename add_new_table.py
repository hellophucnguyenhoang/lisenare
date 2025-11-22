from sqlmodel import Session, create_engine
from app.models import OTP, SQLModel

engine = create_engine("sqlite:///./database.db")
SQLModel.metadata.create_all(engine)