# seed_data.py
from datetime import datetime, timezone
from app.database import get_session, create_db_and_tables
from app.services import users as user_service
from app.services import topics as topic_service
from app.services import readings as reading_service
from app.models import User, Reading, ObjectiveQuestion
from app.schemas import UserCreate, ReadingCreate, ObjectiveQuestionCreate

TOPIC_LIST = [
    "environment", "technology", "education", "health", "culture",
    "science", "sports", "travel", "business", "society",
]

USER_LIST = [
    {"username": "alice", "password": "alice123", "email": "alice@example.com"},
    {"username": "bob", "password": "bob123", "email": "bob@example.com"},
    {"username": "charlie", "password": "charlie123", "email": "charlie@example.com"},
]

READING_LIST = [
    {"title": "The Importance of Clean Air", "content_text": "Air pollution affects health...", "difficulty": 2, "estimated_time": 5},
    {"title": "Advances in AI Technology", "content_text": "AI is transforming industries...", "difficulty": 3, "estimated_time": 7},
    {"title": "Education in the 21st Century", "content_text": "Modern education focuses on...", "difficulty": 1, "estimated_time": 6},
    {"title": "Healthy Living Tips", "content_text": "Eat well, exercise regularly...", "difficulty": 1, "estimated_time": 4},
    {"title": "Cultural Heritage Around the World", "content_text": "Every country has unique traditions...", "difficulty": 2, "estimated_time": 5},
]

# Sample questions per reading
SAMPLE_QUESTIONS = [
    {
        "question_text": "What is the main topic?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_option": 0,
        "explanation": "The first option is correct."
    },
    {
        "question_text": "Why is it important?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_option": 1,
        "explanation": "The second option is correct."
    },
    {
        "question_text": "Which statement is true?",
        "options": ["Option A", "Option B", "Option C", "Option D"],
        "correct_option": 2,
        "explanation": "The third option is correct."
    },
]

def seed_topics(session):
    return [topic_service.create_topic(session, name) for name in TOPIC_LIST]

def seed_users(session):
    users = []
    for u in USER_LIST:
        user_create = UserCreate(username=u["username"], password=u["password"], email=u["email"])
        users.append(user_service.create_user(session, user_create))
    return users

def seed_readings(session, topics):
    readings = []
    for i, data in enumerate(READING_LIST):
        topic = topics[i % len(topics)]

        reading_create = ReadingCreate(
            topic_id=topic.id, 
            title=data["title"], 
            content_text=data["content_text"],
            difficulty=data["difficulty"],
            estimated_time=data["estimated_time"])
        
        reading = reading_service.create_reading(
            session,
            reading_create
        )
        readings.append(reading)
        seed_questions(session, reading)
    return readings

def seed_questions(session, reading):
    for q in SAMPLE_QUESTIONS:
        question_create = ObjectiveQuestionCreate(
            reading_id=reading.id,
            question_text=q["question_text"],
            option_a=q["options"][0],
            option_b=q["options"][1],
            option_c=q["options"][2],
            option_d=q["options"][3],
            correct_option=q["correct_option"],
            explanation=q["explanation"]
        )
        reading_service.add_objective_question(
            session,
            question_create
        )

