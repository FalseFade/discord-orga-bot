#!/usr/bin/env python3
"""
ORGA Bot – Discord-Assistenz für ein studentisches 8er-Team.

Slash-Commands:
  /meeting         – Meeting planen mit automatischen Erinnerungen (Kanal + DM)
  /recap           – Smart Protocol Parser (Beschlüsse, To-Dos mit Personen, offene Fragen)
  /quiz            – Quizfrage zu Vorlesungsinhalten generieren & bewerten
  /delegate        – Projektziel in Unteraufgaben zerlegen und rotierend im Team zuweisen
  /task-done       – Eigene Aufgabe als erledigt markieren
  /my-tasks        – Offene Aufgaben anzeigen
  /critique        – Devil's Advocate / Kritischer Investor Modus
  /dm-all          – Nachricht per DM an alle Mitglieder senden
  /meeting-dm      – Nächstes Meeting per DM an alle erinnern
  /standup-ask     – Tägliche Stand-up Frage jetzt manuell per DM senden
  /standup-summary – Heutige Stand-up Zusammenfassung im Orga-Kanal posten

Web-Dashboard:
  Läuft parallel auf http://localhost:8080 (konfigurierbar via WEB_PORT)
  - Dashboard mit Stats & Countdown
  - Task Board (Kanban / Listenansicht pro User & Projekt)
  - Stand-up Monitor (Fokus, Blocker & Abgabe-Quote)
  - Meetings Manager mit 1-Klick DM Broadcast
  - Recaps Archiv

Starten:
  python bot.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

import discord
from aiohttp import web
from discord.ext import commands

import database as db
from config import DISCORD_TOKEN, WEB_PORT
from web_server import create_web_app

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("orga-bot")

# ── Bot-Setup ──────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True   # Für Nachrichten & Protokolle
intents.members = True           # Für Mitglieder-Listen & DM-Broadcasts

bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    description="ORGA Bot – Autonomer Projektmanager für 8er-Teams",
)

# ── Cogs ───────────────────────────────────────────────────────────────────
EXTENSIONS = [
    "cogs.meeting",
    "cogs.recap",
    "cogs.quiz",
    "cogs.notify",
    "cogs.delegate",
    "cogs.critique",
    "cogs.team",
]


@bot.event
async def on_ready() -> None:
    log.info("✅ Eingeloggt als %s (ID: %s)", bot.user, bot.user.id)  # type: ignore[union-attr]
    log.info("📡 Verbunden mit %d Server(n)", len(bot.guilds))

    for guild in bot.guilds:
        members_count = sum(1 for m in guild.members if not m.bot)
        log.info("   └── %s (%d echte Mitglieder)", guild.name, members_count)

    # Slash-Commands global synchronisieren
    try:
        synced = await bot.tree.sync()
        log.info("🔄 %d Slash-Command(s) synchronisiert", len(synced))
    except Exception:
        log.exception("Fehler beim Sync der Slash-Commands")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Globaler Error-Handler für Prefix-Commands."""
    log.error("Command-Fehler: %s", error)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: discord.app_commands.AppCommandError,
) -> None:
    """Globaler Error-Handler für Slash-Commands."""
    log.exception("Slash-Command-Fehler", exc_info=error)
    embed = discord.Embed(
        title="❌ Ein Fehler ist aufgetreten",
        description=f"```{error}```",
        color=discord.Color.red(),
    )
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def main() -> None:
    # ── Datenbank initialisieren ───────────────────────────────────────────
    await db.init_db()

    async with bot:
        # ── Extensions laden ───────────────────────────────────────────────
        for ext in EXTENSIONS:
            try:
                await bot.load_extension(ext)
                log.info("📦 Extension geladen: %s", ext)
            except Exception:
                log.exception("Fehler beim Laden von %s", ext)
                sys.exit(1)

        # ── Web-Dashboard starten ──────────────────────────────────────────
        from cogs.meeting import scheduler

        web_app = await create_web_app(bot, scheduler)
        runner = web.AppRunner(web_app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", WEB_PORT)
        await site.start()
        log.info("🌐 Web-Dashboard online: http://localhost:%d", WEB_PORT)

        # ── Bot starten ────────────────────────────────────────────────────
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
