"""Vòng lặp RLM cho chatbot tutoring — adapt Algorithm 1 (project RLM) cho domain lisenare.

`run_rlm(question, session, depth)` là lệnh gọi gốc: nạp state tutoring (list_question,
theta, current_question_id, set_current) vào REPL. Nếu depth>=2, LLM có thể gọi
`rlm_query(context, query)` để spawn một RLM con "generic" (không có state tutoring) qua
`_run_generic`, dùng để xử lý một đoạn ngữ cảnh lớn/phức tạp cần tự chia nhỏ nhiều tầng.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from app.services.theta_learner_lesson_service import theta_to_level

from . import config
from .gemini_client import GeminiClient
from .parser import extract_final, extract_repl_blocks
from .repl_env import REPLState, exec_code
from .system_prompts import (
    fill_generic_prompt,
    fill_tutoring_prompt,
    pick_generic_prompt,
    pick_tutoring_prompt,
)


class TrajectoryLogger:
    """Ghi mỗi turn ra 2 file JSONL trong config.LOG_DIR (chỉ khi bật TRAJECTORY_LOGGING_ENABLED):

    - `{tag}_{ts}.jsonl`         — vắn tắt (như trước): mốc sự kiện, độ dài, timing.
    - `{tag}_{ts}_detail.jsonl` — chi tiết: code REPL sinh ra, stdout đầy đủ, state
      REPL trước/sau mỗi lần exec, output thô của LLM.
    """

    def __init__(self, tag: str) -> None:
        self._enabled = config.TRAJECTORY_LOGGING_ENABLED
        self._fp = None
        self._detail_fp = None
        if self._enabled:
            os.makedirs(config.LOG_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(config.LOG_DIR, f"{tag}_{ts}.jsonl")
            detail_path = os.path.join(config.LOG_DIR, f"{tag}_{ts}_detail.jsonl")
            self._fp = open(path, "w", encoding="utf-8")
            self._detail_fp = open(detail_path, "w", encoding="utf-8")

    def log(self, event: str, payload: dict) -> None:
        if not self._enabled:
            return
        record = {"ts": time.time(), "event": event, **payload}
        self._fp.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._fp.flush()

    def log_detail(self, event: str, payload: dict) -> None:
        if not self._enabled:
            return
        record = {"ts": time.time(), "event": event, **payload}
        self._detail_fp.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._detail_fp.flush()

    def close(self) -> None:
        if self._fp is not None:
            self._fp.close()
        if self._detail_fp is not None:
            self._detail_fp.close()


def _json_safe(value):
    """Chuyển value thành dạng JSON-serialize được, tốt nhất có thể (pydantic model -> dict)."""
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:  # noqa: BLE001
            return str(value)
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    return value


def _serialize_state(state_globals: dict) -> dict:
    """Snapshot REPL globals, bỏ hàm/biến nội bộ, cho vào log chi tiết."""
    return {
        k: _json_safe(v)
        for k, v in state_globals.items()
        if k != "__builtins__" and not callable(v)
    }


def _shorten(text: str, limit: int = 120) -> str:
    text = str(text).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _truncate(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    return s[:limit] + f"\n... [đã cắt bớt, tổng {len(s)} ký tự]"


def _resolve_final_var(expr: str, state_globals: dict) -> str:
    expr = expr.strip()
    if expr.isidentifier() and expr in state_globals:
        return str(state_globals[expr])
    try:
        return str(eval(expr, state_globals))  # noqa: S307
    except Exception as err:  # noqa: BLE001
        return f"[Không đánh giá được FINAL_VAR({expr}): {err}]"


def _describe_context(ctx) -> tuple[str, int, str]:
    if isinstance(ctx, str):
        return ("chuỗi", len(ctx), str(len(ctx)))
    if isinstance(ctx, list):
        lens = [len(str(x)) for x in ctx]
        return (
            f"danh sách gồm {len(ctx)} phần tử",
            sum(lens),
            ", ".join(str(x) for x in lens[:20]) + ("..." if len(lens) > 20 else ""),
        )
    text = str(ctx)
    return (type(ctx).__name__, len(text), str(len(text)))


def _history_to_string(history: list) -> str:
    if not history:
        return "[Chưa có lịch sử trò chuyện]"
    return "\n".join(f"[{turn.role.upper()}]: {turn.content}" for turn in history)


def _make_llm_query(client: GeminiClient, logger: TrajectoryLogger):
    def llm_query(prompt: str) -> str:
        print(f"  [llm_query] → gọi sub-LLM (prompt {len(prompt)} ký tự)...")
        t0 = time.time()
        out = client.simple_query(prompt)
        elapsed = round(time.time() - t0, 3)
        print(f"  [llm_query] ← xong trong {elapsed}s, trả lời {len(out)} ký tự: {_shorten(out)}")
        logger.log(
            "llm_query",
            {
                "prompt_len": len(prompt),
                "answer_len": len(out),
                "elapsed": elapsed,
            },
        )
        return out

    return llm_query


def _make_rlm_query(child_depth: int, client: GeminiClient, logger: TrajectoryLogger):
    def rlm_query(ctx, query: str) -> str:
        print(f"  [rlm_query] ↓ spawn RLM con depth={child_depth}, context {len(str(ctx))} ký tự, query: {_shorten(query)}")
        combined_prompt = f"{query}\n\n--- CONTEXT ---\n{ctx}"
        logger.log("rlm_query_enter", {"child_depth": child_depth, "ctx_len": len(str(ctx))})
        out = _run_generic(combined_prompt, child_depth, _parent_client=client, _parent_logger=logger)
        print(f"  [rlm_query] ↑ RLM con depth={child_depth} xong, trả lời {len(out)} ký tự")
        logger.log("rlm_query_exit", {"child_depth": child_depth, "answer_len": len(out)})
        return out

    return rlm_query


def _make_set_current(session, state: REPLState):
    def set_current(qid) -> bool:
        before = session.current_question_id
        ok = session.set_current_question(qid)
        if ok:
            state.globals["current_question_id"] = session.current_question_id
            if before != session.current_question_id:
                print(f"  [set_current] current_question_id: {before} → {session.current_question_id}")
        else:
            print(f"  [set_current] qid={qid!r} KHÔNG hợp lệ, current_question_id giữ nguyên ({before})")
        return ok

    return set_current


def _run_generic(
    prompt: str,
    depth: int,
    *,
    _parent_client: Optional[GeminiClient] = None,
    _parent_logger: Optional[TrajectoryLogger] = None,
) -> str:
    """RLM con "generic" (không có state tutoring) — chỉ dùng bởi rlm_query."""
    depth = max(0, min(depth, config.MAX_RECURSION_DEPTH))
    client = _parent_client or GeminiClient(model_name=config.SUB_MODEL)
    logger = _parent_logger or TrajectoryLogger(tag="rlm_generic")
    print(f"  [RLM generic] bắt đầu depth={depth}, context {len(prompt)} ký tự")

    state = REPLState()
    state.globals["context"] = prompt
    if depth >= 1:
        state.globals["llm_query"] = _make_llm_query(client, logger)
    if depth >= 2:
        state.globals["rlm_query"] = _make_rlm_query(depth - 1, client, logger)

    ctype, total, lens = _describe_context(prompt)
    system_prompt = fill_generic_prompt(
        pick_generic_prompt(depth),
        context_type=ctype,
        context_total_length=total,
        context_lengths=lens,
        sub_lm_chars=f"{config.SUB_LM_CONTEXT_CHAR_HINT:,}",
    )

    history: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Ngữ cảnh đã được nạp vào biến `context`. Loại: {ctype}, tổng {total} ký tự.\n"
                "Hãy bắt đầu bằng cách viết một khối ```repl để khám phá và xử lý context."
            ),
        }
    ]

    logger.log_detail("state_init", {"depth": depth, "state": _serialize_state(state.globals)})

    final_answer: Optional[str] = None
    for it in range(config.MAX_ITERATIONS):
        print(f"  [RLM generic depth={depth} iter={it}] gọi LLM...")
        try:
            output = client.generate(history, system_prompt)
        except Exception as err:  # noqa: BLE001
            print(f"  [RLM generic depth={depth} iter={it}] LỖI: {err}")
            final_answer = f"[RLM lỗi khi gọi LLM: {err}]"
            break

        history.append({"role": "model", "content": output})

        blocks = extract_repl_blocks(output)
        final = extract_final(output)

        if blocks:
            code = "\n".join(blocks)
            print(f"  [RLM generic depth={depth} iter={it}] exec code ({len(code)} ký tự)")
            state_before = _serialize_state(state.globals)
            stdout = exec_code(state, code, config.MAX_CODE_EXEC_SECONDS)
            state_after = _serialize_state(state.globals)
            truncated = _truncate(stdout, config.MAX_STDOUT_CHARS)
            print(f"  [RLM generic depth={depth} iter={it}] stdout: {_shorten(stdout)}")
            logger.log_detail(
                "repl_exec",
                {
                    "iter": it,
                    "llm_output": output,
                    "code": code,
                    "stdout": stdout,
                    "state_before": state_before,
                    "state_after": state_after,
                },
            )
            history.append(
                {"role": "user", "content": f"[REPL stdout, tổng {len(stdout)} ký tự]\n{truncated}"}
            )
            continue

        if final is not None:
            kind, val = final
            final_answer = val if kind == "direct" else _resolve_final_var(val, state.globals)
            print(f"  [RLM generic depth={depth} iter={it}] FINAL ({kind}): {_shorten(final_answer)}")
            logger.log_detail(
                "rlm_final",
                {"iter": it, "kind": kind, "final_answer": final_answer, "state": _serialize_state(state.globals)},
            )
            break

        print(f"  [RLM generic depth={depth} iter={it}] không có code/FINAL → nhắc lại")
        history.append(
            {
                "role": "user",
                "content": (
                    "Bạn không viết code REPL hay FINAL nào. Hãy tiếp tục bằng cách viết "
                    "một khối ```repl để thao tác với context, hoặc trả FINAL(...) nếu đã "
                    "có câu trả lời chắc chắn."
                ),
            }
        )

    if final_answer is None:
        final_answer = "[RLM: quá số vòng lặp cho phép mà chưa có FINAL]"
        print(f"  [RLM generic depth={depth}] hết {config.MAX_ITERATIONS} vòng lặp mà chưa có FINAL")

    return final_answer


def run_rlm(question: str, session, depth: int = config.DEFAULT_DEPTH) -> str:
    """Lệnh gọi gốc dùng bởi `app.services.rlm_service.run_rlm`.

    depth=0: chỉ REPL (không llm_query) — root LLM tự viết câu trả lời trong FINAL.
    depth=1 (mặc định): + llm_query cho sub-task sinh nội dung tiếng Việt.
    depth=2: + rlm_query để đệ quy xử lý ngữ cảnh lớn/phức tạp (hiếm cần trong tutoring).
    """
    depth = max(0, min(depth, config.MAX_RECURSION_DEPTH))
    client = GeminiClient(model_name=config.ROOT_MODEL)
    logger = TrajectoryLogger(tag="rlm_tutoring")

    print(f"\n{'=' * 60}")
    print(f"[RLM] bắt đầu turn mới — depth={depth}")
    print(f"[RLM] học viên: {_shorten(question, 200)}")
    print(f"{'=' * 60}")

    theta = session.theta
    topic = session.topic
    list_question = session.list_question
    history_str = _history_to_string(session.history)

    state = REPLState()
    state.globals.update(
        {
            "context": history_str,
            "list_question": list_question,
            "topic": topic,
            "theta": theta,
            "current_question_id": session.current_question_id,
        }
    )
    protected_keys = {"context", "list_question", "topic", "theta"}
    state.globals["set_current"] = _make_set_current(session, state)
    if depth >= 1:
        state.globals["llm_query"] = _make_llm_query(client, logger)
    if depth >= 2:
        state.globals["rlm_query"] = _make_rlm_query(depth - 1, client, logger)

    context_preview = history_str if len(history_str) <= 500 else "..." + history_str[-500:]
    order_ids = [q.order_id for q in list_question]

    system_prompt = fill_tutoring_prompt(
        pick_tutoring_prompt(depth),
        depth=depth,
        topic=topic,
        theta=theta,
        level=theta_to_level(theta),
        total_questions=len(list_question),
        available_ids=order_ids,
        current_question_id=session.current_question_id,
        context_length=len(history_str),
        context_preview=context_preview,
    )

    history: list[dict] = [
        {
            "role": "user",
            "content": (
                f'Tin nhắn mới của học viên: "{question}"\n\n'
                "Hãy bắt đầu bằng cách viết một khối ```repl để đọc dữ liệu cần thiết "
                "(list_question, current_question_id, ...) và tạo câu trả lời, rồi dùng "
                "FINAL(...)/FINAL_VAR(...) NGOÀI code block khi đã xong."
            ),
        }
    ]

    logger.log("rlm_start", {"depth": depth, "question": question[:300]})
    logger.log_detail(
        "state_init",
        {"depth": depth, "question": question, "state": _serialize_state(state.globals)},
    )

    final_answer: Optional[str] = None
    for it in range(config.MAX_ITERATIONS):
        print(f"\n[RLM iter={it}] gọi LLM gốc...")
        try:
            output = client.generate(history, system_prompt)
        except Exception as err:  # noqa: BLE001
            print(f"[RLM iter={it}] LỖI khi gọi LLM: {err}")
            logger.log("llm_error", {"iter": it, "error": str(err)})
            final_answer = f"[RLM lỗi khi gọi LLM: {err}]"
            break

        history.append({"role": "model", "content": output})

        blocks = extract_repl_blocks(output)
        final = extract_final(output)

        if blocks:
            code = "\n".join(blocks)
            print(f"[RLM iter={it}] LLM viết code REPL ({len(code)} ký tự) → exec...")
            state_before = _serialize_state(state.globals)
            stdout = exec_code(state, code, config.MAX_CODE_EXEC_SECONDS)
            print(f"[RLM iter={it}] REPL stdout ({len(stdout)} ký tự): {_shorten(stdout)}")

            # Khôi phục các biến chỉ đọc phòng khi LLM cố tình gán đè trong code.
            state.globals["context"] = history_str
            state.globals["list_question"] = list_question
            state.globals["topic"] = topic
            state.globals["theta"] = theta
            state.globals["current_question_id"] = session.current_question_id
            state_after = _serialize_state(state.globals)

            truncated = _truncate(stdout, config.MAX_STDOUT_CHARS)
            logger.log("repl_exec", {"iter": it, "code_len": len(code)})
            logger.log_detail(
                "repl_exec",
                {
                    "iter": it,
                    "llm_output": output,
                    "code": code,
                    "stdout": stdout,
                    "state_before": state_before,
                    "state_after": state_after,
                },
            )
            history.append(
                {"role": "user", "content": f"[REPL stdout, tổng {len(stdout)} ký tự]\n{truncated}"}
            )
            continue

        if final is not None:
            kind, val = final
            final_answer = val if kind == "direct" else _resolve_final_var(val, state.globals)
            print(f"[RLM iter={it}] FINAL ({kind}): {_shorten(final_answer, 200)}")
            logger.log("rlm_final", {"iter": it, "kind": kind})
            logger.log_detail(
                "rlm_final",
                {
                    "iter": it,
                    "kind": kind,
                    "llm_output": output,
                    "final_answer": final_answer,
                    "state": _serialize_state(state.globals),
                },
            )
            break

        print(f"[RLM iter={it}] LLM không viết code REPL cũng không FINAL → nhắc lại")
        history.append(
            {
                "role": "user",
                "content": (
                    "Bạn không viết code REPL hay FINAL nào. Hãy tiếp tục bằng cách viết "
                    "một khối ```repl để thao tác với dữ liệu, hoặc trả FINAL(...)/"
                    "FINAL_VAR(...) nếu đã có câu trả lời chắc chắn."
                ),
            }
        )

    if final_answer is None:
        final_answer = "[RLM: quá số vòng lặp cho phép mà chưa có câu trả lời cuối cùng]"
        print(f"[RLM] hết {config.MAX_ITERATIONS} vòng lặp mà chưa có câu trả lời cuối cùng")
        logger.log("rlm_timeout_iters", {"iters": config.MAX_ITERATIONS})

    print(
        f"[RLM] kết thúc turn — current_question_id={session.current_question_id}, "
        f"số lần gọi LLM={client.stats.calls}, tokens in/out={client.stats.prompt_tokens}/"
        f"{client.stats.completion_tokens}"
    )
    print(f"{'=' * 60}\n")
    logger.log("rlm_end", {"answer_len": len(final_answer), "calls": client.stats.calls})
    logger.close()

    return final_answer
