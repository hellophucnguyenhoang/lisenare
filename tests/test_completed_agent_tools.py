import json
import os

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, text

from app.database import engine
from app.services.agent.tools.grammar_tool import get_topics_lesson
from app.services.agent.tools.history_tool import get_user_answer_history
from app.services.agent.tools.progress_tool import get_user_progress


DEFAULT_TEST_LEARNER_ID = 2


def print_tool_data(tool_name: str, data, capsys=None):
    output = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    message = f"\n\n===== {tool_name} =====\n{output}\n"

    if capsys is None:
        print(message)
        return

    with capsys.disabled():
        print(message, flush=True)


@pytest.fixture
def session():
    try:
        with Session(engine) as db_session:
            db_session.exec(text("SELECT 1"))
            yield db_session
    except SQLAlchemyError as exc:
        pytest.skip(f"Database is not available for agent tool tests: {exc}")


@pytest.fixture
def learner_id():
    return int(os.getenv("AGENT_TOOL_TEST_LEARNER_ID", DEFAULT_TEST_LEARNER_ID))


def test_get_user_progress_tool(session: Session, learner_id: int, capsys):
    result = get_user_progress(session, learner_id)
    print_tool_data("get_user_progress", result, capsys)

    assert result["ok"] is True
    assert result["tool"] == "get_user_progress"
    assert isinstance(result["summary"], str)
    assert "data" in result
    assert isinstance(result["data"]["theta_average"], (int, float))
    assert isinstance(result["data"]["theta_info"], list)
    assert isinstance(result["data"]["CEFR"], str)

    for item in result["data"]["theta_info"]:
        assert set(item) == {
            "theta_lesson",
            "lesson_name",
            "topic_name",
            "lesson_description",
            "topic_description",
        }


def test_get_user_answer_history_tool(
    session: Session, learner_id: int, capsys
):
    result = get_user_answer_history(session, learner_id)
    print_tool_data("get_user_answer_history", result, capsys)

    assert result["ok"] is True
    assert result["tool"] == "get_user_answer_history"
    assert isinstance(result["summary"], str)
    assert result["data"]["total_records"] == len(result["data"]["history"])
    assert 0.0 <= result["data"]["accuracy"] <= 1.0

    for item in result["data"]["history"]:
        assert set(item) == {
            "id",
            "timesecond",
            "question",
            "answer",
            "user_answer",
            "difficulty",
            "correct_answer",
        }


def test_get_topics_lesson_tool(session: Session, capsys):
    result = json.loads(get_topics_lesson(session))
    print_tool_data("get_topics_lesson", result, capsys)

    assert result["status"] in {"success", "empty"}
    assert isinstance(result["total_topics"], int)
    assert isinstance(result["total_lessons"], int)
    assert isinstance(result["topics"], list)
    assert result["total_topics"] == len(result["topics"])

    counted_lessons = 0
    for topic in result["topics"]:
        assert {"id", "name", "total_lessons", "lessons"} <= set(topic)
        assert isinstance(topic["lessons"], list)
        assert topic["total_lessons"] == len(topic["lessons"])
        counted_lessons += len(topic["lessons"])

    assert result["total_lessons"] == counted_lessons


def main():
    learner_id = int(
        os.getenv("AGENT_TOOL_TEST_LEARNER_ID", DEFAULT_TEST_LEARNER_ID)
    )
    with Session(engine) as session:
        outputs = {
            "get_user_progress": get_user_progress(session, learner_id),
            "get_user_answer_history": get_user_answer_history(
                session, learner_id
            ),
            "get_topics_lesson": json.loads(get_topics_lesson(session)),
        }
    print_tool_data("completed_agent_tools", outputs)


if __name__ == "__main__":
    main()
