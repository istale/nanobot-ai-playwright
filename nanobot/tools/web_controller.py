"""Browser/context/page control for web-driven providers."""

from __future__ import annotations

import os
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

CHROME_CDP_URL = os.getenv("NANOBOT_CHROME_CDP_URL", "").strip()

_PLAYWRIGHT: Playwright | None = None
_CONTEXT_CACHE: dict[tuple[str, bool], BrowserContext] = {}
_PAGE_CACHE: dict[tuple[str, bool], Page] = {}
_LAST_INPUT_SELECTOR: dict[tuple[str, bool], str] = {}


def cache_key(profile_dir: Path, headless: bool) -> tuple[str, bool]:
    return (str(profile_dir), headless)


def get_last_input_selector(key: tuple[str, bool]) -> str | None:
    return _LAST_INPUT_SELECTOR.get(key)


def set_last_input_selector(key: tuple[str, bool], selector: str) -> None:
    _LAST_INPUT_SELECTOR[key] = selector


async def _get_playwright() -> Playwright:
    global _PLAYWRIGHT
    if _PLAYWRIGHT is None:
        _PLAYWRIGHT = await async_playwright().start()
    return _PLAYWRIGHT


async def get_cached_context(profile_dir: Path, headless: bool) -> BrowserContext:
    key = cache_key(profile_dir, headless)
    existing = _CONTEXT_CACHE.get(key)
    if existing is not None:
        return existing

    p = await _get_playwright()
    if CHROME_CDP_URL:
        browser = await p.chromium.connect_over_cdp(CHROME_CDP_URL)
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = await browser.new_context(viewport={"width": 1400, "height": 1000})
    else:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            headless=headless,
            viewport={"width": 1400, "height": 1000},
            args=["--disable-blink-features=AutomationControlled"],
        )

    _CONTEXT_CACHE[key] = context
    return context


async def get_or_create_page(context: BrowserContext, key: tuple[str, bool]) -> Page:
    page = _PAGE_CACHE.get(key)
    if page is None or page.is_closed():
        page = context.pages[0] if context.pages else await context.new_page()
        _PAGE_CACHE[key] = page
    return page
