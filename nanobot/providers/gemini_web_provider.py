"""Gemini Web provider (non-API) backed by Playwright browser automation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.tools.gemini_web_mvp import run_once


class GeminiWebProvider(LLMProvider):
    """Provider that uses Gemini web UI instead of API."""

    def __init__(
        self,
        user_data_dir: Path | None = None,
        headless: bool = False,
        timeout_ms: int = 120000,
        output_dir: Path | None = None,
    ):
        super().__init__(api_key=None, api_base=None)
        self.user_data_dir = user_data_dir or (Path.home() / ".nanobot" / "profiles" / "gemini-web")
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.output_dir = output_dir or Path("outputs")

    def get_default_model(self) -> str:
        return "gemini_web/default"

    @staticmethod
    def _to_text(content: Any) -> str:
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text)
                elif isinstance(item, str) and item.strip():
                    parts.append(item)
            return "\n".join(parts)
        if isinstance(content, dict):
            text = content.get("text")
            return text if isinstance(text, str) else ""
        return str(content)

    def _build_prompt(self, messages: list[dict[str, Any]]) -> str:
        # Keep context, but ensure final user intent is present.
        lines: list[str] = []
        for msg in messages[-12:]:
            role = msg.get("role", "user")
            text = self._to_text(msg.get("content")).strip()
            if not text:
                continue
            if role == "system":
                lines.append(f"[system]\n{text}")
            elif role == "assistant":
                lines.append(f"[assistant]\n{text}")
            else:
                lines.append(f"[user]\n{text}")

        if not lines:
            return "Hello"
        return "\n\n".join(lines)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        del tools, model, max_tokens, temperature, reasoning_effort  # Not supported in web mode.

        prompt = self._build_prompt(messages)
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        output_path = self.output_dir / f"gemini-web-provider-{ts}.txt"

        content = await run_once(
            prompt=prompt,
            output_path=output_path,
            headless=self.headless,
            timeout_ms=self.timeout_ms,
            user_data_dir=self.user_data_dir,
            keep_browser_open=True,
        )

        usage = {
            "prompt_tokens": len(prompt),
            "completion_tokens": len(content),
            "total_tokens": len(prompt) + len(content),
        }
        return LLMResponse(content=content, finish_reason="stop", usage=usage)
