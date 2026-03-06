"""Site profile/selectors for Gemini web style chat pages."""

from __future__ import annotations

GEMINI_URL = "https://gemini.google.com/app"

INPUT_SELECTORS = [
    "textarea[aria-label*='Enter a prompt']",
    "textarea[aria-label*='prompt']",
    "textarea[placeholder*='Enter a prompt']",
    "textarea",
    "div[contenteditable='true'][role='textbox']",
    "div[contenteditable='true'][aria-label*='prompt']",
]

RESPONSE_COUNT_SELECTORS = [
    "model-response",
    "[data-test-id='response-container']",
    "message-content",
]

RESPONSE_SELECTORS = [
    "model-response .markdown",
    "model-response",
    "[data-test-id='response-container'] .markdown",
    "[data-test-id='response-container']",
    "message-content .markdown",
]

STOP_SELECTORS = [
    "button:has-text('Stop generating')",
    "button[aria-label*='Stop']",
]
