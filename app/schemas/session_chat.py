from pydantic import BaseModel
from typing import Optional


class RuntimeSession:
    def __init__(self, list_question, topic, theta, history, current_question_id):
        self.list_question = list_question
        self.topic = topic
        self.theta = theta              # tĩnh: chỉ để bot biết trình độ học viên
        self.history = history
        self.current_question_id = str(current_question_id) if current_question_id is not None else None

        # order_id từ FE dùng làm key — lưu dạng str để khớp với LLM
        self._valid_ids = {str(q.order_id) for q in list_question if q.order_id is not None}

    def get_question_by_id(self, qid: str) -> Optional[dict]:
        for q in self.list_question:
            if q["id"] == qid:
                return q
        return None

    def set_current_question(self, qid: int) -> bool:
        """
        Set câu hỏi đang được thảo luận với học viên.
        - Trả về True nếu update thành công.
        - Trả về False nếu qid không hợp lệ — KHÔNG raise để LLM
          không bị crash REPL khi gọi nhầm.
        - qid=None → reset về trạng thái "không thảo luận câu nào".
        """
        if qid is None:
            self.current_question_id = None
            return True

        qid = str(qid)
        if qid not in self._valid_ids:
            return False

        self.current_question_id = qid
        return True


class RLMOutput(BaseModel):
    answer: str
    current_question_id: str | None  # có thể đã thay đổi sau turn

    
