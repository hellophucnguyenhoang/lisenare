from sqlmodel import Session
from app.database import create_db_and_tables, get_session
from app.models import Topic, Reading, ObjectiveQuestion
from app.services import topics as topic_service
import pandas as pd
import ast
from app.services.readmepp import predict_cefr 
from typing import List, Optional, Callable, Tuple, Dict

cluster_names = {
    0: "Biography",
    1: "Arts",
    2: "Life",
    3: "History",
    4: "Travel",
    5: "Animals",
    6: "Education",
    7: "Society",
    8: "Sports",
    9: "Environment",
}

topic_to_cluster = {
    # Group 0
    "biography": 0, "personal qualities": 0, "person": 0, "object": 0,

    # Group 1
    "fashion": 1, "literature": 1, "art": 1, "music": 1, "arts": 1,
    "persion": 1, "book": 1, "folktales": 1, "archaeology": 1,

    # Group 2
    "life": 2, "health": 2, "personal experience": 2, "safety": 2,
    "growing up": 2, "survival": 2, "courage": 2, "job": 2,
    "attitude": 2, "friendship": 2, "friend": 2, "home": 2,
    "seasons": 2, "childhood": 2,

    # Group 3
    "history": 3, "social studies": 3, "psychology": 3, "politics": 3,

    # Group 4
    "transportation": 4, "travel": 4, "leisure": 4,
    "transport": 4, "shopping": 4,

    # Group 5
    "wildlife": 5, "animal": 5, "animals": 5, "food": 5, "objects": 5,

    # Group 6
    "education": 6, "business": 6, "personal development": 6,
    "communication": 6, "science": 6, "technology": 6,
    "language": 6, "challenges": 6,

    # Group 7
    "family": 7, "culture": 7, "society": 7, "behavior": 7,
    "behaviour": 7, "tradition": 7, "forgiveness": 7,
    "social gathering": 7, "socializing": 7,

    # Group 8
    "sports": 8, "sport": 8, "fantasy": 8, "entertainment": 8,
    "calls": 8, "school": 8, "hobbies": 8, "celebration": 8,

    # Group 9
    "natural disasters": 9, "nature": 9, "environment": 9,
    "human nature": 9, "resilience": 9, "natural": 9,
}


def clusterize(name: str) -> Tuple[Optional[int], Optional[str]]:
    key = str(name).lower().strip()
    cid = topic_to_cluster.get(key)
    if cid is None:
        print(f"CLUSTERIZE FAIL={name}")
        return None, None
    return cid, cluster_names[cid]

def parse_options_generic(raw) -> List[str]:
    """Convert string cell to list of options"""
    if pd.isna(raw):
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw]
    s = str(raw).strip()
    try:
        val = ast.literal_eval(s)
        if isinstance(val, (list, tuple)):
            return [str(x).strip() for x in val]
    except Exception:
        pass
    # fallback separators
    for sep in [";", "|", ","]:
        if sep in s:
            return [x.strip() for x in s.split(sep) if x.strip()]
    return [s]
    
def find_correct_option(true_answer, options):
    """Find the index (0-3) of the correct answer."""
    if pd.isna(true_answer):
        return 0
    ans = str(true_answer).strip().lower()
    for i, opt in enumerate(options):
        if ans in str(opt).lower() or str(opt).lower() in ans:
            return i
    return 0  # fallback

def create_data(data_file: str):
    # 0) read file once
    df = pd.read_excel(data_file)

    # 1) Phase 1 - ensure all canonical topics in the file exist in DB
    # collect canonical names from file (deduped)
    raw_topics = df["topic"].dropna().unique()
    canonical_names = set()
    raw_to_canonical = {}
    for raw in raw_topics:
        cid, canonical = clusterize(raw)
        if canonical:
            canonical_names.add(canonical)
            raw_to_canonical[raw] = canonical

    # Insert missing Topic rows (single transaction). Safe against duplicates.
    with next(get_session()) as session:
        # load existing names
        existing_topics = topic_service.get_all_topics(session)
        existing_names = {t.name for t in existing_topics}

        to_create = [Topic(name=n) for n in canonical_names if n not in existing_names]
        if to_create:
            session.add_all(to_create)
            session.commit()   # commit new topics
            
        # At this point DB contains all canonical topics we need.

    # 2) Phase 2 - build readings + questions using Topic objects from DB
    with next(get_session()) as session:
        # load all topics into dict name -> Topic (attached to this session)
        db_topics = {t.name: t for t in topic_service.get_all_topics(session)}

        readings_to_add: List[Reading] = []

        # iterate groups (title, passage, topic)
        for (title, passage, raw_topic), group in df.groupby(["title", "passage", "topic"], dropna=False):
            if not title or not passage or not raw_topic:
                continue

            # canonicalize topic and find DB Topic object
            canonical = raw_to_canonical.get(raw_topic)
            if canonical is None:
                print(f'NO canonical for topic: {raw_topic}')
                continue
            

            # compute difficulty
            combined_text = f"{str(passage)} {str(title)}"
            difficulty_val = predict_cefr(combined_text)
            difficulty = round(difficulty_val)

            topic_obj = db_topics.get(canonical)

            # create Reading object (link to topic object)
            reading = Reading(
                title=str(title).strip(),
                content_text=str(passage).strip(),
                difficulty=difficulty,
                num_questions=len(group),
                topic=topic_obj,
            )

            # build questions list
            questions = []
            for i, row in enumerate(group.itertuples(index=False)):

                options = parse_options_generic(row.option)
                correct_idx = find_correct_option(row.answer, options)

                q = ObjectiveQuestion(
                    question_text=str(row.question),
                    option_a=options[0] if len(options) > 0 else None,
                    option_b=options[1] if len(options) > 1 else None,
                    option_c=options[2] if len(options) > 2 else None,
                    option_d=options[3] if len(options) > 3 else None,
                    correct_option=correct_idx,
                    explanation=str(row.explanation) if not pd.isna(row.explanation) else None,
                    order_index=i,
                )
                questions.append(q)

            reading.questions = questions
            readings_to_add.append(reading)

        if readings_to_add:
            session.add_all(readings_to_add)
        session.commit()

    return {"topics_created": len(canonical_names), "readings": len(readings_to_add)}

def main():
    create_db_and_tables()
    file_names = [
        "static_data/All_Passages_Questions_unified.xlsx",
        "static_data/QA_Race_unified.xlsx",
        "static_data/ResultCambridge_unified.xlsx"
    ]
    for file_name in file_names:
        print(create_data(file_name))
        print(f'Done file {file_name}')

if __name__ == "__main__":  
    main()