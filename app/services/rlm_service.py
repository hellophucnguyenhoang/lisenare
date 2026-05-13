import re

from .llm_service import call_llm
from .repl_env_service import REPLEnvironment
from .theta_learner_lesson_service import theta_to_level


# ============================================================
# LOGGER
# ============================================================
class RLMLogger:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.turn = 0
        self.iteration = 0

    def new_turn(self, question: str):
        self.turn += 1
        self.iteration = 0
        if self.verbose:
            print(f"\n{'=' * 60}")
            print(f"[TURN {self.turn}] User: {question}")
            print(f"{'=' * 60}")

    def log_llm_call(self, role: str, prompt: str, response: str):
        self.iteration += 1
        if self.verbose:
            print(f"\n{'─' * 40}")
            print(f"[LLM CALL #{self.iteration}] Role: {role}")
            print(f"── INPUT ({len(prompt)} chars) ──")
            print(prompt[:300] + "..." if len(prompt) > 300 else prompt)
            print(f"── OUTPUT ({len(response)} chars) ──")
            print(response[:500] + "..." if len(response) > 500 else response)
            print(f"{'─' * 40}")

    def log_repl(self, code: str, stdout: str):
        if self.verbose:
            print("\n[REPL EXECUTE]")
            print("── CODE ──")
            print(code[:300] + "..." if len(code) > 300 else code)
            print("── STDOUT ──")
            print(stdout[:300] + "..." if len(stdout) > 300 else stdout)

    def log_current_change(self, before, after):
        if self.verbose and before != after:
            print(f"\n[CURRENT_QUESTION] {before} → {after}")

    def log_final(self, answer: str, source: str):
        if self.verbose:
            print(f"\n[FINAL ANSWER] source={source}")
            print(f"  {answer[:200]}")


logger = RLMLogger(verbose=True)


# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = """
You are a friendly English tutor chatbot. You support both English and Vietnamese.
You answer student queries using an interactive REPL environment.

You are STRONGLY ENCOURAGED to delegate work to sub-LLMs via llm_query().
You will be queried iteratively until you call FINAL(answer).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REPL ENVIRONMENT — VARIABLES & FUNCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write Python code inside ```python ... ``` blocks.

READ-ONLY variables (do NOT redeclare):
  - context              : str       — full conversation history
  - list_question        : list[QuestionInput] with attrs id, order_id, question, type, answer, correct_answer, difficulty
  - current_question_id  : str | None — q.id (as string) of question being shown/discussed RIGHT NOW
  - theta                : float     — student ability level (STATIC; for adapting
                                       explanation difficulty, NOT updated by this system)
  - topic                : str       — current topic name

Functions:
  - llm_query(prompt) → str
        Call a sub-LLM. Use for grammar analysis, hints, explanations,
        and for generating the natural-language reply to the student.

  - set_current(qid)  → bool
        Tell the system which question is now being shown to the student.
        ALWAYS pass q.order_id as a string: set_current(str(q.order_id)).
        order_id is the display number on the frontend (1, 2, 3, ...).
        Returns True on success, False if qid is not in list_question.
        CALL THIS whenever you decide to show, switch to, or move on to
        a new question. Do NOT call it when the user is just chatting,
        greeting, or asking off-topic things.

  - FINAL(answer)     → None
        Set the final reply to the student. Call once when done.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT SESSION METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Topic                 : {topic}
  Student theta         : {theta} ({level})
  Total questions       : {total_questions}
  Available IDs         : {available_ids}
  Currently discussing  : {current_question_id}
  History length        : {context_length} chars
  History preview (tail): "{context_preview}"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO USE theta
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
theta is a static indicator of the student's level (range roughly -3 to 3):
  -3 to -1.5 : Beginner          → giải thích thật chậm, nhiều ví dụ cơ bản
  -1.5 to -0.5 : Elementary      → ngữ pháp đơn giản, từ vựng quen thuộc
  -0.5 to 0.5  : Intermediate    → có thể dùng thuật ngữ ngữ pháp
   0.5 to 1.5  : Upper-Inter.    → ví dụ phức tạp hơn, ít cầm tay chỉ việc
   1.5 to 3    : Advanced        → giải thích ngắn gọn, thử thách
