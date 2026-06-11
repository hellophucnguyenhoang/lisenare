import json

from google.genai import types

from app.services.agent.context import AgentContext
from app.services.agent.tools.grammar_tool import get_topics_lesson
from app.services.agent.tools.history_tool import get_user_answer_history
from app.services.agent.tools.progress_tool import get_user_progress


TOOL_DEFINITIONS = [
    {
        "name": "get_user_progress",
        "description": (
            "Lấy tiến độ học của học viên hiện tại: theta trung bình, "
            "level CEFR, danh sách lesson đã học cùng theta từng lesson. "
            "Dùng khi học viên hỏi về trình độ, điểm yếu, nên học gì tiếp."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda ctx, args: get_user_progress(ctx.session, ctx.learner_id),
    },
    {
        "name": "get_user_answer_history",
        "description": (
            "Lấy lịch sử các câu hỏi học viên đã trả lời gần đây, kèm "
            "đáp án đúng/sai và accuracy tổng. Dùng khi học viên hỏi về "
            "bài đã làm, lỗi thường gặp, kết quả gần đây."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda ctx, args: get_user_answer_history(
            ctx.session, ctx.learner_id
        ),
    },
    {
        "name": "get_topics_lesson",
        "description": (
            "Liệt kê toàn bộ topic và lesson có trong hệ thống. Dùng khi "
            "học viên hỏi 'có gì để học', 'có những chủ đề nào', hoặc khi "
            "cần gợi ý lesson cụ thể."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda ctx, args: json.loads(get_topics_lesson(ctx.session)),
    },
]


def get_tool_declarations() -> list[types.Tool]:
    function_declarations = [
        {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
        }
        for tool in TOOL_DEFINITIONS
    ]
    return [types.Tool(function_declarations=function_declarations)]


def dispatch(name: str, args: dict, ctx: AgentContext) -> dict:
    args = args or {}
    for tool in TOOL_DEFINITIONS:
        if tool["name"] == name:
            try:
                return tool["fn"](ctx, args)
            except Exception as exc:
                return {
                    "ok": False,
                    "tool": name,
                    "error": f"{type(exc).__name__}: {exc}",
                }
    return {"ok": False, "error": f"Unknown tool: {name}"}
