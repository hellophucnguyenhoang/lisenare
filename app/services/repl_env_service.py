import io
import contextlib

class REPLEnvironment:
    def __init__(self, session):
        self.session = session
        self.variables = {}
        self.final_answer = None

        self._env_data = {
            # Conversation history dạng string — LLM truy cập qua biến `context`
            "context": self._history_to_string(session.history),

            # Data thật của session — LLM truy cập qua biến tương ứng
            "list_question":    session.list_question,
            "detected_answers": session.detected_answers,
            "topic":            session.topic,
            "theta":            session.theta,
        }

    def get_metadata(self) -> dict:
        """
        Trả về metadata ngắn gọn để nhúng vào system prompt.
        LLM chỉ được biết những thông tin này — không phải data thật.
        """
        ctx = self._env_data["context"]
        answered_ids = [a["question_id"] for a in self._env_data["detected_answers"]]
        q_ids = [q["id"] for q in self._env_data["list_question"]]

        return {
            "topic":               self._env_data["topic"],
            "theta":               round(self._env_data["theta"], 3),
            "total_questions":     len(self._env_data["list_question"]),
            "available_ids":       q_ids,
            "answered_ids":        answered_ids,
            "context_length":      len(ctx),
            "context_preview":     ctx[:150],
        }

    def _history_to_string(self, history: list) -> str:
        if not history:
            return "[No conversation history yet]"
        lines = []
        for turn in history:
            lines.append(f"[{turn['role'].upper()}]: {turn['content']}")
        return "\n".join(lines)

    def _set_final(self, answer: str):
        self.final_answer = answer

    def refresh(self):
        """
        Gọi sau mỗi lần session.theta hoặc detected_answers thay đổi,
        để REPL luôn có data mới nhất.
        """
        self._env_data["theta"]            = self.session.theta
        self._env_data["detected_answers"] = self.session.detected_answers
        self._env_data["context"]          = self._history_to_string(self.session.history)

    def execute(self, code: str, llm_fn) -> str:
        """
        Thực thi code trong REPL namespace.

        Namespace gồm:
          - Toàn bộ _env_data (list_question, theta, ...) — data thật
          - llm_query: để LLM gọi sub-LLM từ trong code
          - FINAL: để LLM set câu trả lời cuối
          - Các biến đã tạo ở lượt exec trước (self.variables)
        """
        # Các biến protected — LLM không được ghi đè
        protected_keys = set(self._env_data.keys())

        namespace = {
            **self._env_data,          # data thật từ REPL
            **self.variables,          # biến đã tạo ở lượt trước
            "llm_query": llm_fn,
            "FINAL":     self._set_final,
        }

        stdout_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, namespace)

            # Lưu biến MỚI mà LLM tạo ra trong code
            # Không cho phép ghi đè các biến protected
            for k, v in namespace.items():
                if (
                    not k.startswith("_")
                    and k not in protected_keys
                    and k not in ("llm_query", "FINAL")
                ):
                    self.variables[k] = v

            # Restore lại các biến protected (đề phòng LLM cố tình ghi đè)
            for k, v in self._env_data.items():
                namespace[k] = v

        except Exception as e:
            return f"[REPL ERROR]: {e}"

        return stdout_capture.getvalue()