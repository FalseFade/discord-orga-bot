"""
Cog: /recap – Smart Protocol Parser.

Maximiertes Token-Limit für lange Markdown-Protokolle.
Extrahiert Beschlüsse und ordnet To-Dos direkt Personen zu.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from ai_client import chat

log = logging.getLogger(__name__)

RECAP_SYSTEM_PROMPT = (
    "Du bist ein präziser, erfahrener Meeting-Assistent für ein studentisches 8er-Team. "
    "Analysiere den folgenden Protokoll-Text sorgfältig.\n\n"
    "Extrahiere und strukturiere die Ergebnisse in exakt diesem Format:\n\n"
    "## 📌 Beschlüsse\n"
    "- Liste jeden konkreten Beschluss auf, der im Protokoll gefasst wurde.\n"
    "- Nummeriere sie.\n\n"
    "## ✅ To-Dos mit Zuständigkeiten\n"
    "- Ordne jedes gefundene To-Do einer konkreten Person zu (soweit im Text erkennbar).\n"
    "- Format: `[ ] @Name: Aufgabenbeschreibung (bis Datum, falls genannt)`\n"
    "- Wenn keine Person zugeordnet werden kann, schreibe `@Team`.\n\n"
    "## ❓ Offene Fragen\n"
    "- Liste alle ungeklärten Punkte, offenen Diskussionen und Nachfolgethemen auf.\n\n"
    "## 📊 Zusammenfassung\n"
    "- Fasse den Gesamtkontext des Meetings in 2-3 Sätzen zusammen.\n\n"
    "REGELN:\n"
    "- Sei präzise, keine Informationen erfinden.\n"
    "- Wenn etwas unklar ist, markiere es als [unklar].\n"
    "- Antworte auf Deutsch. Nutze sauberes Markdown."
)


class RecapCog(commands.Cog):
    """Fasst Meeting-Protokolle mithilfe von KI:Connect zusammen."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="recap",
        description="Analysiere und fasse dein Meeting-Protokoll mit KI zusammen.",
    )
    @app_commands.describe(text="Dein Protokoll-Text (Markdown / Freitext – so lang wie nötig)")
    async def recap(self, interaction: discord.Interaction, text: str) -> None:
        await interaction.response.defer(thinking=True)

        if len(text.strip()) < 20:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Zu wenig Text",
                    description="Bitte gib mindestens einen kurzen Absatz ein.",
                    color=discord.Color.orange(),
                )
            )
            return

        try:
            summary = await chat(
                messages=[
                    {"role": "system", "content": RECAP_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                temperature=0.2,
                max_tokens=4096,  # Maximiert für lange Protokolle
            )
        except RuntimeError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ KI-Fehler", description=str(exc), color=discord.Color.red(),
                )
            )
            return

        # ── In Datenbank speichern ─────────────────────────────────────────
        await db.add_recap(
            original_text=text,
            summary=summary,
            created_by=interaction.user.display_name,
        )

        # ── Embed(s) senden ────────────────────────────────────────────────
        chunks = _split_text(summary, max_len=4096)
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="📝 Protokoll-Analyse" if i == 0 else "",
                description=chunk,
                color=discord.Color.teal(),
            )
            if i == 0:
                embed.set_footer(
                    text=f"Analysiert von KI:Connect · Angefordert von {interaction.user.display_name}"
                )
            await interaction.followup.send(embed=embed)


def _split_text(text: str, max_len: int = 4096) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RecapCog(bot))
