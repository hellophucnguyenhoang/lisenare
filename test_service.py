from sqlmodel import Session, create_engine
from app.services.recommendation_states import get_latest_recommendation_state


engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    results = get_latest_recommendation_state(session, user_id=1, interacted_only=True)
    for r in results:
        print(r)