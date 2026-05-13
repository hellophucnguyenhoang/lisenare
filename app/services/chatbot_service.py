import re
from collections.abc import Iterable

from app.schemas.grammar import Message, QuestionContext
from app.services.llm_service import call_llm, call_llm_stream


def find_target_question(
    messages: list[Message], questions: list[QuestionContext]
) -> QuestionContext | None:

    # Bước 1: Lấy message cuối cùng của user
    last_user_message = next(
        (m for m in reversed(messages) if m.role == "user"), None
    )
    if not last_user_message:
        return None

    # Bước 2: Build prompt với đầy đủ context
    question_list_text = "\n".join(
        [f"question_id={q.question_id}: {q.question}" for q in questions]
    )

    conversation_history = "\n".join(
        [f"{m.role}: {m.content}" for m in messages]
    )

    prompt = f"""You have access to the following data to determine which question the user is asking about.

    === CONVERSATION HISTORY ===
    {conversation_history}

    === QUESTION LIST ===
    {question_list_text}

    === TASK ===
    1. Read the latest user message: "{last_user_message.content}"
    2. If the message is ambiguous (e.g., "that question", "the previous one", "what you just said"),
    trace back through the conversation history to determine the context.
    3. Match the intent to the question list and find the corresponding question_id.

    Examples of cases that require reading conversation history:
    - "how about that one?" → check which question the assistant last mentioned
    - "what about the next question?" → find the question after the last discussed one
    - "what did you say about it?" → re-read the assistant's previous response

    Return ONLY a single integer representing the question_id.
    If you cannot determine the question, return -1.
    No explanation, just the number."""

    response = call_llm(prompt)

    match = re.search(r"-?\d+", response.strip())
    if not match:
        return None

    question_id = int(match.group())
    if question_id == -1:
        return None

    return next((q for q in questions if q.question_id == question_id), None)


def get_hint_stream(
    theta: float,
    prob: float,
    lesson: str,
    question: str,
    correct_answer: str,
    choice: str,
) -> Iterable[str]:
    prompt = f"""
You are a helpful English learning assistant. Your role is to give a SHORT hint to help the user think, NOT to reveal the answer.
## Input:
- User level (theta): {theta} (scale -3 to 3, where -3=A1, 0=B1/B2, 3=C2)
- Probability of correct answer (P): {prob} (0 to 1)
- Lesson: {lesson}
- Question: {question}
- Choice: {choice}
- Correct answer: {correct_answer}
## Your task:
Give ONE short hint (1–2 sentences max) to guide the user toward the correct answer.
## Hint strategy based on P value:
- P < 0.3 (question is too hard): Give a more direct hint, provide a similar example sentence or context clue
- 0.3 ≤ P ≤ 0.7 (appropriate level): Give a subtle hint, nudge them to think about grammar rule or word meaning
- P > 0.7 (question is too easy): Give a very minimal hint, just a gentle reminder
## Rules:
- NEVER reveal the correct answer
- NEVER say "the answer is..." or "you should use..."
- Keep it SHORT (1–2 sentences)
- Always respond in Vietnamese
- Match hint complexity to user level: simpler language for low theta, more sophisticated for high theta
## Output:
Return only the hint text, nothing else.
"""
    yield from call_llm_stream(prompt)
