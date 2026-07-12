from app.config import settings
from app.services.rlm.core import run_rlm as _run_rlm_engine


def run_rlm(question: str, session) -> str:
    """Chạy RLM engine (app/services/rlm) cho một lượt chat tutoring.

    Mutating side effect: engine có thể gọi session.set_current_question(qid) bên
    trong, nên session.current_question_id có thể đã đổi sau khi hàm này trả về.
    """
    return _run_rlm_engine(question, session, depth=settings.rlm_default_depth)
