"""Gemini Web MVP automation via Playwright (non-API mode)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


GEMINI_URL = "https://gemini.google.com/app"


async def run_once(
    prompt: str,
    output_path: Path,
    *,
    headless: bool = False,
    timeout_ms: int = 120000,
    user_data_dir: Path | None = None,
    debug_dir: Path | None = None,
) -> str:
    """Run one Gemini web prompt and persist the raw response text."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile_dir = user_data_dir or (Path.home() / ".nanobot" / "profiles" / "gemini-web")
    profile_dir.mkdir(parents=True, exist_ok=True)

    _debug_dir = debug_dir or Path("outputs")
    _debug_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            viewport={"width": 1400, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=timeout_ms)

        input_selectors = [
            "textarea[aria-label*='Enter a prompt']",
            "textarea[aria-label*='prompt']",
            "textarea[placeholder*='Enter a prompt']",
            "textarea",
            "div[contenteditable='true'][role='textbox']",
            "div[contenteditable='true'][aria-label*='prompt']",
        ]

        prompt_box = None
        for selector in input_selectors:
            try:
                candidate = page.locator(selector).last
                await candidate.wait_for(state="visible", timeout=6000)
                prompt_box = candidate
                break
            except PlaywrightTimeoutError:
                continue

        if prompt_box is None:
            await page.screenshot(path=str(_debug_dir / "gemini-web-no-input.png"), full_page=True)
            await context.close()
            raise RuntimeError(
                "Cannot find Gemini prompt box. Likely not logged in or page layout changed."
            )

        response_count_before = 0
        for sel in ["model-response", "[data-test-id='response-container']", "message-content"]:
            try:
                response_count_before = max(response_count_before, await page.locator(sel).count())
            except Exception:
                pass

        await prompt_box.click()
        await prompt_box.fill(prompt)
        await prompt_box.press("Enter")

        # Wait for one new response block to appear, then settle briefly.
        async def _response_count() -> int:
            c = 0
            for sel in ["model-response", "[data-test-id='response-container']", "message-content"]:
                try:
                    c = max(c, await page.locator(sel).count())
                except Exception:
                    pass
            return c

        deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
        while asyncio.get_event_loop().time() < deadline:
            if await _response_count() > response_count_before:
                await page.wait_for_timeout(1200)
                break
            await page.wait_for_timeout(300)
        else:
            await page.screenshot(path=str(_debug_dir / "gemini-web-timeout.png"), full_page=True)
            await context.close()
            raise RuntimeError("Timed out waiting for Gemini response completion.")

        response_selectors = [
            "model-response .markdown",
            "model-response",
            "[data-test-id='response-container'] .markdown",
            "[data-test-id='response-container']",
            "message-content .markdown",
        ]

        extracted = ""
        for selector in response_selectors:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                continue
            text = (await locator.nth(count - 1).inner_text()).strip()
            if text:
                extracted = text
                break

        if not extracted:
            await page.screenshot(path=str(_debug_dir / "gemini-web-no-extract.png"), full_page=True)
            await context.close()
            raise RuntimeError("Gemini response found but could not extract text.")

        output_path.write_text(extracted, encoding="utf-8")
        await context.close()
        return extracted


def default_output_path() -> Path:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return Path("outputs") / f"gemini-web-{ts}.txt"


def run_sync(
    prompt: str,
    output_path: Path,
    *,
    headless: bool = False,
    timeout_ms: int = 120000,
    user_data_dir: Path | None = None,
) -> str:
    return asyncio.run(
        run_once(
            prompt=prompt,
            output_path=output_path,
            headless=headless,
            timeout_ms=timeout_ms,
            user_data_dir=user_data_dir,
        )
    )
