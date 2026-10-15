"""
Cog: meeting – Meeting planen mit automatischen Erinnerungen, DM-Notifications
und automatischer Erfassung der Anwesenheit im Sprachkanal (VC) zu Meeting-Beginn
in #meeting-protokolle.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

import dateparser
import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import app_commands
from discord.ext import commands

import database as db
from config import CHANNEL_TERMINE, CHANNEL_MEETING_PROTOKOLLE

log = logging.getLogger(__name__)

# Globaler Scheduler
scheduler = AsyncIOScheduler(timezone="Europe/Berlin")


class MeetingCog(commands.Cog):
    """Plant Meetings, sendet Erinnerungen und erfasst VC-Anwesenheitsprotokolle."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        if not scheduler.running:
            scheduler.start()

    # ── Slash-Command ──────────────────────────────────────────────────────
    @app_commands.command(
        name="meeting",
        description="Plane ein Meeting mit Erinnerungen und automatischem VC-Anwesenheitsprotokoll.",
    )
    @app_commands.describe(
        datum_uhrzeit='Datum & Uhrzeit, z. B. "morgen 15:00" oder "18.10. 10:00"',
        thema="Thema / Titel des Meetings",
    )
    async def meeting(
        self,
        interaction: discord.Interaction,
        datum_uhrzeit: str,
        thema: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        # ── Datum parsen ───────────────────────────────────────────────────
        parsed = dateparser.parse(
            datum_uhrzeit,
            languages=["de"],
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": "Europe/Berlin",
                "RETURN_AS_TIMEZONE_AWARE": True,
            },
        )

        if parsed is None:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Ungültiges Datum",
                    description=(
                        f'Ich konnte **„{datum_uhrzeit}"** nicht verstehen.\n'
                        "Versuche z. B. `morgen 15:00` oder `20.10. 14:30`."
                    ),
                    color=discord.Color.red(),
                )
            )
            return

        now = datetime.now(tz=parsed.tzinfo)
        if parsed <= now:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⏰ Zeitpunkt liegt in der Vergangenheit",
                    description="Bitte gib einen zukünftigen Zeitpunkt an.",
                    color=discord.Color.orange(),
                )
            )
            return

        # ── In Datenbank speichern ─────────────────────────────────────────
        meeting_id = await db.add_meeting(
            topic=thema,
            scheduled_at=parsed,
            created_by=interaction.user.display_name,
            created_by_id=interaction.user.id,
        )

        # ── Erinnerungen & VC-Protokoll planen ─────────────────────────────
        time_str = parsed.strftime("%d.%m.%Y um %H:%M Uhr")
        reminder_24h = parsed - timedelta(hours=24)
        reminder_1h = parsed - timedelta(hours=1)
        meeting_start = parsed

        # 1. 24h & 1h Erinnerung planen
        if reminder_24h > now:
            scheduler.add_job(
                self.send_reminder,
                "date",
                run_date=reminder_24h,
                args=[thema, time_str, "⏳ Noch **24 Stunden** bis zum Meeting!"],
                id=f"meeting-24h-{meeting_id}",
                replace_existing=True,
            )
        if reminder_1h > now:
            scheduler.add_job(
                self.send_reminder,
                "date",
                run_date=reminder_1h,
                args=[thema, time_str, "🔔 Noch **1 Stunde** bis zum Meeting!"],
                id=f"meeting-1h-{meeting_id}",
                replace_existing=True,
            )

        # 2. Genau zu Meeting-Beginn: VC-Anwesenheit in #meeting-protokolle erfassen!
        scheduler.add_job(
            self.record_meeting_attendance,
            "date",
            run_date=meeting_start,
            args=[meeting_id, thema, time_str],
            id=f"meeting-start-{meeting_id}",
            replace_existing=True,
        )

        # ── Bestätigung ───────────────────────────────────────────────────
        embed = discord.Embed(
            title="✅ Meeting geplant!",
            color=discord.Color.green(),
        )
        embed.add_field(name="📌 Thema", value=thema, inline=False)
        embed.add_field(name="🕐 Zeitpunkt", value=time_str, inline=False)
        embed.add_field(
            name="📢 Benachrichtigungen",
            value=(
                f"• Ankündigung in <#{CHANNEL_TERMINE}>\n"
                f"• DMs 24h & 1h vorab an alle 8\n"
                f"• Automatisches VC-Anwesenheitsprotokoll zu Meeting-Beginn in <#{CHANNEL_MEETING_PROTOKOLLE}>"
            ),
            inline=False,
        )
        embed.add_field(name="🆔 Meeting-ID", value=f"#{meeting_id}", inline=True)
        embed.set_footer(text=f"Geplant von {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)
        log.info("Meeting #%d geplant: %s am %s", meeting_id, thema, time_str)

    # ── Erinnerung senden ──────────────────────────────────────────────────
    async def send_reminder(self, topic: str, time_str: str, prefix: str) -> None:
        """Sendet Erinnerung in #termine und per DM an alle Mitglieder."""
        channel = self.bot.get_channel(CHANNEL_TERMINE)
        if channel:
            embed = discord.Embed(
                title=f"📅 Meeting-Erinnerung: {topic}",
                description=f"{prefix}\n\n**Thema:** {topic}\n**Wann:** {time_str}",
                color=discord.Color.blue(),
            )
            try:
                await channel.send(content="@everyone", embed=embed)
            except Exception:
                log.exception("Fehler beim Senden in #termine")

        # Persönliche DM an jedes Mitglied
        dm_embed = discord.Embed(
            title="📅 Meeting-Erinnerung",
            description=(
                f"{prefix}\n\n"
                f"**Thema:** {topic}\n"
                f"**Wann:** {time_str}\n\n"
                f"Bitte sei pünktlich im Sprachkanal! 🙏"
            ),
            color=discord.Color.blue(),
        )
        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                try:
                    await member.send(embed=dm_embed)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass

    # ── VC-Anwesenheit zu Meeting-Beginn erfassen ─────────────────────────
    async def record_meeting_attendance(self, meeting_id: int, topic: str, time_str: str) -> None:
        """Prüft zur Meeting-Zeit den Sprachkanal (VC) und postet das Anwesenheitsprotokoll."""
        log.info("Meeting-Start! Erfasse VC-Anwesenheit für: %s", topic)

        # Alle Mitglieder ermitteln
        team_dict = {m["user_id"]: m["full_name"] for m in await db.get_team_members()}

        present_members: list[discord.Member] = []
        all_guild_members: list[discord.Member] = []

        # Alle Voice Channels durchsuchen
        for guild in self.bot.guilds:
            for m in guild.members:
                if not m.bot and m not in all_guild_members:
                    all_guild_members.append(m)

            for vc in guild.voice_channels:
                for member in vc.members:
                    if not member.bot and member not in present_members:
                        present_members.append(member)

        # Anwesende / Abwesende formatieren (mit Klarnamen falls registriert)
        present_str_list = []
        for m in present_members:
            klarname = team_dict.get(m.id)
            name_label = f"{klarname} ({m.mention})" if klarname else m.mention
            present_str_list.append(name_label)

        absent_members = [m for m in all_guild_members if m not in present_members]
        absent_str_list = []
        for m in absent_members:
            klarname = team_dict.get(m.id)
            name_label = f"{klarname} ({m.mention})" if klarname else m.mention
            absent_str_list.append(name_label)

        present_count = len(present_members)
        total_count = len(all_guild_members) or 8

        # 1. Anwesenheits-Embed in #meeting-protokolle posten
        proto_channel = self.bot.get_channel(CHANNEL_MEETING_PROTOKOLLE)
        if proto_channel is None:
            try:
                proto_channel = await self.bot.fetch_channel(CHANNEL_MEETING_PROTOKOLLE)
            except Exception:
                log.error("Kanal #meeting-protokolle (%d) nicht erreichbar", CHANNEL_MEETING_PROTOKOLLE)

        embed = discord.Embed(
            title=f"🎙️ Anwesenheitsprotokoll: {topic}",
            description=(
                f"**Meeting gestartet:** {time_str}\n"
                f"**Anwesenheitsquote:** **{present_count}/{total_count} Personen** im Sprachkanal."
            ),
            color=discord.Color.green() if present_count >= total_count else discord.Color.orange(),
        )

        embed.add_field(
            name=f"🟢 Anwesend im Sprachkanal ({present_count})",
            value="\n".join(present_str_list) if present_str_list else "⚠️ *Niemand im Sprachkanal*",
            inline=False,
        )

        if absent_str_list:
            embed.add_field(
                name=f"🔴 Abwesend ({len(absent_str_list)})",
                value="\n".join(absent_str_list),
                inline=False,
            )

        embed.set_footer(text="Automatische VC-Anwesenheitserfassung • ORGA Bot")

        if proto_channel:
            await proto_channel.send(embed=embed)

        # 2. In #termine posten, dass es jetzt losgeht
        termine_channel = self.bot.get_channel(CHANNEL_TERMINE)
        if termine_channel:
            start_embed = discord.Embed(
                title=f"🔔 Meeting startet JETZT: {topic}",
                description=(
                    f"Das Meeting beginnt jetzt!\n"
                    f"Bitte alle in den Sprachkanal kommen.\n\n"
                    f"👉 Das Anwesenheitsprotokoll wurde in <#{CHANNEL_MEETING_PROTOKOLLE}> erfasst."
                ),
                color=discord.Color.red(),
            )
            try:
                await termine_channel.send(content="@everyone", embed=start_embed)
            except Exception:
                pass

        # In DB persistieren
        await db.add_attendance(
            meeting_id=meeting_id,
            topic=topic,
            scheduled_at=time_str,
            present_count=present_count,
            present_names=", ".join(m.display_name for m in present_members),
            absent_names=", ".join(m.display_name for m in absent_members),
        )

    # ── Manueller VC-Check per Slash-Command ──────────────────────────────
    @app_commands.command(
        name="vc-attendance",
        description="Erfasse die aktuelle Anwesenheit im Sprachkanal sofort als Protokoll.",
    )
    @app_commands.describe(thema="Thema des aktuellen Meetings")
    async def vc_attendance(self, interaction: discord.Interaction, thema: str = "Spontanes Meeting") -> None:
        """Erfasst sofort manuell die Anwesenheit aller Mitglieder im VC."""
        await interaction.response.defer(thinking=True)
        now_str = datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")
        await self.record_meeting_attendance(meeting_id=0, topic=thema, time_str=now_str)
        await interaction.followup.send(
            embed=discord.Embed(
                title="✅ Anwesenheitsprotokoll erstellt!",
                description=f"Das VC-Protokoll für **{thema}** wurde in <#{CHANNEL_MEETING_PROTOKOLLE}> gepostet.",
                color=discord.Color.green(),
            )
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(MeetingCog(bot))
