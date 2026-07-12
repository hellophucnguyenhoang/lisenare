import threading

from sqlmodel import Session, func, select

from app.database import HistoryAnswerQuestion, engine
from app.services import memory_service
from app.services.agent.tools.wrong_answers_tool import (
    _collect_wrong_records,
    _llm_analyze_chunk,
)
from app.services.history_answer_question_service import get_filtered_history


def trigger_analysis_if_milestone(learner_id: int) -> None:
    try:
        with Session(engine) as session:
            count = session.exec(
                select(func.count()).where(
                    HistoryAnswerQuestion.learner_id == learner_id
                )
            ).one()
            if count > 0 and count % 100 == 0:
                threading.Thread(
                    target=run_wrong_answer_analysis,
                    args=(learner_id,),
                    daemon=True,
                ).start()
    except Exception as exc:
        print(f"[wrong_analysis] trigger check failed learner={learner_id}: {exc}")


def run_wrong_answer_analysis(learner_id: int, limit: int = 15, chunk_size: int = 8) -> None:
    try:
        with Session(engine) as session:
            rows = get_filtered_history(session, learner_id, limit=200)
            _, wrong_by_qid = _collect_wrong_records(rows)
            if not wrong_by_qid:
                return

            candidates = list(wrong_by_qid.values())[:limit]

            pending = []
            for c in candidates:
                if memory_service.has_mistake_for_question(session, learner_id, c["question_id"]):
                    continue
                pending.append(c)

            if not pending:
                return

            for i in range(0, len(pending), chunk_size):
                chunk = pending[i: i + chunk_size]
                chunk_results = _llm_analyze_chunk(chunk)

                for c, r in zip(chunk, chunk_results):
                    if r.get("failed"):
                        continue
                    try:
                        content = (
                            f"[qid:{c['question_id']}] "
                            f"Q: {c['question']}\n"
                            f"Learner: {c['last_user_answer']}\n"
                            f"Explain: {r.get('explanation') or ''}"
                        )
                        memory_service.add_mistake(
                            session,
                            learner_id=learner_id,
                            mistake_type=r["mistake_type"],
                            content=content,
                            grammar_point=r.get("grammar_point"),
                            suggested_fix=r.get("suggested_fix"),
                        )
                    except Exception as exc:
                        print(f"[wrong_analysis] save memory failed qid={c['question_id']}: {exc}")

            print(f"[wrong_analysis] done learner={learner_id}, analyzed {len(pending)} questions")
    except Exception as exc:
        print(f"[wrong_analysis] run failed learner={learner_id}: {exc}")
