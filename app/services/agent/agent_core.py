from google.genai import types

from app.services.agent.context import AgentContext
from app.services.agent.tool_registry import dispatch, get_tool_declarations
from app.services.llm_service import call_llm_with_tools

SYSTEM_PROMPT = """Bạn là một gia sư tiếng Anh thân thiện, hỗ trợ học viên Việt Nam.

Phong cách: Socratic Tutor — gợi mở, không lộ đáp án ngay; phân tích lỗi sai;
điều chỉnh độ khó giải thích theo trình độ học viên; động viên đúng lúc.

QUY TẮC DÙNG TOOL (chọn đúng tool theo intent của học viên):

Đọc dữ liệu học viên:
- Tiến độ / theta / level / nên học gì → `get_user_progress`.
- Lịch sử bài đã làm / accuracy → `get_user_answer_history`
  (có thể lọc lesson_id, topic_id, since_days).
- Thống kê câu sai (distinct, đếm số lần sai, theo lesson/topic/khoảng
  thời gian) — KHÔNG LLM, nhanh → `aggregate_wrong_answers`.
- Lỗi sai gần đây / hay sai gì → `get_recent_mistakes` (đọc MistakeMemory
  đã lưu).

Ghi memory:
- Học viên đưa MỘT câu sai cụ thể và muốn phân tích lẻ → `analyze_mistake`.

Khám phá nội dung:
- Có gì để học / liệt kê topic, lesson → `get_topics_lesson`.
- Hỏi sâu về 1 lesson cụ thể → `get_lesson_detail`.
- Tra nghĩa / cách dùng 1 từ → `lookup_vocabulary`.
- Hỏi nghĩa từ TRONG ngữ cảnh câu → `explain_word_in_context`.
- Tìm snippet audio/transcript → `search_snippet`.

Sinh nội dung & gợi ý:
- "Cho đoạn văn luyện đọc..." → `generate_passage`.
- "Cho vài câu để luyện tập" → `recommend_questions`.

NGUYÊN TẮC:
- KHÔNG bịa số liệu (theta, accuracy, tên lesson). Cần dữ liệu thật
  thì PHẢI gọi tool. Nếu tool trả về rỗng/lỗi, trả lời trung thực.
- Không cần gọi tool cho lời chào hỏi, câu hỏi kiến thức tiếng Anh thuần
  (ngữ pháp/từ vựng đại chúng) khi không cần dữ liệu cá nhân của học viên.
- Có thể gọi nhiều tool trong cùng 1 lượt nếu cần (vd: `get_user_progress`
  + `get_recent_mistakes` trước khi tổng hợp câu trả lời).
- Sau khi tool trả dữ liệu, tổng hợp lại bằng văn phong gia sư, không paste
  thẳng JSON cho học viên.

QUY TẮC NGÔN NGỮ (BẮT BUỘC):
- Trả lời hoàn toàn bằng tiếng Việt.
- Giữ nguyên thuật ngữ ngữ pháp tiếng Anh trong ngoặc khi cần (ví dụ:
  "thì hiện tại hoàn thành (present perfect)").
- Không viết song ngữ, không dịch lại sang tiếng Anh.
"""


def _messages_to_contents(messages: list[dict]) -> list:
    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        text = msg.get("content", "")
        genai_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=genai_role,
                parts=[types.Part.from_text(text=text)],
            )
        )
    return contents


def _summarize_result(result) -> str:
    if isinstance(result, dict):
        if "summary" in result:
            return str(result["summary"])
        if "error" in result:
            return f"error: {result['error']}"
        keys = list(result.keys())[:5]
        return f"keys={keys}"
    return str(result)[:200]


def run_agent(
    messages: list[dict],
    ctx: AgentContext,
    max_steps: int = 6,
) -> dict:
    contents = _messages_to_contents(messages)
    tools = get_tool_declarations()
    tool_call_logs: list[dict] = []

    for step in range(max_steps):
        response = call_llm_with_tools(
            contents=contents,
            tools=tools,
            system_instruction=SYSTEM_PROMPT,
        )

        candidate = response.candidates[0] if response.candidates else None
        if candidate is None or candidate.content is None:
            feedback = getattr(response, "prompt_feedback", None)
            print(
                f"[agent] step {step}: no candidate, "
                f"prompt_feedback={feedback}"
            )
            break

        finish_reason = getattr(candidate, "finish_reason", None)
        parts = candidate.content.parts or []
        function_calls = [p.function_call for p in parts if p.function_call]

        if not function_calls:
            answer = (response.text or "").strip()
            print(
                f"[agent] step {step}: final text ({len(answer)} chars), "
                f"finish_reason={finish_reason}"
            )
            if not answer:
                return {
                    "answer": (
                        "Xin lỗi, tôi đã lấy được dữ liệu nhưng chưa "
                        "diễn giải được thành câu trả lời. Bạn có thể "
                        "hỏi cụ thể hơn không?"
                    ),
                    "tool_calls": tool_call_logs,
                }
            return {"answer": answer, "tool_calls": tool_call_logs}

        contents.append(candidate.content)

        for fc in function_calls:
            name = fc.name
            args = dict(fc.args) if fc.args else {}
            print(f"[agent] step {step}: call tool={name} args={args}")
            result = dispatch(name, args, ctx)
            summary = _summarize_result(result)
            print(f"[agent] step {step}: result {summary}")
            tool_call_logs.append(
                {"name": name, "args": args, "result_summary": summary}
            )
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=name,
                            response={"result": result},
                        )
                    ],
                )
            )

    print(f"[agent] hit max_steps={max_steps}, returning fallback")
    return {
        "answer": (
            "Xin lỗi, tôi đã thử dùng nhiều công cụ nhưng chưa tổng hợp "
            "được câu trả lời. Bạn có thể hỏi lại cụ thể hơn không?"
        ),
        "tool_calls": tool_call_logs,
    }
