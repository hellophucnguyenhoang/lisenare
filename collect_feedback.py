from redis_client import r
import time, math, json, redis
from collections import defaultdict
from app.models import FeedBack, ObjectiveQuestion
from sqlmodel import Session, select, func
from app.database import engine
import subprocess

session_buffer = defaultdict(list)
FEEDBACK_BATCH_SIZE = 1000
feedback_counter = 0        
def save_session_to_db(username, reading_text, question_text, session_events):
    global feedback_counter
    print(">>> SAVING SESSION TO DB")
    print("User:", username)
    print("reading text:", reading_text)
    print("Question:", question_text)
    correct_option = find_corect_option(question_text)
    score = calculate_r2_from_events(session_events, correct_option)
    print("Score la:", score)
    print("Events:", session_events)
    print("-------------------------")
    new_feed_back = FeedBack(
        user_name=username,
        reading_text=reading_text,
        question_text=question_text,
        score=score
    )
    save_feedback(new_feed_back)
    feedback_counter += 1
    print(f"Total new feedback count: {feedback_counter}")

    # ✅ Trigger retrain khi đủ batch
    if feedback_counter >= FEEDBACK_BATCH_SIZE:
        feedback_counter = 0  # reset counter
        print(">>> Bắt đầu retrain PPO model vì đủ 1000 feedback")
        subprocess.Popen(["python", "retrain.py"])

def find_corect_option(question: str):
    with Session(engine) as session:
        statement = select(ObjectiveQuestion.correct_option).where(ObjectiveQuestion.question_text == question)
        result = session.exec(statement).first()  # lấy 1 kết quả
        if result is None:
            return None  
        option_map = {0: "A", 1: "B", 2: "C", 3: "D"}
        return option_map.get(result)
def save_feedback(feedback: FeedBack):
    with Session(engine) as session:
        try:
            session.add(feedback)
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
def worker_loop(batch_size=1000):
    print("van dang chay nha cu")
    events = []
    for _ in range(batch_size):
        raw = r.lpop("event_queue")
        if not raw:
            break
        events.append(json.loads(raw))

    if not events:
        return  # không có event → thoát
    for ev in events:
        username = ev["username"]
        reading_text = ev.get("reading_text")
        question_text = ev.get("question_text")
        event_type = ev["event_type"]
        key = (username, reading_text, question_text)
        session_buffer[key].append(ev)
        if event_type == "time_spent_on_question":
            session_events = session_buffer[key]
            save_session_to_db(username, reading_text, question_text, session_events)
            del session_buffer[key]
def calculate_r2_from_events(events, correct_option):
    # Sắp xếp theo timestamp
    events = sorted(events, key=lambda e: e.get('metadata', {}).get('timestamp', 0))

    r2 = 0.0
    last_hover_option = None
    hover_streak = 0
    selected_option = None
    time_spent = 0
    like_count = 0
    dislike_count = 0
    view_count = 0

    for e in events:
        event_type = e.get('event_type', '')
        meta = e.get('metadata', {})

        if event_type == 'option_hover':
            option = meta.get('option')
            if option == last_hover_option:
                hover_streak += 1
            else:
                hover_streak = 1
                last_hover_option = option
            # Hover liên tục ít thì +0.01, nhiều thì -0.05, max trừ -0.2
            r2 += min(max(-0.05 * hover_streak + 0.01, -0.2), 0.05)

        elif event_type == 'option_selected':
            selected_option = meta.get('option')

        elif event_type == 'time_spent_on_question':
            duration_ms = meta.get('duration_ms', 0)
            time_spent = duration_ms / 1000  # đổi sang giây

        elif event_type == 'question_view':
            view_count += 1

        elif event_type == 'like':
            like_count += 1

        elif event_type == 'dislike':
            dislike_count += 1

    # Điểm dựa trên lựa chọn cuối cùng
    if selected_option:
        r2 += 0.5 if selected_option == correct_option else -0.5

    # Time spent
    if 10 <= time_spent <= 60:
        r2 += 0.2
    elif time_spent > 120:
        r2 -= 0.1

    # Views
    r2 += min(view_count, 4) * 0.05

    # Like / Dislike
    r2 += min(like_count, 1) * 0.3
    r2 -= min(dislike_count, 1) * 0.3  # trừ nếu dislike

    # Clamp về [-1,1]
    r2 = math.tanh(r2)
    return r2

while True:
    worker_loop()
    time.sleep(0.5)  # tránh tốn CPU
