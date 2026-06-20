import json

from google.genai import types

from app.services.agent.context import AgentContext
from app.services.agent.tools.explain_word_tool import (
    explain_word_in_context,
)
from app.services.agent.tools.grammar_tool import (
    get_topics_lesson,
)
from app.services.agent.tools.history_tool import get_user_answer_history
from app.services.agent.tools.lesson_detail_tool import get_lesson_detail
from app.services.agent.tools.mistake_tool import analyze_mistake
from app.services.agent.tools.passage_tool import generate_passage
from app.services.agent.tools.preference_tool import (
    get_learner_preferences,
    set_learner_preferences,
)
from app.services.agent.tools.progress_tool import get_user_progress
from app.services.agent.tools.recent_mistakes_tool import get_recent_mistakes
from app.services.agent.tools.recommend_tool import recommend_questions
from app.services.agent.tools.snippet_tool import search_snippet
from app.services.agent.tools.study_plan_tool import generate_study_plan
from app.services.agent.tools.vocab_tool import lookup_vocabulary
from app.services.agent.tools.wrong_answers_tool import (
    aggregate_wrong_answers,
    batch_analyze_wrong_answers,
)

TOOL_DEFINITIONS = [
    # ─── Read-only progress / history ──────────────────────────────────
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
            "đáp án đúng/sai và accuracy tổng. Có thể lọc theo "
            "lesson_id, topic_id, hoặc số ngày gần đây (since_days). "
            "Dùng khi học viên hỏi về bài đã làm, kết quả gần đây."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "integer"},
                "topic_id": {"type": "integer"},
                "since_days": {
                    "type": "integer",
                    "description": "Số ngày gần đây, vd 7 = 1 tuần.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Số bản ghi (1-200), mặc định 20.",
                },
            },
            "required": [],
        },
        "fn": lambda ctx, args: get_user_answer_history(
            ctx.session,
            ctx.learner_id,
            lesson_id=(
                int(args["lesson_id"])
                if args.get("lesson_id") is not None
                else None
            ),
            topic_id=(
                int(args["topic_id"])
                if args.get("topic_id") is not None
                else None
            ),
            since_days=(
                int(args["since_days"])
                if args.get("since_days") is not None
                else None
            ),
            limit=int(args.get("limit") or 20),
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
    # ─── Vocabulary / Grammar lookup ───────────────────────────────────
    {
        "name": "lookup_vocabulary",
        "description": (
            "Tra cứu từ vựng tiếng Anh: trả về các brick/câu ví dụ chứa "
            "từ đó kèm bản dịch. Dùng khi học viên hỏi nghĩa hoặc cách "
            "dùng của một từ/cụm từ."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "word": {
                    "type": "string",
                    "description": "Từ hoặc cụm từ tiếng Anh cần tra.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Số ví dụ tối đa (1-10), mặc định 5.",
                },
            },
            "required": ["word"],
        },
        "fn": lambda ctx, args: lookup_vocabulary(
            ctx.session,
            word=args.get("word", ""),
            limit=int(args.get("limit") or 5),
        ),
    },
    # ─── Memory: mistakes & preferences ────────────────────────────────
    {
        "name": "aggregate_wrong_answers",
        "description": (
            "Thống kê câu sai của học viên dựa trên lịch sử trả lời "
            "(historyanswerquestion). KHÔNG gọi LLM, trả về số liệu "
            "nhanh: tổng số, accuracy, danh sách câu sai distinct kèm "
            "wrong_count, phân bố theo độ khó. Có thể lọc lesson_id, "
            "topic_id, since_days. Dùng cho 'tôi hay sai câu nào', "
            "'accuracy lesson X', 'tuần qua sai gì'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "integer"},
                "topic_id": {"type": "integer"},
                "since_days": {
                    "type": "integer",
                    "description": "Số ngày gần đây, vd 7 = 1 tuần.",
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Số bản ghi history quét (1-200), mặc định 50."
                    ),
                },
            },
            "required": [],
        },
        "fn": lambda ctx, args: aggregate_wrong_answers(
            ctx.session,
            ctx.learner_id,
            lesson_id=(
                int(args["lesson_id"])
                if args.get("lesson_id") is not None
                else None
            ),
            topic_id=(
                int(args["topic_id"])
                if args.get("topic_id") is not None
                else None
            ),
            since_days=(
                int(args["since_days"])
                if args.get("since_days") is not None
                else None
            ),
            limit=int(args.get("limit") or 50),
        ),
    },
    {
        "name": "batch_analyze_wrong_answers",
        "description": (
            "Phân tích hàng loạt câu sai của học viên: lấy câu sai từ "
            "history, gọi LLM theo chunk (mặc định 8 câu/call), có "
            "shared cache giữa các học viên (cùng câu hỏi + cùng kiểu "
            "sai chỉ gọi LLM 1 lần cho toàn hệ thống), lưu kết quả vào "
            "MistakeMemory cá nhân (có dedupe theo question_id). Dùng "
            "khi học viên muốn 'phân tích lỗi của tôi' hoặc sau khi "
            "aggregate_wrong_answers cho thấy có lỗi đáng phân tích."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "integer"},
                "topic_id": {"type": "integer"},
                "since_days": {"type": "integer"},
                "limit": {
                    "type": "integer",
                    "description": (
                        "Số câu sai tối đa để phân tích (1-15), mặc định 10."
                    ),
                },
                "chunk_size": {
                    "type": "integer",
                    "description": "Số câu/1 LLM call (1-10), mặc định 8.",
                },
            },
            "required": [],
        },
        "fn": lambda ctx, args: batch_analyze_wrong_answers(
            ctx.session,
            ctx.learner_id,
            lesson_id=(
                int(args["lesson_id"])
                if args.get("lesson_id") is not None
                else None
            ),
            topic_id=(
                int(args["topic_id"])
                if args.get("topic_id") is not None
                else None
            ),
            since_days=(
                int(args["since_days"])
                if args.get("since_days") is not None
                else None
            ),
            limit=int(args.get("limit") or 10),
            chunk_size=int(args.get("chunk_size") or 8),
        ),
    },
    {
        "name": "analyze_mistake",
        "description": (
            "Phân tích lỗi sai của học viên (loại lỗi, điểm ngữ pháp, "
            "giải thích, gợi ý sửa) và lưu vào MistakeMemory. Dùng khi "
            "học viên đưa câu trả lời sai hoặc hỏi 'câu này sai ở đâu'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Đề bài/câu hỏi gốc.",
                },
                "learner_answer": {
                    "type": "string",
                    "description": "Câu trả lời sai của học viên.",
                },
                "correct_answer": {
                    "type": "string",
                    "description": "Đáp án đúng (nếu biết). Có thể bỏ qua.",
                },
            },
            "required": ["question", "learner_answer"],
        },
        "fn": lambda ctx, args: analyze_mistake(
            ctx.session,
            learner_id=ctx.learner_id,
            question=args.get("question", ""),
            learner_answer=args.get("learner_answer", ""),
            correct_answer=args.get("correct_answer"),
        ),
    },
    {
        "name": "get_recent_mistakes",
        "description": (
            "Lấy danh sách lỗi sai gần nhất đã ghi vào MistakeMemory, "
            "kèm thống kê theo loại và theo điểm ngữ pháp. Dùng khi "
            "học viên hỏi 'tôi hay sai gì', hoặc cần ngữ cảnh trước "
            "khi gợi ý bài tập."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Số lỗi gần nhất (1-20), mặc định 5.",
                },
            },
            "required": [],
        },
        "fn": lambda ctx, args: get_recent_mistakes(
            ctx.session,
            ctx.learner_id,
            limit=int(args.get("limit") or 5),
        ),
    },
    {
        "name": "get_learner_preferences",
        "description": (
            "Đọc preferences đã lưu của học viên (kiểu bài tập ưa thích, "
            "phong cách học, mục tiêu, ghi chú). Dùng khi cần cá nhân "
            "hoá lời khuyên."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "fn": lambda ctx, args: get_learner_preferences(
            ctx.session, ctx.learner_id
        ),
    },
    {
        "name": "set_learner_preferences",
        "description": (
            "Ghi/Cập nhật preferences của học viên. Dùng khi học viên "
            "nói rõ sở thích/mục tiêu, ví dụ 'tôi thích học qua đoạn "
            "văn', 'mục tiêu của tôi là TOEIC 700'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "preferred_exercise_type": {"type": "string"},
                "learning_style": {"type": "string"},
                "goal": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": [],
        },
        "fn": lambda ctx, args: set_learner_preferences(
            ctx.session,
            ctx.learner_id,
            preferred_exercise_type=args.get("preferred_exercise_type"),
            learning_style=args.get("learning_style"),
            goal=args.get("goal"),
            notes=args.get("notes"),
        ),
    },
    # ─── Content generation ────────────────────────────────────────────
    {
        "name": "generate_passage",
        "description": (
            "Sinh đoạn văn tiếng Anh luyện đọc theo chủ đề, độ khó tự "
            "động bám theo theta của học viên (CEFR), kèm câu hỏi đọc "
            "hiểu và từ vựng quan trọng."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Chủ đề đoạn văn (vd: 'travel').",
                },
                "question_count": {
                    "type": "integer",
                    "description": "Số câu hỏi đọc hiểu (1-5).",
                },
            },
            "required": ["topic"],
        },
        "fn": lambda ctx, args: generate_passage(
            ctx.session,
            learner_id=ctx.learner_id,
            topic=args.get("topic", ""),
            question_count=int(args.get("question_count") or 3),
        ),
    },
    {
        "name": "generate_study_plan",
        "description": (
            "Lập kế hoạch học cá nhân hoá theo mục tiêu (vd: 'TOEIC 600 "
            "trong 3 tháng'), dựa trên theta hiện tại + lỗi gần đây."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Mục tiêu học tập.",
                },
                "weeks": {
                    "type": "integer",
                    "description": "Số tuần (1-24), mặc định 4.",
                },
            },
            "required": ["goal"],
        },
        "fn": lambda ctx, args: generate_study_plan(
            ctx.session,
            learner_id=ctx.learner_id,
            goal=args.get("goal", ""),
            weeks=int(args.get("weeks") or 4),
        ),
    },
    # ─── Recommendation & deep lookup ──────────────────────────────────
    {
        "name": "recommend_questions",
        "description": (
            "Gợi ý câu hỏi luyện tập có độ khó phù hợp với theta của "
            "học viên. Có thể giới hạn theo topic_id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic_id": {
                    "type": "integer",
                    "description": "ID topic muốn lọc, có thể bỏ qua.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Số câu (1-10), mặc định 5.",
                },
            },
            "required": [],
        },
        "fn": lambda ctx, args: recommend_questions(
            ctx.session,
            ctx.learner_id,
            topic_id=(
                int(args["topic_id"])
                if args.get("topic_id") is not None
                else None
            ),
            limit=int(args.get("limit") or 5),
        ),
    },
    {
        "name": "explain_word_in_context",
        "description": (
            "Giải thích nghĩa của 1 từ TRONG ngữ cảnh cụ thể. Nếu "
            "không có ngữ cảnh, fallback sang giải thích chung. Dùng "
            "khi học viên đưa nguyên câu và hỏi 'từ X trong câu này "
            "nghĩa là gì'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "word": {"type": "string"},
                "context": {
                    "type": "string",
                    "description": "Câu/đoạn chứa từ. Có thể bỏ qua.",
                },
            },
            "required": ["word"],
        },
        "fn": lambda ctx, args: explain_word_in_context(
            ctx.session,
            word=args.get("word", ""),
            context=args.get("context"),
        ),
    },
    {
        "name": "get_lesson_detail",
        "description": (
            "Lấy chi tiết 1 lesson: tên, mô tả "
            "danh sách exercise. Dùng khi học viên hỏi sâu về 1 lesson."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lesson_id": {"type": "integer"},
            },
            "required": ["lesson_id"],
        },
        "fn": lambda ctx, args: get_lesson_detail(
            ctx.session, lesson_id=int(args.get("lesson_id"))
        ),
    },
    {
        "name": "search_snippet",
        "description": (
            "Tìm snippet (đoạn audio + transcript do người dùng đóng "
            "góp) khớp với từ khoá. Dùng khi học viên muốn nghe ví dụ "
            "thực tế hoặc tìm clip về một chủ đề."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {
                    "type": "integer",
                    "description": "Số snippet (1-10), mặc định 5.",
                },
            },
            "required": ["query"],
        },
        "fn": lambda ctx, args: search_snippet(
            ctx.session,
            query=args.get("query", ""),
            limit=int(args.get("limit") or 5),
        ),
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
