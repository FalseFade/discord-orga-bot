"""
KI:Connect API-Client – Wrapper um openai.AsyncOpenAI mit angepasster base_url.
"""

from __future__ import annotations

import logging
from openai import AsyncOpenAI

from config import KICONNECT_API_KEY, KICONNECT_BASE_URL, KICONNECT_MODEL

log = logging.getLogger(__name__)

# Einmalig initialisierter Async-Client (wird im gesamten Bot geteilt)
client = AsyncOpenAI(
    api_key=KICONNECT_API_KEY,
    base_url=KICONNECT_BASE_URL,
)


async def chat(
    messages: list[dict[str, str]],
    *,
    model: str = KICONNECT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Sendet eine Chat-Completion-Anfrage an KI:Connect und gibt die Antwort zurück."""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        return content.strip() if content else "(Keine Antwort von der KI erhalten.)"
    except Exception as exc:
        log.exception("KI:Connect API-Fehler")
        raise RuntimeError(f"KI:Connect API-Fehler: {exc}") from exc
