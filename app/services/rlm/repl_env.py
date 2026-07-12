"""REPL state bền vững + hàm exec_code chạy Python có timeout (vendor từ project RLM)."""

from __future__ import annotations

import io
import json
import math
import re
import sys
import threading
import traceback
from dataclasses import dataclass, field
from typing import Any


@dataclass
class REPLState:
    globals: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.globals:
            self.globals = {
                "__builtins__": __builtins__,
                "re": re,
                "json": json,
                "math": math,
            }


def exec_code(state: REPLState, code: str, timeout: float) -> str:
    """Chạy `code` trong globals của state, capture stdout, có timeout mềm.

    Timeout được thực hiện bằng thread + join. Nếu quá hạn, thread vẫn chạy nền
    (Python không kill thread được) nhưng vòng lặp RLM sẽ nhận được thông báo timeout
    và tiếp tục.
    """
    buf = io.StringIO()
    result: dict[str, Any] = {"error": None, "done": False}

    def _target() -> None:
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            exec(code, state.globals)
        except Exception:
            result["error"] = traceback.format_exc()
        finally:
            sys.stdout = old_stdout
            result["done"] = True

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if not result["done"]:
        return (
            buf.getvalue()
            + f"\n[LỖI TIMEOUT] Code vượt quá {timeout:.0f} giây, đã bỏ dở. "
            "Hãy chia nhỏ công việc hoặc tối ưu code."
        )

    out = buf.getvalue()
    if result["error"]:
        out += "\n[TRACEBACK]\n" + result["error"]
    return out
