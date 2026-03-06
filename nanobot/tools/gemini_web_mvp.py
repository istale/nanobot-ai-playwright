"""Gemini Web MVP automation via Playwright (non-API mode)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from playwright.async_api import BrowserContext, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from nanobot.tools.gemini_web_selectors import (
    GEMINI_URL,
    INPUT_SELECTORS,
    RESPONSE_COUNT_SELECTORS,
    RESPONSE_SELECTORS,
    STOP_SELECTORS,
)
from nanobot.tools.web_controller import (
    CHROME_CDP_URL,
    cache_key,
    get_cached_context,
    get_last_input_selector,
    get_or_create_page,
    set_last_input_selector,
)


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

    key = cache_key(profile_dir, headless)

    if keep_browser_open:
        context = await get_cached_context(profile_dir, headless)
        page = await get_or_create_page(context, key)
        navigate = page.url == "" or GEMINI_URL not in page.url
    else:
        if CHROME_CDP_URL:
            context = await get_cached_context(profile_dir, headless)
            page = await get_or_create_page(context, key)
            return await _run_on_page(
                page,
                context,
                prompt,
                output_path,
                timeout_ms,
                _debug_dir,
                transient=False,
                navigate=(page.url == "" or GEMINI_URL not in page.url),
                key=key,
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
                key=key,
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
        key=key,
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
    key: tuple[str, bool] | None = None,
) -> str:
    if navigate:
        await page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=timeout_ms)

    input_selectors = list(INPUT_SELECTORS)
    if key:
        preferred = get_last_input_selector(key)
        if preferred:
            input_selectors = [preferred] + [s for s in input_selectors if s != preferred]

    prompt_box = None
    for selector in input_selectors:
        try:
            candidate = page.locator(selector).last
            await candidate.wait_for(state="visible", timeout=1000)
            prompt_box = candidate
            if key:
                set_last_input_selector(key, selector)
            break
        except PlaywrightTimeoutError:
            continue

    if prompt_box is None:
        await page.screenshot(path=str(debug_dir / "gemini-web-no-input.png"), full_page=True)
        if transient:
            await context.close()
        raise RuntimeError("Cannot find Gemini prompt box. Likely not logged in or page layout changed.")

    response_count_before = 0
    for sel in RESPONSE_COUNT_SELECTORS:
        try:
            response_count_before = max(response_count_before, await page.locator(sel).count())
        except Exception:
            pass

    await prompt_box.click()
    await prompt_box.fill(prompt)
    await prompt_box.press("Enter")

    async def _response_count() -> int:
        c = 0
        for sel in RESPONSE_COUNT_SELECTORS:
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

    async def _latest_response_text() -> str:
        for selector in RESPONSE_SELECTORS:
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
        for stop_sel in STOP_SELECTORS:
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
