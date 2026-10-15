"""
Cog: /delegate – Proaktive KI-gestützte Aufgabenverteilung.

Zerlegt ein Projektziel via KI:Connect in Unteraufgaben und weist sie
rotierend den Server-Mitgliedern zu.
"""

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

import database as db
from ai_client import chat

log = logging.getLogger(__name__)

DELEGATE_SYSTEM_PROMPT = (
    "Du bist ein erfahrener Projektmanager für ein studentisches 8er-Team. "
    "Zerlege das folgende Projektziel in sinnvolle, konkrete Unteraufgaben.\n\n"
    "REGELN:\n"
    "- Erstelle zwischen 4 und 16 Aufgaben, je nach Komplexität.\n"
    "- Jede Aufgabe muss klar, konkret und in 1-2 Sätzen beschrieben sein.\n"
    "- Gib die Aufgaben als nummerierte Liste zurück, EINE Aufgabe pro Zeile:\n"
    "  1. [Aufgabenbeschreibung]\n"
    "  2. [Aufgabenbeschreibung]\n"
    "  ...\n"
    "- Gib NUR die nummerierte Liste aus, keine Einleitung, keine Zusammenfassung.\n"
    "- Antworte auf Deutsch."
)


def _parse_tasks(ai_response: str) -> list[str]:
    """Extrahiert einzelne Aufgaben aus der KI-Antwort."""
    tasks: list[str] = []
    for line in ai_response.strip().split("\n"):
        line = line.strip()
        # Zeilen wie "1. Aufgabe" oder "- Aufgabe" oder "• Aufgabe"
        match = re.match(r"^(?:\d+[\.\)]\s*|[-•]\s*)(.*)", line)
        if match:
            task = match.group(1).strip()
            if len(task) > 5:  # Mindestlänge
                tasks.append(task)
    return tasks


