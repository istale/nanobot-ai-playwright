"""Gemini Web MVP automation via Playwright (non-API mode)."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import Playwright, async_playwright


GEMINI_URL = "https://gemini.google.com/app"
CHROME_CDP_URL = os.getenv("NANOBOT_CHROME_CDP_URL", "").strip()

_PLAYWRIGHT: Playwright | None = None
_CONTEXT_CACHE: dict[tuple[str, bool], BrowserContext] = {}
_PAGE_CACHE: dict[tuple[str, bool], Page] = {}
_LAST_INPUT_SELECTOR: dict[tuple[str, bool], str] = {}


async def _get_cached_context(profile_dir: Path, headless: bool) -> BrowserContext:
    global _PLAYWRIGHT
    key = (str(profile_dir), headless)
    existing = _CONTEXT_CACHE.get(key)
    if existing is not None:
        return existing

    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = await async_playwright().start()

    if CHROME_CDP_URL:
        browser = await _PLAYWRIGHT.chromium.connect_over_cdp(CHROME_CDP_URL)
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context(viewport={"width": 1400, "height": 1000})
    else:
        context = await _PLAYWRIGHT.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            viewport={"width": 1400, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )

    _CONTEXT_CACHE[key] = context
    return context


async def run_once(
    prompt: str,
    output_path: Path,
    *,
    headless: bool = False,
    timeout_ms: int = 120000,
    user_data_dir: Path | None = None,
    debug_dir: Path | None = None,
    keep_browser_open: bool = False,
) -> str:
    """Run one Gemini web prompt and persist the raw response text."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile_dir = user_data_dir or (Path.home() / ".nanobot" / "profiles" / "gemini-web")
    profile_dir.mkdir(parents=True, exist_ok=True)

    _debug_dir = debug_dir or Path("outputs")
    _debug_dir.mkdir(parents=True, exist_ok=True)

    context: BrowserContext | None = None
    page: Page | None = None
    transient = (not keep_browser_open) and (not CHROME_CDP_URL)

    if keep_browser_open:
        context = await _get_cached_context(profile_dir, headless)
        key = (str(profile_dir), headless)
        page = _PAGE_CACHE.get(key)
        if page is None or page.is_closed():
            page = context.pages[0] if context.pages else await context.new_page()
            _PAGE_CACHE[key] = page
        navigate = page.url == "" or "gemini.google.com" not in page.url
    else:
        if CHROME_CDP_URL:
            context = await _get_cached_context(profile_dir, headless)
            page = context.pages[0] if context.pages else await context.new_page()
            return await _run_on_page(
                page,
                context,
                prompt,
                output_path,
                timeout_ms,
                _debug_dir,
                transient=False,
                navigate=True,
            )

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(profile_dir),
                headless=headless,
                viewport={"width": 1400, "height": 1000},
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else await context.new_page()
            return await _run_on_page(
                page,
                context,
                prompt,
                output_path,
                timeout_ms,
                _debug_dir,
                transient=True,
                navigate=True,
            )

    return await _run_on_page(
        page,
        context,
        prompt,
        output_path,
        timeout_ms,
        _debug_dir,
        transient=transient,
        navigate=navigate,
    )


async def _run_on_page(
    page: Page,
    context: BrowserContext,
    prompt: str,
    output_path: Path,
    timeout_ms: int,
    debug_dir: Path,
    *,
    transient: bool,
    navigate: bool,
) -> str:
    if navigate:
        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=timeout_ms)

    key = None
    for k, v in _PAGE_CACHE.items():
        if v is page:
            key = k
            break

    input_selectors = [
        "textarea[aria-label*='Enter a prompt']",
        "textarea[aria-label*='prompt']",
        "textarea[placeholder*='Enter a prompt']",
        "textarea",
        "div[contenteditable='true'][role='textbox']",
        "div[contenteditable='true'][aria-label*='prompt']",
    ]
    if key and key in _LAST_INPUT_SELECTOR:
        preferred = _LAST_INPUT_SELECTOR[key]
        input_selectors = [preferred] + [s for s in input_selectors if s != preferred]

    prompt_box = None
    for selector in input_selectors:
        try:
            candidate = page.locator(selector).last
            await candidate.wait_for(state="visible", timeout=1000)
            prompt_box = candidate
            if key:
                _LAST_INPUT_SELECTOR[key] = selector
            break
        except PlaywrightTimeoutError:
            continue

    if prompt_box is None:
        await page.screenshot(path=str(debug_dir / "gemini-web-no-input.png"), full_page=True)
        if transient:
            await context.close()
        raise RuntimeError("Cannot find Gemini prompt box. Likely not logged in or page layout changed.")

    response_count_before = 0
    for sel in ["model-response", "[data-test-id='response-container']", "message-content"]:
        try:
            response_count_before = max(response_count_before, await page.locator(sel).count())
        except Exception:
            pass

    await prompt_box.click()
    await prompt_box.fill(prompt)
    await prompt_box.press("Enter")

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
            break
        await page.wait_for_timeout(300)
    else:
        await page.screenshot(path=str(debug_dir / "gemini-web-timeout.png"), full_page=True)
        if transient:
            await context.close()
        raise RuntimeError("Timed out waiting for Gemini response completion.")

    response_selectors = [
        "model-response .markdown",
        "model-response",
        "[data-test-id='response-container'] .markdown",
        "[data-test-id='response-container']",
        "message-content .markdown",
    ]

    async def _latest_response_text() -> str:
        for selector in response_selectors:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                continue
            text = (await locator.nth(count - 1).inner_text()).strip()
            if text:
                return text
        return ""

    # Wait until streaming appears settled: stop button gone and text stable.
    extracted = ""
    stable_ticks = 0
    last_text = ""
    while asyncio.get_event_loop().time() < deadline:
        cur_text = await _latest_response_text()
        if cur_text and cur_text == last_text:
            stable_ticks += 1
        else:
            stable_ticks = 0
        last_text = cur_text or last_text

        stop_visible = False
        for stop_sel in ["button:has-text('Stop generating')", "button[aria-label*='Stop']"]:
            try:
                stop_visible = stop_visible or await page.locator(stop_sel).first.is_visible(timeout=100)
            except Exception:
                pass

        if last_text and stable_ticks >= 4 and not stop_visible:
            extracted = last_text
            break

        await page.wait_for_timeout(500)

    if not extracted:
        await page.screenshot(path=str(debug_dir / "gemini-web-no-extract.png"), full_page=True)
        if transient:
            await context.close()
        raise RuntimeError("Gemini response found but could not extract text.")

    output_path.write_text(extracted, encoding="utf-8")
    if transient:
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
    keep_browser_open: bool = False,
) -> str:
    return asyncio.run(
        run_once(
            prompt=prompt,
            output_path=output_path,
            headless=headless,
            timeout_ms=timeout_ms,
            user_data_dir=user_data_dir,
            keep_browser_open=keep_browser_open,
        )
    )