Adjust hint depth, vocabulary, and example complexity accordingly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TYPICAL PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Pattern 1 — Student asks about a specific question (e.g. "câu 4 làm sao"):
```python
q = next((q for q in list_question if q.order_id == 4), None)
hint = llm_query(
    f"Bạn là gia sư tiếng Anh. Đưa ra gợi ý kiểu Socratic cho câu hỏi {{topic}} "
    f"sau, KHÔNG tiết lộ đáp án. Trình độ học viên theta={{theta}} "
    f"(điều chỉnh độ khó giải thích cho phù hợp).\\n"
    f"Câu hỏi: {{q.question}}\\nĐáp án đúng: {{q.correct_answer}}\\n\\n"
    f"YÊU CẦU NGÔN NGỮ: Trả lời hoàn toàn bằng tiếng Việt. Chỉ dùng tiếng "
    f"Anh cho nội dung câu hỏi gốc và thuật ngữ ngữ pháp trong ngoặc. "
    f"Không viết song ngữ, không dịch lại sang tiếng Anh."
)
set_current(str(q.order_id))
FINAL(hint)
```

# Pattern 2 — Student asks for the NEXT question:
```python
order_ids = [str(q.order_id) for q in list_question]
if current_question_id is None:
    next_q = list_question[0]
else:
    idx = order_ids.index(current_question_id)
    next_q = list_question[idx + 1] if idx + 1 < len(list_question) else None

if next_q is None:
    FINAL("Bạn đã làm hết các câu rồi! 🎉")
else:
    hint = llm_query(
        f"Bạn là gia sư tiếng Anh. Giới thiệu câu hỏi {{topic}} sau cho "
        f"học viên (trình độ theta={{theta}}) và đưa gợi ý ngắn (không "
        f"tiết lộ đáp án).\\n"
        f"Câu hỏi: {{next_q.question}}\\n\\n"
        f"YÊU CẦU NGÔN NGỮ: Trả lời hoàn toàn bằng tiếng Việt. Giữ nguyên "
        f"câu hỏi tiếng Anh khi trích dẫn. Thuật ngữ ngữ pháp đặt trong "
        f"ngoặc, ví dụ: thì hiện tại tiếp diễn (Present Continuous). "
        f"Không viết song ngữ, không dịch lại lời giải thích."
    )
    set_current(str(next_q.order_id))
    FINAL(hint)
```

# Pattern 3 — Student is chatting / greeting / off-topic:
```python
# Do NOT call set_current — current_question_id should not change.
reply = llm_query(
    f"Học viên vừa nói: '...'. Hãy phản hồi thân thiện rồi nhẹ nhàng "
    f"đưa cuộc trò chuyện quay lại bài học về {{topic}}. Câu đang thảo "
    f"luận có id: {{current_question_id}}.\\n\\n"
    f"YÊU CẦU NGÔN NGỮ: Trả lời hoàn toàn bằng tiếng Việt. Không chào "
    f"hai lần bằng hai ngôn ngữ. Không dịch lại sang tiếng Anh."
)
FINAL(reply)
```

# Pattern 4 — Student submits an answer (just give feedback, no scoring):
```python
q = next((q for q in list_question if str(q.order_id) == current_question_id), None)
feedback = llm_query(
    f"Câu hỏi: {{q.question}}\\nĐáp án đúng: {{q.correct_answer}}\\n"
    f"Học viên trả lời: <their answer>\\n"
    f"Trình độ học viên theta={{theta}}.\\n"
    f"Hãy đưa phản hồi: nói rõ đúng/sai, giải thích lý do, đưa đáp án "
    f"đúng nếu sai. Trả lời hoàn toàn bằng tiếng Việt; chỉ tiếng Anh cho "
    f"câu hỏi gốc, đáp án mẫu, và thuật ngữ ngữ pháp trong ngoặc."
)
FINAL(feedback)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. NEVER hallucinate question content — always read from list_question.
2. NEVER reassign protected variables (list_question, context, theta, topic,
   current_question_id). Any such assignment is silently discarded.
3. To change which question is being discussed, you MUST call set_current(qid).
   Reassigning current_question_id in code does NOTHING.
4. Do NOT call set_current() when:
     - the user is just greeting / chatting / asking their own name
     - the user asks a general grammar question not tied to a specific item
   In those cases, leave current_question_id unchanged.
5. "câu tiếp theo" / "next question" means the question AFTER
   current_question_id in list_question order — NOT "first unanswered".
6. Always use llm_query() for grammar evaluation and hint generation —
   never guess in your own voice.
7. Use theta to ADAPT explanation depth, vocabulary, and example complexity.
   theta is STATIC — do not try to update it.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LANGUAGE POLICY (STRICT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The reply to the student MUST be in Vietnamese. English is allowed ONLY for:
  - the original question text being shown (verbatim from list_question)
  - the correct/sample answer being shown
  - English grammar terms in parentheses, e.g. "thì hiện tại tiếp diễn (Present Continuous)"
  - short inline examples like "He is running."

DO NOT:
  - write the same sentence twice in two languages (no "Chào bạn! Hello!")
  - translate your own Vietnamese explanations into English
  - mix two full languages line-by-line

When you call llm_query() to generate the student-facing reply, ALWAYS
include this instruction in the sub-prompt:
  "Trả lời hoàn toàn bằng tiếng Việt. Chỉ dùng tiếng Anh cho nội dung câu
   hỏi gốc, đáp án mẫu, hoặc thuật ngữ ngữ pháp trong ngoặc. Không viết
   song ngữ, không dịch lại câu giải thích sang tiếng Anh."
"""


# ============================================================
# ACTION PROMPTS
# ============================================================
FIRST_ACTION_PROMPT = """Think step-by-step on what to do to answer: "{question}"

You have NOT interacted with the REPL yet.
Your FIRST action: write Python code to READ data from REPL variables
(list_question, current_question_id, ...) and use llm_query() to analyse
or generate content. If appropriate, call set_current(qid) and FINAL(answer)
inside the same code block.

Do NOT answer in plain text yet — explore data first."""

CONTINUE_ACTION_PROMPT = """The history above shows your previous REPL interactions.

Continue to answer: "{question}"

Use llm_query() for any natural-language generation, set_current(qid) when
switching the active question, and FINAL(answer) when done."""

FINAL_ACTION_PROMPT = """Based on all information gathered, provide a final answer now.
If you haven't called FINAL() yet, do so. Otherwise write your reply directly."""


# ============================================================
# HELPERS
# ============================================================
def extract_code(text: str):
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None


def is_complete_answer(text: str) -> bool:
    has_no_code = "```python" not in text
    has_no_final = "FINAL(" not in text
    is_substantial = len(text.strip()) > 50
    return has_no_code and has_no_final and is_substantial


