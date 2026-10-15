"""
Konfigurationsmodul – Lädt Umgebungsvariablen und stellt sie als typisierte
Konstanten bereit.
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Discord & KI:Connect ──────────────────────────────────────────────────
DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
KICONNECT_API_KEY: str = os.getenv("KICONNECT_API_KEY", "")
KICONNECT_BASE_URL: str = os.getenv("KICONNECT_BASE_URL", "https://chat.kiconnect.nrw/api/v1")
KICONNECT_MODEL: str = os.getenv("KICONNECT_MODEL", "gpt-4o")
WEB_PORT: int = int(os.getenv("WEB_PORT", "8080"))

# ── Spezifische Channel-IDs für das 8er-Team ──────────────────────────────
CHANNEL_TERMINE: int = int(os.getenv("CHANNEL_TERMINE", "1560255601798291577"))
CHANNEL_ORGA_BOT: int = int(os.getenv("CHANNEL_ORGA_BOT", "1560255747986559027"))
CHANNEL_VORLESUNG_MATERIAL: int = int(os.getenv("CHANNEL_VORLESUNG_MATERIAL", "1560255397754048609"))
CHANNEL_MEETING_PROTOKOLLE: int = int(os.getenv("CHANNEL_MEETING_PROTOKOLLE", "1560255397754048610"))
CHANNEL_RESEARCH_LOG: int = int(os.getenv("CHANNEL_RESEARCH_LOG", "1560255397754048611"))
CHANNEL_PRAKTIKUM_QUIZ: int = int(os.getenv("CHANNEL_PRAKTIKUM_QUIZ", "1560255397754048605"))

# Fallback für Rückwärtskompatibilität
ORGA_CHANNEL_ID: int = int(os.getenv("ORGA_CHANNEL_ID", str(CHANNEL_ORGA_BOT)))

# ── Validierung ────────────────────────────────────────────────────────────
_MISSING: list[str] = []
if not DISCORD_TOKEN:
    _MISSING.append("DISCORD_TOKEN")
if not KICONNECT_API_KEY:
    _MISSING.append("KICONNECT_API_KEY")

if _MISSING:
    sys.exit(
        f"❌  Fehlende Umgebungsvariablen: {', '.join(_MISSING)}\n"
        "    → Überprüfe deine .env-Datei."
    )
