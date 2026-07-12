"""Tách khối ```repl và lệnh FINAL / FINAL_VAR từ output raw của LLM (vendor từ project RLM)."""

from __future__ import annotations

import re
from typing import Optional

_REPL_BLOCK_RE = re.compile(
    r"```(?:repl|python)\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_repl_blocks(text: str) -> list[str]:
    """Trả về list các đoạn code Python nằm trong ```repl ... ``` (hoặc ```python)."""
    return [m.group(1).strip() for m in _REPL_BLOCK_RE.finditer(text)]


def _strip_repl_blocks(text: str) -> str:
    return _REPL_BLOCK_RE.sub("", text)


def _match_balanced(text: str, tag: str) -> Optional[str]:
    """Tìm `TAG(...)`, cân bằng ngoặc đơn giản. Trả về chuỗi bên trong."""
    marker = tag + "("
    idx = text.find(marker)
    if idx < 0:
        return None
    start = idx + len(marker)
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def extract_final(text: str) -> Optional[tuple[str, str]]:
    """Tìm FINAL(...) hoặc FINAL_VAR(...) NGOÀI code block.

    Returns ("direct", answer) hoặc ("var", var_name) hoặc None.
    Ưu tiên FINAL_VAR trước (matcher check trước) vì tên nó dài hơn.
    """
    plain = _strip_repl_blocks(text)

    var = _match_balanced(plain, "FINAL_VAR")
    if var is not None:
        return ("var", var.strip().strip("'\"`"))

    direct = _match_balanced(plain, "FINAL")
    if direct is not None:
        return ("direct", direct.strip())

    return None
