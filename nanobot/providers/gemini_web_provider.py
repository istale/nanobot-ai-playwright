"""Gemini Web provider (non-API) backed by Playwright browser automation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.tools.gemini_web_mvp import run_once


class GeminiWebProvider(LLMProvider):
    """Provider that uses Gemini web UI instead of API."""

    TOOL_CALL_PATTERN = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)

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
        self._seeded_system_prompt = False

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

    def _build_prompt(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> str:
        """First turn includes system+tool protocol; later turns send user or tool-result context."""
        latest_user = ""
        latest_system = ""
        latest_tool_result = ""

        for msg in reversed(messages):
            role = msg.get("role")
            text = self._to_text(msg.get("content")).strip()
            if not text:
                continue
            if not latest_user and role == "user":
                latest_user = text
            elif not latest_system and role == "system":
                latest_system = text
            elif not latest_tool_result and role == "tool":
                latest_tool_result = text
            if latest_user and latest_system and latest_tool_result:
                break

        if not latest_user:
            latest_user = "Hello"

        tool_protocol = ""
        if tools:
            names = [t.get("function", {}).get("name", "") for t in tools if isinstance(t, dict)]
            names = [n for n in names if n]
            if names:
                tool_protocol = (
                    "\n\n[TOOL_CALL_PROTOCOL]\n"
                    "When you need a tool, output EXACTLY one XML block and nothing else before it:\n"
                    "<tool_call>{\"name\":\"<tool_name>\",\"arguments\":{...}}</tool_call>\n"
                    f"Allowed tools: {', '.join(names)}\n"
                    "If no tool needed, reply normally."
                )

        if not self._seeded_system_prompt and latest_system:
            self._seeded_system_prompt = True
            return (
                f"[SYSTEM INSTRUCTION - APPLY THIS STYLE FOR THIS CHAT]\n{latest_system}"
                f"{tool_protocol}\n\n[USER]\n{latest_user}"
            )

        if latest_tool_result:
            return (
                f"[USER]\n{latest_user}\n\n"
                f"[TOOL_RESULT]\n{latest_tool_result}\n\n"
                "Use the tool result to continue and answer the user."
            )

        return latest_user

    def _extract_tool_calls(self, content: str) -> tuple[str | None, list[ToolCallRequest]]:
        calls: list[ToolCallRequest] = []
        cleaned = content
        for m in self.TOOL_CALL_PATTERN.finditer(content or ""):
            raw = m.group(1)
            try:
                data = json.loads(raw)
                name = str(data.get("name", "")).strip()
                arguments = data.get("arguments", {})
                if name and isinstance(arguments, dict):
                    calls.append(ToolCallRequest(id=f"tw_{uuid4().hex[:12]}", name=name, arguments=arguments))
            except Exception:
                continue

        if calls:
            cleaned = self.TOOL_CALL_PATTERN.sub("", cleaned).strip() or None
        return cleaned, calls

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        del model, max_tokens, temperature, reasoning_effort  # Not supported in web mode.

        prompt = self._build_prompt(messages, tools=tools)
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

        cleaned, tool_calls = self._extract_tool_calls(content)
        usage = {
            "prompt_tokens": len(prompt),
            "completion_tokens": len(content),
            "total_tokens": len(prompt) + len(content),
        }
        if tool_calls:
            return LLMResponse(content=cleaned, tool_calls=tool_calls, finish_reason="tool_calls", usage=usage)
        return LLMResponse(content=cleaned or content, finish_reason="stop", usage=usage)
