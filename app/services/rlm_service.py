from repl_env import REPLEnvironment
from llm import call_llm
from theta_learner_lesson_service import computeP, theta_to_level
import re
import json


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
            print(f"\n{'='*60}")
            print(f"[TURN {self.turn}] User: {question}")
            print(f"{'='*60}")

    def log_llm_call(self, role: str, prompt: str, response: str):
        self.iteration += 1
        if self.verbose:
            print(f"\n{'─'*40}")
            print(f"[LLM CALL #{self.iteration}] Role: {role}")
            print(f"── INPUT ({len(prompt)} chars) ──")
            print(prompt[:300] + "..." if len(prompt) > 300 else prompt)
            print(f"── OUTPUT ({len(response)} chars) ──")
            print(response[:500] + "..." if len(response) > 500 else response)
            print(f"{'─'*40}")

    def log_repl(self, code: str, stdout: str):
        if self.verbose:
            print(f"\n[REPL EXECUTE]")
            print(f"── CODE ──")
            print(code[:300] + "..." if len(code) > 300 else code)
            print(f"── STDOUT ──")
            print(stdout[:300] + "..." if len(stdout) > 300 else stdout)

    def log_irt(self, qid, is_correct, prob, theta_before, theta_after):
        if self.verbose:
            print(f"\n[IRT UPDATE]")
            print(f"  Q{qid} | correct={is_correct} | "
                  f"P={prob:.2f} | "
                  f"theta: {theta_before:.3f} → {theta_after:.3f}")

    def log_final(self, answer: str, source: str):
        if self.verbose:
            print(f"\n[FINAL ANSWER] source={source}")
            print(f"  {answer[:200]}")


logger = RLMLogger(verbose=True)


# ============================================================
# SYSTEM PROMPT — CHỈ CHỨA METADATA, KHÔNG CÓ DATA THẬT
#   System prompt chỉ chứa metadata ngắn:
#     - Có bao nhiêu câu hỏi
#     - ID nào có sẵn
#     - Theta hiện tại là bao nhiêu
#     - ...
#   Data thật (list_question, detected_answers) sống trong REPL.
#   LLM muốn biết nội dung câu hỏi → phải viết code để đọc.
# ============================================================
SYSTEM_PROMPT = """
You are a friendly English tutor chatbot. You support both English and Vietnamese.
You are tasked with answering student queries using an interactive REPL environment.

You can access, transform, and analyze data interactively in a REPL environment
that can recursively query sub-LLMs, which you are STRONGLY ENCOURAGED to use
as much as possible. You will be queried iteratively until you provide a final answer.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REPL ENVIRONMENT — AVAILABLE VARIABLES & TOOLS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Write Python code inside ```python ... ``` blocks.

Variables available in REPL (access by writing code — NOT pre-loaded in this prompt):
  - context          : full conversation history as string
  - list_question    : list[dict] with keys: id, question, type, answer, correct_answer, difficulty
  - detected_answers : list[dict] of already answered questions
  - theta            : float — current student ability
  - topic            : str — current topic name

Functions:
  - llm_query(prompt) → str : call a sub-LLM. Use for grammar analysis, hints, explanations.
  - FINAL(answer)           : set the final answer to return to user. Call when done.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CURRENT SESSION METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[These are metadata only — to access full data, write code to read REPL variables]

  Topic            : {topic}
  Student theta    : {theta} ({level})
  Total questions  : {total_questions}
  Available IDs    : {available_ids}
  Already answered : {answered_ids}
  History length   : {context_length} chars
  History preview  : "{context_preview}..."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ACCESS DATA (examples)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Peek at a specific question:
```python
q = next((q for q in list_question if q["id"] == "2"), None)
print(q)
```

# Find questions not yet answered:
```python
answered = [a["question_id"] for a in detected_answers]
remaining = [q for q in list_question if q["id"] not in answered]
print(f"Remaining: {{len(remaining)}}")
```

# Evaluate a student answer using sub-LLM:
```python
q = next((q for q in list_question if q["id"] == "1"), None)
analysis = llm_query(
    f"Question: {{q['question']}}\\n"
    f"Correct answer: {{q['correct_answer']}}\\n"
    f"Student answered: is running\\n"
    f"Is this correct? Explain briefly."
)
response = llm_query(
    f"Based on: {{analysis}}\\n"
    f"Generate a friendly tutor reply for student at theta={{theta}}."
)
FINAL(response)
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. NEVER hallucinate question content — always read from list_question via code
2. NEVER redeclare list_question, detected_answers, context, theta, topic in code
3. To find next question, always compute from list_question in code
4. If question ID not in the Available IDs list above → say so politely
5. Always use llm_query() for grammar evaluation — never guess

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASSIFY USER MESSAGE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CASE A — Related to list_question (MUST use REPL + llm_query):
  A1: First-time answer → evaluate via llm_query → DETECTED_JSON
  A2: Re-answering     → check retry_count → hints or evaluate → DETECTED_JSON
  A3: Already answered → report old result, no update
  A4: Asking hint      → Socratic method via llm_query, never reveal answer
  A5: Multiple Qs      → read each from list_question via code
  A6: Next question    → compute from list_question in code

CASE B — Not related to list_question:
  B1: Greeting / small talk → reply naturally
  B2: Grammar theory        → use llm_query() to explain, adapted to theta
  B3: Off-topic             → politely decline
  B4: Unclear               → ask for clarification

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTPUT FORMAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For CASE A — always include:
DETECTED_JSON: [{{"question_id": "...", "user_answer": "...", "is_correct": true/false/null}}]
For wrong first attempt — also include:
RETRY: {{"question_id": "...", "retry_count": 1}}
For CASE B — just reply naturally, no special tags.

Language: Vietnamese input → reply Vietnamese + English terms. English input → reply English.
"""


