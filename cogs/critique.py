"""
Cog: /critique – Devil's Advocate / Kritischer Investor-Modus.

Bewertet eine Idee gnadenlos nach Desirability, Viability und Feasibility.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from ai_client import chat

log = logging.getLogger(__name__)

CRITIQUE_SYSTEM_PROMPT = (
    "Du bist ein kritischer, erfahrener Investor und Geschäftsstratege. "
    "Bewerte die folgende Geschäftsidee/Konzept gnadenlos und ehrlich anhand "
    "dieser drei Kriterien:\n\n"
    "## 1. 💛 Desirability (Kundenwert)\n"
    "- Gibt es ein echtes, nachweisbares Kundenproblem?\n"
    "- Wie validiert, oder wie stark angenommen ist der Bedarf?\n"
    "- Was ist das Value Proposition Canvas dafür?\n\n"
    "## 2. 💚 Viability (Markt & Rentabilität)\n"
    "- Existiert ein tragfähiges Geschäftsmodell?\n"
    "- Wie groß ist der TAM/SAM/SOM?\n"
    "- Wie differenziert sich die Idee vom Wettbewerb?\n\n"
    "## 3. 💙 Feasibility (Machbarkeit)\n"
    "- Welche technischen und organisatorischen Risiken bestehen?\n"
    "- Wie realistisch ist die Umsetzung mit begrenzten Ressourcen?\n"
    "- Welche kritischen Abhängigkeiten gibt es?\n\n"
    "## ⚠️ Logische Lücken & Blinde Flecken\n"
    "- Zeige logische Lücken, unbewiesene Annahmen und Widersprüche auf.\n"
    "- Stelle bohrende Folgefragen, die ein Prüfer/Dozent stellen würde.\n\n"
    "Sei direkt, sei hart, aber sei fair. "
    "Gib am Ende eine Gesamtbewertung (Stärken vs. Schwächen) und "
    "3 konkrete Verbesserungsvorschläge.\n"
    "Antworte auf Deutsch. Nutze Markdown-Formatierung."
)


class CritiqueCog(commands.Cog):
    """Devil's Advocate – Kritische Bewertung von Ideen."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="critique",
        description="Lass deine Idee von einem kritischen Investor zerlegen (Devil's Advocate).",
    )
    @app_commands.describe(
        idee_text="Deine Geschäftsidee, dein Konzept oder Pitch (Freitext)."
    )
    async def critique(self, interaction: discord.Interaction, idee_text: str) -> None:
        await interaction.response.defer(thinking=True)

        if len(idee_text.strip()) < 15:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Zu wenig Text",
                    description="Beschreibe deine Idee etwas ausführlicher (mindestens 2-3 Sätze).",
                    color=discord.Color.orange(),
                )
            )
            return

        try:
            critique = await chat(
                messages=[
                    {"role": "system", "content": CRITIQUE_SYSTEM_PROMPT},
                    {"role": "user", "content": idee_text},
                ],
                temperature=0.5,
                max_tokens=3000,
            )
        except RuntimeError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ KI-Fehler", description=str(exc), color=discord.Color.red(),
                )
            )
            return

        # ── Aufteilen auf Embeds (max 4096 chars) ──────────────────────────
        chunks = _split_text(critique, max_len=4096)
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title="😈 Devil's Advocate – Kritische Analyse" if i == 0 else "",
                description=chunk,
                color=discord.Color.dark_red(),
            )
            if i == 0:
                embed.set_author(name="Investor Review")
                embed.set_footer(
                    text=f"Angefordert von {interaction.user.display_name} · Nutzt es, um euren Pitch zu stählen!"
                )
            await interaction.followup.send(embed=embed)


def _split_text(text: str, max_len: int = 4096) -> list[str]:
    """Teilt einen langen Text an Zeilengrenzen in Chunks."""
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
    await bot.add_cog(CritiqueCog(bot))
