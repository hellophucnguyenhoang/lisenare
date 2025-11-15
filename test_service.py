from sqlmodel import Session, create_engine
import app.services.study_sessions as study_session_services
import numpy as np

engine = create_engine("sqlite:///database.db")
with Session(engine) as session:
    o = study_session_services.update_event(session, 0, "view")
    
    for i in o:
        print(i)