# ============================================================
# ACTION PROMPTS (iteration-aware)
# ============================================================
FIRST_ACTION_PROMPT = """Think step-by-step on what to do to answer: "{question}"

You have NOT interacted with the REPL yet.
Your FIRST action: write Python code to READ data from REPL variables (list_question, detected_answers, etc.)
then use llm_query() to analyze or generate content.

Do NOT answer yet — explore data first.
Your next action:"""

CONTINUE_ACTION_PROMPT = """The history above shows your previous REPL interactions.

Continue to answer: "{question}"

Use llm_query() to delegate grammar analysis, answer evaluation, explanation to sub-LLMs.
When done, call FINAL(answer) inside code.
Your next action:"""

FINAL_ACTION_PROMPT = """Based on all information gathered, provide a final answer now.
If you haven't called FINAL() yet, do so. Otherwise write your complete answer directly."""


# ============================================================
# HELPERS
# ============================================================
def extract_code(text: str):
    match = re.search(r"```python\n(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else None

def extract_detected_json(text: str) -> list:
    match = re.search(r"DETECTED_JSON:\s*(\[.*?\])", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            return []
    return []

def extract_retry(text: str) -> dict:
    match = re.search(r"RETRY:\s*(\{.*?\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            return {}
    return {}

def is_complete_answer(text: str) -> bool:
    has_no_code    = "```python" not in text
    has_no_final   = "FINAL("    not in text
    is_substantial = len(text.strip()) > 50
    return has_no_code and has_no_final and is_substantial

def _build_action_prompt(question: str, iteration: int, max_iterations: int) -> str:
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

    # Khởi tạo REPL — data thật (list_question, theta, ...) sống ở đây
    env = REPLEnvironment(session)

    meta = env.get_metadata()

    system_prompt = SYSTEM_PROMPT.format(
        topic            = meta["topic"],
        theta            = meta["theta"],
        level            = theta_to_level(meta["theta"]),
        total_questions  = meta["total_questions"],
        available_ids    = meta["available_ids"],
        answered_ids     = meta["answered_ids"],
        context_length   = meta["context_length"],
        context_preview  = meta["context_preview"],
    )

    hist = [system_prompt]
    max_iterations = 7

    for i in range(max_iterations):
        # Refresh REPL với state mới nhất (theta có thể đã thay đổi)
        env.refresh()

        action_prompt = _build_action_prompt(question, i, max_iterations)
        hist.append(action_prompt)

        full_prompt = "\n\n".join(hist)
        response = call_llm(full_prompt)
        logger.log_llm_call("root", full_prompt, response)
        hist.append(response)

        # Xử lý DETECTED_JSON → cập nhật IRT
        detected = extract_detected_json(response)
        for d in detected:
            if d.get("user_answer") and d.get("is_correct") is not None:
                q = session.get_question_by_id(d["question_id"])
                if q:
                    theta_before = session.theta
                    p = computeP(session.theta, q["difficulty"])
                    session.record_answer(
                        d["question_id"],
                        d["user_answer"],
                        d["is_correct"]
                    )
                    logger.log_irt(
                        d["question_id"],
                        d["is_correct"],
                        p,
                        theta_before,
                        session.theta
                    )

        # Xử lý RETRY
        retry = extract_retry(response)
        if retry:
            print(f"[RETRY] Q{retry.get('question_id')} | "
                  f"attempt={retry.get('retry_count')}")

        # Ưu tiên 1: có code → chạy TRƯỚC (RLM style)
        # Phải chạy code trước để REPL truy cập được list_question,
        # và để FINAL() bên trong code được gọi đúng cách.
        code = extract_code(response)
        if code:
            stdout = env.execute(code, _logged_llm_query)
            logger.log_repl(code, stdout)
            hist.append(f"[REPL OUTPUT]:\n{stdout}")
            if env.final_answer:
                logger.log_final(env.final_answer, "REPL.FINAL()")
                return env.final_answer
            continue

        # Ưu tiên 2: FINAL() đã set từ vòng trước
        if env.final_answer:
            logger.log_final(env.final_answer, "REPL.FINAL()")
            return env.final_answer

        # Ưu tiên 3: FINAL("...") trong text (fallback hiếm)
        final_match = re.search(r'FINAL\("(.+?)"\)', response, re.DOTALL)
        if final_match:
            logger.log_final(final_match.group(1), "text.FINAL()")
            return final_match.group(1)

        # Ưu tiên 4: CASE B — không code, không FINAL → trả lời trực tiếp
        if is_complete_answer(response):
            logger.log_final(response, "direct_answer")
            return response

    result = env.final_answer or response
    logger.log_final(result, "fallback")
    return result