class DelegateCog(commands.Cog):
    """Zerlegt Projektziele in Aufgaben und verteilt sie im Team."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="delegate",
        description="Zerlege ein Projektziel in Aufgaben und verteile sie im Team.",
    )
    @app_commands.describe(
        projekt_ziel="Das Projektziel, das in Aufgaben zerlegt werden soll.",
        deadline='Optionale Deadline für alle Aufgaben (z. B. "25.10.2026")',
    )
    async def delegate(
        self,
        interaction: discord.Interaction,
        projekt_ziel: str,
        deadline: str | None = None,
    ) -> None:
        await interaction.response.defer(thinking=True)

        if not interaction.guild:
            await interaction.followup.send("❌ Nur auf Servern verfügbar.", ephemeral=True)
            return

        # ── Mitglieder sammeln ─────────────────────────────────────────────
        members = [m for m in interaction.guild.members if not m.bot]
        if not members:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Keine Mitglieder gefunden",
                    description="Server Members Intent muss aktiviert sein.",
                    color=discord.Color.orange(),
                )
            )
            return

        # ── KI-Aufgabenzerlegung ───────────────────────────────────────────
        try:
            ai_response = await chat(
                messages=[
                    {"role": "system", "content": DELEGATE_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Projektziel: {projekt_ziel}"},
                ],
                temperature=0.6,
                max_tokens=2048,
            )
        except RuntimeError as exc:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ KI-Fehler", description=str(exc), color=discord.Color.red(),
                )
            )
            return

        tasks = _parse_tasks(ai_response)
        if not tasks:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Keine Aufgaben erkannt",
                    description=f"Die KI-Antwort konnte nicht geparst werden:\n```\n{ai_response[:1000]}\n```",
                    color=discord.Color.orange(),
                )
            )
            return

        # ── Round-Robin-Zuweisung ──────────────────────────────────────────
        assignments: list[dict] = []
        for i, task_desc in enumerate(tasks):
            member = members[i % len(members)]
            task_id = await db.add_task(
                user_id=member.id,
                user_name=member.display_name,
                task_desc=task_desc,
                project=projekt_ziel[:100],
                deadline=deadline,
            )
            assignments.append({
                "id": task_id,
                "task": task_desc,
                "member": member,
            })

        # ── Ergebnis-Embed ─────────────────────────────────────────────────
        embed = discord.Embed(
            title="📋 Aufgaben verteilt!",
            description=f"**Projekt:** {projekt_ziel}\n**{len(tasks)} Aufgaben** an **{len(members)} Mitglieder** zugewiesen.",
            color=discord.Color.green(),
        )

        if deadline:
            embed.add_field(name="📅 Deadline", value=deadline, inline=False)

        # Aufgaben gruppiert nach Mitglied
        member_tasks: dict[int, list[str]] = {}
        for a in assignments:
            mid = a["member"].id
            if mid not in member_tasks:
                member_tasks[mid] = []
            member_tasks[mid].append(f"`#{a['id']}` {a['task']}")

        for member_id, task_list in member_tasks.items():
            member = interaction.guild.get_member(member_id)
            name = member.display_name if member else f"User {member_id}"
            # Discord Embed Field max 1024 chars
            value = "\n".join(task_list)
            if len(value) > 1024:
                value = value[:1020] + "..."
            embed.add_field(name=f"👤 {name}", value=value, inline=False)

        embed.set_footer(text=f"Delegiert von {interaction.user.display_name} · Aufgaben im Dashboard sichtbar")

        # ── Pings an alle betroffenen Mitglieder ───────────────────────────
        ping_mentions = " ".join({a["member"].mention for a in assignments})
        await interaction.followup.send(
            content=f"📋 Neue Aufgaben für: {ping_mentions}",
            embed=embed,
        )

        log.info(
            "Delegate: %d Aufgaben für Projekt '%s' an %d Mitglieder verteilt",
            len(tasks), projekt_ziel[:50], len(member_tasks),
        )

    # ── Aufgabe als erledigt markieren ──────────────────────────────────────
    @app_commands.command(
        name="task-done",
        description="Markiere eine Aufgabe als erledigt.",
    )
    @app_commands.describe(task_id="Die ID der Aufgabe (z. B. 5)")
    async def task_done(self, interaction: discord.Interaction, task_id: int) -> None:
        await interaction.response.defer(thinking=True)

        task = await db.get_task(task_id)
        if not task:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Aufgabe nicht gefunden",
                    description=f"Keine Aufgabe mit ID `#{task_id}` vorhanden.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        from datetime import datetime
        await db.update_task(task_id, status="done", completed_at=datetime.now().isoformat())

        embed = discord.Embed(
            title="✅ Aufgabe erledigt!",
            description=f"**#{task_id}** – {task['task_desc']}",
            color=discord.Color.green(),
        )
        embed.add_field(name="👤 Zugewiesen an", value=task["user_name"], inline=True)
        embed.add_field(name="📁 Projekt", value=task["project"] or "–", inline=True)

        await interaction.followup.send(embed=embed)

    # ── Eigene Aufgaben anzeigen ───────────────────────────────────────────
    @app_commands.command(
        name="my-tasks",
        description="Zeige deine offenen Aufgaben.",
    )
    async def my_tasks(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        tasks = await db.get_tasks(user_id=interaction.user.id)
        open_tasks = [t for t in tasks if t["status"] != "done"]

        if not open_tasks:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="🎉 Keine offenen Aufgaben",
                    description="Du hast aktuell keine zugewiesenen Aufgaben. Genieße es!",
                    color=discord.Color.green(),
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"📋 Deine Aufgaben ({len(open_tasks)} offen)",
            color=discord.Color.blue(),
        )

        for t in open_tasks:
            status_icon = "🟡" if t["status"] == "in_progress" else "🔵"
            deadline_str = f" · 📅 {t['deadline']}" if t.get("deadline") else ""
            embed.add_field(
                name=f"{status_icon} #{t['id']} – {t['project'][:30] or 'Kein Projekt'}",
                value=f"{t['task_desc']}{deadline_str}",
                inline=False,
            )

        embed.set_footer(text="Nutze /task-done <id> um eine Aufgabe abzuschließen")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DelegateCog(bot))
