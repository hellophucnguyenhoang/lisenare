"""Wrapper mỏng cho Gemini API (vendor từ project RLM, dùng settings của lisenare)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable

from google import genai
from google.genai import types

from app.config import settings

from . import config


@dataclass
class TokenStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    def add(self, in_tok: int, out_tok: int) -> None:
        self.prompt_tokens += in_tok
        self.completion_tokens += out_tok
        self.calls += 1


@dataclass
class GeminiClient:
    model_name: str = config.ROOT_MODEL
    stats: TokenStats = field(default_factory=TokenStats)

    def __post_init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)

    @staticmethod
    def _to_gemini_contents(history: Iterable[dict]) -> list[types.Content]:
        out: list[types.Content] = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            out.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=turn["content"])],
                )
            )
        return out

    def _record_usage(self, resp) -> None:
        usage = getattr(resp, "usage_metadata", None)
        if usage is None:
            self.stats.add(0, 0)
            return
        in_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
        out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
        self.stats.add(in_tok, out_tok)

    @staticmethod
    def _extract_text(resp) -> str:
        text = getattr(resp, "text", None)
        if text:
            return text
        try:
            parts = resp.candidates[0].content.parts
            return "".join(getattr(p, "text", "") for p in parts if getattr(p, "text", None))
        except Exception:
            return ""

    def generate(self, history: list[dict], system_prompt: str) -> str:
        contents = self._to_gemini_contents(history)
        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=config.MAX_LLM_OUTPUT_TOKENS,
            temperature=0.2,
        )
        last_err: Exception | None = None
        for attempt in range(config.LLM_RETRY_ATTEMPTS):
            try:
                resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=gen_config,
                )
                self._record_usage(resp)
                return self._extract_text(resp)
            except Exception as err:  # noqa: BLE001
                last_err = err
                print(f"  [GeminiClient.generate] lần thử {attempt + 1} thất bại: {err}")
                if attempt < config.LLM_RETRY_ATTEMPTS - 1:
                    time.sleep(config.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise RuntimeError(f"Gemini generate thất bại sau retry: {last_err}")

    def simple_query(self, prompt: str) -> str:
        """Gọi LLM một lần không cần system prompt — dùng cho llm_query trong REPL."""
        gen_config = types.GenerateContentConfig(
            max_output_tokens=config.MAX_LLM_OUTPUT_TOKENS,
            temperature=0.2,
        )
        last_err: Exception | None = None
        for attempt in range(config.LLM_RETRY_ATTEMPTS):
            try:
                resp = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=gen_config,
                )
                self._record_usage(resp)
                return self._extract_text(resp)
            except Exception as err:  # noqa: BLE001
                last_err = err
                print(f"  [GeminiClient.simple_query] lần thử {attempt + 1} thất bại: {err}")
                if attempt < config.LLM_RETRY_ATTEMPTS - 1:
                    time.sleep(config.LLM_RETRY_BACKOFF_SECONDS * (attempt + 1))
        raise RuntimeError(f"Gemini simple_query thất bại: {last_err}")