def _build_action_prompt(
    question: str, iteration: int, max_iterations: int
) -> str:
    if iteration >= max_iterations - 1:
        return FINAL_ACTION_PROMPT
    elif iteration == 0:
        return FIRST_ACTION_PROMPT.format(question=question)
    else:
        return CONTINUE_ACTION_PROMPT.format(question=question)


def _logged_llm_query(prompt: str) -> str:
    response = call_llm(prompt)
    logger.log_llm_call("sub-LLM", prompt, response)
    return response


# ============================================================
# RUN RLM
# ============================================================
def run_rlm(question: str, session) -> str:
    logger.new_turn(question)
    env = REPLEnvironment(session)
    meta = env.get_metadata()

    system_prompt = SYSTEM_PROMPT.format(
        topic=meta["topic"],
        theta=meta["theta"],
        level=theta_to_level(meta["theta"]),
        total_questions=meta["total_questions"],
        available_ids=meta["available_ids"],
        current_question_id=meta["current_question_id"],
        context_length=meta["context_length"],
        context_preview=meta["context_preview"],
    )

    hist = [system_prompt]
    max_iterations = 7

    cqid_before_turn = session.current_question_id

    for i in range(max_iterations):
        env.refresh()

        action_prompt = _build_action_prompt(question, i, max_iterations)
        hist.append(action_prompt)

        full_prompt = "\n\n".join(hist)
        response = call_llm(full_prompt)
        logger.log_llm_call("root", full_prompt, response)
        hist.append(response)

        # ---- Ưu tiên 1: có code → exec (set_current/FINAL nằm trong đây) ----
        code = extract_code(response)
        if code:
            stdout = env.execute(code, _logged_llm_query)
            logger.log_repl(code, stdout)
            hist.append(f"[REPL OUTPUT]:\n{stdout}")
            if env.final_answer:
                logger.log_current_change(
                    cqid_before_turn, session.current_question_id
                )
                logger.log_final(env.final_answer, "REPL.FINAL()")
                return env.final_answer
            continue

        # ---- Ưu tiên 2: FINAL() đã set từ vòng trước ----
        if env.final_answer:
            logger.log_current_change(
                cqid_before_turn, session.current_question_id
            )
            logger.log_final(env.final_answer, "REPL.FINAL()")
            return env.final_answer

        # ---- Ưu tiên 3: FINAL("...") trong text (fallback) ----
        final_match = re.search(r'FINAL\("(.+?)"\)', response, re.DOTALL)
        if final_match:
            final_text = final_match.group(1)
            logger.log_current_change(
                cqid_before_turn, session.current_question_id
            )
            logger.log_final(final_text, "text.FINAL()")
            return final_text

        # ---- Ưu tiên 4: trả lời text trực tiếp ----
        if is_complete_answer(response):
            logger.log_current_change(
                cqid_before_turn, session.current_question_id
            )
            logger.log_final(response, "direct_answer")
            return response

    result = env.final_answer or response
    logger.log_current_change(cqid_before_turn, session.current_question_id)
    logger.log_final(result, "fallback")
    return result
