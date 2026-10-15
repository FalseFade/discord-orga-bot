"""
Cog: /quiz – Interaktives Quiz zu Vorlesungsmaterialien.

Liest lokale Text-/PDF-Dateien aus dem Ordner `data/` und generiert über
KI:Connect eine fordernde Verständnisfrage.  Der Nutzer kann per Button
antworten, und die KI bewertet die Antwort kritisch.
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path

import discord
from discord import app_commands, ui
from discord.ext import commands

from ai_client import chat

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

QUIZ_SYSTEM_PROMPT = (
    "Du bist ein anspruchsvoller Professor für Organisation & Projektmanagement (OPM, FH Aachen, Dr. Axel Emunds). "
    "Dir liegen die folgenden Vorlesungsinhalte und Skripte vor:\n\n"
    "{context}\n\n"
    "Stelle dem Studierenden EINE zufällige, fordernde Verständnis- oder Anwendungsfrage zu "
    "den Inhalten (z. B. zu ZESPORT-Kriterien, Kuster-Matrix, Tuckman-Phasen, Belbin-Rollen, "
    "Auftragsklärung nach Dr. Emunds, Arbeit im vs. am System, DIN 69901 / ISO 21500, "
    "Gewinner-Gewinner-Modell, Projektgrößen nach Jakoby, AFB I-III). "
    "Die Frage soll zum Nachdenken anregen und nicht trivial sein. "
    "Gib NUR die Frage aus – keine Antwort, keine Erklärung."
)

EVAL_SYSTEM_PROMPT = (
    "Du bist ein kritischer Professor für Organisation & Projektmanagement (OPM, FH Aachen). "
    "Bewerte die folgende Antwort des Studierenden auf die Frage.\n\n"
    "**Frage:** {question}\n\n"
    "**Antwort des Studierenden:** {answer}\n\n"
    "Gib eine kritische, aber faire Bewertung ab. "
    "Erkläre präzise, was fachlich richtig ist und was fehlt oder ungenau war (orientiert an Dr. Emunds / OPM). "
    "Gib am Ende eine Note (1-6, deutsches Notensystem) und eine kurze Begründung. "
    "Antworte auf Deutsch."
)


def _load_materials() -> str:
    """Lädt alle .txt-, .md- und .pdf-Dateien aus data/ und gibt den Text zurück."""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return ""

    texts: list[str] = []

    for file in sorted(DATA_DIR.iterdir()):
        try:
            if file.suffix.lower() in (".txt", ".md"):
                texts.append(file.read_text(encoding="utf-8"))
            elif file.suffix.lower() == ".pdf":
                texts.append(_extract_pdf(file))
        except Exception:
            log.exception("Fehler beim Lesen von %s", file)

    return "\n\n---\n\n".join(texts)


def _extract_pdf(path: Path) -> str:
    """Extrahiert Text aus einer PDF-Datei mit PyPDF2."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        log.warning("PyPDF2 nicht installiert – PDF %s wird übersprungen.", path)
        return ""

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n".join(pages)


# ── Answer-Modal (Pop-up zum Antworten) ───────────────────────────────────

class AnswerModal(ui.Modal, title="Deine Antwort"):
    """Modal-Dialog, in dem der Studierende seine Antwort eintippen kann."""

    answer = ui.TextInput(
        label="Antwort",
        style=discord.TextStyle.paragraph,
        placeholder="Schreibe deine Antwort hier...",
        required=True,
        max_length=2000,
    )

    def __init__(self, question: str) -> None:
        super().__init__(timeout=300)  # 5 Minuten
        self.question = question

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        try:
            evaluation = await chat(
                messages=[
                    {
                        "role": "system",
                        "content": EVAL_SYSTEM_PROMPT.format(
                            question=self.question,
                            answer=self.answer.value,
                        ),
                    },
                    {"role": "user", "content": self.answer.value},
                ],
                temperature=0.4,
            )
        except RuntimeError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ KI-Fehler bei der Bewertung",
                    description=str(exc),
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="📊 Bewertung deiner Antwort",
            description=evaluation,
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="❓ Frage",
            value=self.question[:1024],
            inline=False,
        )
        embed.add_field(
            name="💬 Deine Antwort",
            value=self.answer.value[:1024],
            inline=False,
        )
        embed.set_footer(text=f"Quiz von {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)


# ── Answer-Button-View ────────────────────────────────────────────────────

class AnswerView(ui.View):
    """View mit einem Button, der das Antwort-Modal öffnet."""

    def __init__(self, question: str) -> None:
        super().__init__(timeout=300)
        self.question = question

    @ui.button(label="✍️ Antworten", style=discord.ButtonStyle.primary)
    async def answer_button(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        await interaction.response.send_modal(AnswerModal(self.question))

    async def on_timeout(self) -> None:
        # Buttons deaktivieren nach Timeout
        for child in self.children:
            if isinstance(child, ui.Button):
                child.disabled = True


# ── Cog ───────────────────────────────────────────────────────────────────

class QuizCog(commands.Cog):
    """Generiert Quizfragen basierend auf Vorlesungsmaterialien."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.materials: str = _load_materials()
        if not self.materials:
            log.warning(
                "⚠️  Keine Vorlesungsmaterialien in %s gefunden. "
                "Lege .txt- oder .pdf-Dateien dort ab.",
                DATA_DIR,
            )

    @app_commands.command(
        name="quiz",
        description="Bekomme eine Quizfrage zu den Vorlesungsinhalten.",
    )
    async def quiz(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        if not self.materials:
            # Materialien erneut laden (evtl. inzwischen hinzugefügt)
            self.materials = _load_materials()

        if not self.materials:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📂 Keine Materialien gefunden",
                    description=(
                        f"Lege `.txt`- oder `.pdf`-Dateien in den Ordner "
                        f"`{DATA_DIR}` und versuche es erneut."
                    ),
                    color=discord.Color.orange(),
                )
            )
            return

        # Kontext kürzen falls nötig (max ~6000 Zeichen für Prompt)
        context = self.materials
        if len(context) > 6000:
            # Zufälligen Ausschnitt wählen für Variation
            start = random.randint(0, len(context) - 6000)
            context = context[start : start + 6000]

        try:
            question = await chat(
                messages=[
                    {
                        "role": "system",
                        "content": QUIZ_SYSTEM_PROMPT.format(context=context),
                    },
                    {"role": "user", "content": "Stelle mir eine Quizfrage."},
                ],
                temperature=0.9,
            )
        except RuntimeError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ KI-Fehler",
                    description=str(exc),
                    color=discord.Color.red(),
                ),
            )
            return

        embed = discord.Embed(
            title="🎓 Quiz – Organisation & Projektmanagement (OPM)",
            description=question,
            color=discord.Color.purple(),
        )
        embed.set_footer(text="Klicke auf den Button, um zu antworten. Du hast 5 Minuten.")

        view = AnswerView(question)
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(QuizCog(bot))
