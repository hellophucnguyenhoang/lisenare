import contextlib
import io


class REPLEnvironment:
    def __init__(self, session):
        self.session = session
        self.variables = {}
        self.final_answer = None

        self._env_data = {
            # Conversation history dạng string — LLM truy cập qua biến `context`
            "context": self._history_to_string(session.history),
            # Data thật của session — LLM truy cập qua biến tương ứng
            "list_question": session.list_question,
            "topic": session.topic,
            "theta": session.theta,  # tĩnh
            "current_question_id": session.current_question_id,
        }

    # ----- metadata cho system prompt -----
    def get_metadata(self) -> dict:
        ctx = self._env_data["context"]
        q_ids = [q.id for q in self._env_data["list_question"]]

        if len(ctx) > 500:
            context_preview = "..." + ctx[-500:]
        else:
            context_preview = ctx

        return {
            "topic": self._env_data["topic"],
            "theta": round(self._env_data["theta"], 3),
            "total_questions": len(self._env_data["list_question"]),
            "available_ids": q_ids,
            "context_length": len(ctx),
            "context_preview": context_preview,
            "current_question_id": self._env_data["current_question_id"],
        }

    def _history_to_string(self, history: list) -> str:
        if not history:
            return "[No conversation history yet]"
        lines = []
        for turn in history:
            lines.append(f"[{turn.role.upper()}]: {turn.content}")
        return "\n".join(lines)

    # ----- side-effect functions exposed to LLM -----
    def _set_final(self, answer: str):
        self.final_answer = answer

    def _set_current(self, qid):
        """
        LLM gọi set_current(qid) để báo: "tôi đang thảo luận câu này với học viên".
        - Validate qua session.set_current_question.
        - Trả về bool để LLM có thể kiểm tra.
        - Cập nhật _env_data để các iteration sau trong cùng turn thấy ngay.
        """
        ok = self.session.set_current_question(qid)
        if ok:
            self._env_data["current_question_id"] = (
                self.session.current_question_id
            )
        return ok

    # ----- refresh giữa các turn -----
    def refresh(self):
        """Đồng bộ data từ session vào REPL (gọi đầu mỗi iteration)."""
        self._env_data["context"] = self._history_to_string(
            self.session.history
        )
        self._env_data["current_question_id"] = (
            self.session.current_question_id
        )
        # theta tĩnh, list_question và topic không đổi → không cần refresh

    # ----- thực thi code -----
    def execute(self, code: str, llm_fn) -> str:
        """
        Thực thi code trong REPL namespace.

        Namespace gồm:
          - Toàn bộ _env_data (read-only đối với LLM)
          - llm_query(prompt) → gọi sub-LLM
          - FINAL(answer)     → set câu trả lời cuối
          - set_current(qid)  → báo system biết đang thảo luận câu nào
          - Các biến đã tạo ở lượt exec trước (self.variables)
        """
        protected_keys = set(self._env_data.keys())
        reserved_funcs = {"llm_query", "FINAL", "set_current"}

        namespace = {
            **self._env_data,
            **self.variables,
            "llm_query": llm_fn,
            "FINAL": self._set_final,
            "set_current": self._set_current,
        }

        stdout_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, namespace)

            # Lưu biến mới mà LLM tạo ra; không cho ghi đè biến/function bảo vệ
            for k, v in namespace.items():
                if (
                    not k.startswith("_")
                    and k not in protected_keys
                    and k not in reserved_funcs
                ):
                    self.variables[k] = v

            # Restore biến bảo vệ (đề phòng LLM cố tình gán đè)
            for k, v in self._env_data.items():
                namespace[k] = v

        except Exception as e:
            return f"[REPL ERROR]: {e}"

        return stdout_capture.getvalue()
