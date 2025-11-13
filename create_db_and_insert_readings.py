from sqlmodel import Session
from app.database import create_db_and_tables, get_session
from app.models import Topic, Reading, ObjectiveQuestion
import pandas as pd
import ast
from ai_models.cefr_classifier.reading_level_classifier import classify_reading_with_length

# --- helper functions ---
def parse_options(raw):
    """Convert the 'Option' cell string to a list."""
    if pd.isna(raw):
        return []
    if isinstance(raw, list):
        return raw
    try:
        return [str(x).strip() for x in ast.literal_eval(str(raw))]
    except Exception:
        # fallback: split by comma
        return [x.strip().strip("'\"") for x in str(raw).strip("[]").split(",") if x.strip()]

def parse_options2(raw):
    """Convert the 'Option' cell string to a list."""
    return raw.split(";")
    
def find_correct_option(true_answer, options):
    """Find the index (0-3) of the correct answer."""
    if pd.isna(true_answer):
        return 0
    ans = str(true_answer).strip().lower()
    for i, opt in enumerate(options):
        if ans in str(opt).lower() or str(opt).lower() in ans:
            return i
    return 0  # fallback

def create_data1():
    with next(get_session()) as session:
        df = pd.read_excel("static_data/QA_Race.xlsx")
        # Pre-create topic objects (avoid duplicates)
        topic_map = {}
        for topic_name in df["Topic"].dropna().unique():
            topic_map[topic_name] = Topic(name=topic_name)

        readings_to_add = []
        for (title, article, topic_name), group in df.groupby(["Title", "article", "Topic"]):
            reading = Reading(
                title=str(title),
                content_text=str(article),
                difficulty=classify_reading_with_length(str(article) + " " + str(title)),
                num_questions=len(group),
                topic=topic_map.get(topic_name),
            )

            # Create all questions for this reading
            questions = []
            for i, row in enumerate(group.itertuples(index=False)):
                options = parse_options(row.Option)
                # while len(options) < 3:
                #     options.append("")
                # if len(options) > 4:
                #     options = options[:4]

                correct_idx = find_correct_option(row.True_answer, options)

                q = ObjectiveQuestion(
                    question_text=str(row.Question),
                    option_a=options[0],
                    option_b=options[1],
                    option_c=options[2],
                    option_d=options[3] if len(options) > 3 else None,
                    correct_option=correct_idx,
                    explanation=str(row.Explain) if not pd.isna(row.Explain) else None,
                    order_index=i,
                )
                questions.append(q)

            reading.questions = questions
            readings_to_add.append(reading)

        session.add_all(topic_map.values())
        session.add_all(readings_to_add)
        session.commit()
    
def create_data2():
    with next(get_session()) as session:
        df = pd.read_excel("static_data/All_Passages_Questions.xlsx")
        # Pre-create topic objects (avoid duplicates)
        topic_map = {}
        for topic_name in df["topic"].dropna().unique():
            topic_map[topic_name] = Topic(name=topic_name)

        readings_to_add = []
        for (title, article, topic_name), group in df.groupby(["title", "passage", "topic"]):
            reading = Reading(
                title=str(title),
                content_text=str(article),
                difficulty=classify_reading_with_length(str(article) + " " + str(title)),
                num_questions=len(group),
                topic=topic_map.get(topic_name),
            )

            # Create all questions for this reading
            questions = []
            for i, row in enumerate(group.itertuples(index=False)):

                options = parse_options2(row.option)

                correct_idx = find_correct_option(row.answer, options)

                q = ObjectiveQuestion(
                    question_text=str(row.Question),
                    option_a=options[0],
                    option_b=options[1],
                    option_c=options[2],
                    option_d=options[3] if len(options) > 3 else None,
                    correct_option=correct_idx,
                    explanation=str(row.explanation) if not pd.isna(row.explanation) else None,
                    order_index=i,
                )
                questions.append(q)

            reading.questions = questions
            readings_to_add.append(reading)

        session.add_all(topic_map.values())
        session.add_all(readings_to_add)
        session.commit()

  
def create_data2():
    with next(get_session()) as session:
        df = pd.read_excel("static_data/All_Passages_Questions.xlsx")
        # Pre-create topic objects (avoid duplicates)
        topic_map = {}
        for topic_name in df["topic"].dropna().unique():
            topic_map[topic_name] = Topic(name=topic_name)

        readings_to_add = []
        for (title, article, topic_name), group in df.groupby(["title", "passage", "topic"]):
            reading = Reading(
                title=str(title),
                content_text=str(article),
                difficulty=classify_reading_with_length(str(article) + " " + str(title)),
                num_questions=len(group),
                topic=topic_map.get(topic_name),
            )

            # Create all questions for this reading
            questions = []
            for i, row in enumerate(group.itertuples(index=False)):

                options = parse_options2(row.option)

                correct_idx = find_correct_option(row.answer, options)

                q = ObjectiveQuestion(
                    question_text=str(row.Question),
                    option_a=options[0],
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

        session.add_all(topic_map.values())
        session.add_all(readings_to_add)
        session.commit()


def create_data3():
    with next(get_session()) as session:
        df = pd.read_excel("static_data/ResultCambridge_with_topic.xlsx")
        # Pre-create topic objects (avoid duplicates)
        topic_map = {}
        for topic_name in df["topic"].dropna().unique():
            topic_map[topic_name] = Topic(name=topic_name)

        readings_to_add = []
        for (title, article, topic_name), group in df.groupby(["title", "passage", "topic"]):
            reading = Reading(
                title=str(title),
                content_text=str(article),
                difficulty=classify_reading_with_length(str(article) + " " + str(title)),
                num_questions=len(group),
                topic=topic_map.get(topic_name),
            )

            # Create all questions for this reading
            questions = []
            for i, row in enumerate(group.itertuples(index=False)):

                options = parse_options(row.option)

                correct_idx = find_correct_option(row.answer, options)

                q = ObjectiveQuestion(
                    question_text=str(row.question),
                    option_a=options[0],
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

        session.add_all(topic_map.values())
        session.add_all(readings_to_add)
        session.commit()



def main():
    create_db_and_tables()
    create_data1()
    create_data2()
    create_data3()

if __name__ == "__main__":  
    main()