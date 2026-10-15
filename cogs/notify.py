"""
Cog: notify – DM-Benachrichtigungen, Broadcasts und automatisierte Stand-ups.

Features:
- Mo-Fr um 09:00: Automatische Stand-up DM an alle Teammitglieder
- Empfängt Antworten via DM und speichert sie in der Tabelle `standups`
- Mo-Fr um 10:00: Generiert kombiniertes Status-Embed im Orga-Kanal
- Slash-Commands: /dm-all, /meeting-dm, /standup-ask, /standup-summary
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import discord
from apscheduler.triggers.cron import CronTrigger
from discord import app_commands
from discord.ext import commands

import database as db
from config import ORGA_CHANNEL_ID

log = logging.getLogger(__name__)


class NotifyCog(commands.Cog):
    """Verwaltet DMs, Team-Broadcasts und tägliche Stand-ups."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._register_standup_jobs()

    def _register_standup_jobs(self) -> None:
        """Registriert die Stand-up Jobs (09:00 Frage, 10:00 Summary) im Scheduler."""
        try:
            from cogs.meeting import scheduler

            if not scheduler.running:
                scheduler.start()

            # Mo-Fr 09:00 Uhr: Stand-up DM an alle Mitglieder
            scheduler.add_job(
                self.send_daily_standup_prompt,
                trigger=CronTrigger(day_of_week="mon-fri", hour=9, minute=0, timezone="Europe/Berlin"),
                id="daily-standup-prompt",
                replace_existing=True,
            )

            # Mo-Fr 10:00 Uhr: Zusammenfassung in Orga-Kanal posten
            scheduler.add_job(
                self.post_daily_standup_summary,
                trigger=CronTrigger(day_of_week="mon-fri", hour=10, minute=0, timezone="Europe/Berlin"),
                id="daily-standup-summary",
                replace_existing=True,
            )

            log.info("⏰ Stand-up Jobs registriert (Mo-Fr 09:00 Prompt, 10:00 Summary Europe/Berlin)")
        except Exception:
            log.exception("Fehler beim Registrieren der Stand-up CronJobs")

    # ═══════════════════════════════════════════════════════════════════════
    # Automatisierte Stand-up Logik
    # ═══════════════════════════════════════════════════════════════════════

    async def send_daily_standup_prompt(self) -> dict:
        """Sendet die tägliche Stand-up-Frage per DM an alle Nicht-Bot-Mitglieder."""
        today_str = datetime.now().strftime("%d.%m.%Y")
        embed = discord.Embed(
            title="🌅 Guten Morgen! Tägliches Stand-up",
            description=(
                f"Hallo! Für unser 8er-Team-Stand-up am **{today_str}**:\n\n"
                "👉 **Was ist dein Fokus für heute und gibt es Blocker?**\n\n"
                "Antworte einfach direkt hier auf diese Nachricht im Chat.\n"
                "*(Deine Antwort wird erfasst und um 10:00 Uhr im Orga-Kanal zusammengefasst.)*"
            ),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="ORGA Bot Stand-up System")

        success = 0
        failed = 0

        for guild in self.bot.guilds:
            for member in guild.members:
                if member.bot:
                    continue
                try:
                    await member.send(embed=embed)
                    success += 1
                    await asyncio.sleep(0.5)
                except Exception as exc:
                    failed += 1
                    log.warning("Stand-up DM an %s fehlgeschlagen: %s", member.display_name, exc)

        log.info("Stand-up Prompt versendet: %d erfolgreich, %d fehlgeschlagen", success, failed)
        return {"success": success, "failed": failed}

    async def post_daily_standup_summary(self, target_channel: discord.TextChannel | None = None) -> bool:
        """Erstellt und sendet das kombinierte Stand-up Embed im Orga-Kanal."""
        today = datetime.now().strftime("%Y-%m-%d")
        display_date = datetime.now().strftime("%d.%m.%Y")

        channel = target_channel or self.bot.get_channel(ORGA_CHANNEL_ID)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(ORGA_CHANNEL_ID)
            except Exception:
                log.error("Orga-Kanal %s konnte für Stand-up Summary nicht gefunden werden", ORGA_CHANNEL_ID)
                return False

        # Alle heutigen Antworten abrufen
        standups = await db.get_standups(date=today)
        answered_users: dict[int, dict] = {s["user_id"]: s for s in standups}

        # Mitglieder ermitteln
        all_members: list[discord.Member] = []
        for guild in self.bot.guilds:
            for m in guild.members:
                if not m.bot and m not in all_members:
                    all_members.append(m)

        embed = discord.Embed(
            title=f"📋 Team Stand-up – {display_date}",
            description=f"Statusübersicht für heute ({len(answered_users)}/{len(all_members)} abgegeben):",
            color=discord.Color.blue(),
        )

        if answered_users:
            for uid, s in answered_users.items():
                uname = s["user_name"]
                ans = s["response_raw"]
                if len(ans) > 900:
                    ans = ans[:895] + "..."
                embed.add_field(
                    name=f"✅ {uname}",
                    value=ans,
                    inline=False,
                )
        else:
            embed.add_field(
                name="⚠️ Noch keine Antworten",
                value="Bislang sind heute noch keine Stand-up Antworten eingegangen.",
                inline=False,
            )

        # Fehlende Mitglieder auflisten
        missing = [m.mention for m in all_members if m.id not in answered_users]
        if missing:
            embed.add_field(
                name="⏳ Ausstehend",
                value=", ".join(missing),
                inline=False,
            )

        embed.set_footer(text="Tägliches Stand-up • ORGA Bot")
        await channel.send(embed=embed)
        log.info("Stand-up Summary für %s in Orga-Kanal gepostet", today)
        return True

    # ═══════════════════════════════════════════════════════════════════════
    # Listener: Eingehende DMs für Stand-up Antworten
    # ═══════════════════════════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Fängt DM-Antworten von Teammitgliedern ab und speichert Stand-ups."""
        # Nur Direktnachrichten von Nicht-Bots verarbeiten
        if message.guild is not None or message.author.bot:
            return

        user = message.author
        content = message.content.strip()

        if not content:
            return

        today = datetime.now().strftime("%Y-%m-%d")

        # In DB speichern (add_standup)
        await db.add_standup(
            user_id=user.id,
            user_name=user.display_name,
            response_raw=content,
            date=today,
        )

        log.info("Stand-up Antwort erfasst von %s (ID: %s)", user.display_name, user.id)

        # Bestätigung an den Nutzer senden
        confirm_embed = discord.Embed(
            title="✅ Stand-up gespeichert!",
            description=(
                f"Danke, **{user.display_name}**! Dein heutiger Status wurde notiert:\n\n"
                f"💬 *„{content[:300]}{'...' if len(content) > 300 else ''}“*\n\n"
                "Deine Antwort wird um **10:00 Uhr** in der Übersicht im Orga-Kanal und im Web-Dashboard angezeigt."
            ),
            color=discord.Color.green(),
        )
        try:
            await user.send(embed=confirm_embed)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════════════════
    # Slash-Commands
    # ═══════════════════════════════════════════════════════════════════════

    @app_commands.command(
        name="standup-ask",
        description="Löse die tägliche Stand-up DM-Runde jetzt manuell aus.",
    )
    async def standup_ask(self, interaction: discord.Interaction) -> None:
        """Sendet sofort die Stand-up-Frage an alle Teammitglieder."""
        await interaction.response.defer(thinking=True)
        res = await self.send_daily_standup_prompt()
        await interaction.followup.send(
            embed=discord.Embed(
                title="🌅 Stand-up Runde gestartet",
                description=f"DMs versendet: **{res['success']}** erfolgreich, **{res['failed']}** fehlgeschlagen.",
                color=discord.Color.green(),
            )
        )

    @app_commands.command(
        name="standup-summary",
        description="Poste die heutige Stand-up Zusammenfassung sofort im Orga-Kanal.",
    )
    async def standup_summary(self, interaction: discord.Interaction) -> None:
        """Postet sofort das aktuelle Stand-up-Ergebnis."""
        await interaction.response.defer(thinking=True)
        channel = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None
        ok = await self.post_daily_standup_summary(target_channel=channel)
        if ok:
            await interaction.followup.send("✅ Stand-up Zusammenfassung wurde gepostet!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Orga-Kanal konnte nicht erreicht werden.", ephemeral=True)

    @app_commands.command(
        name="dm-all",
        description="Sende eine DM-Nachricht an alle Mitglieder des Servers.",
    )
    @app_commands.describe(nachricht="Die Nachricht, die alle per DM erhalten sollen.")
    async def dm_all(self, interaction: discord.Interaction, nachricht: str) -> None:
        await interaction.response.defer(thinking=True)

        if not interaction.guild:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Nur auf Servern verfügbar",
                    description="Dieser Befehl kann nur auf einem Server verwendet werden.",
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )
            return

        members = [m for m in interaction.guild.members if not m.bot]

        if not members:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Keine Mitglieder gefunden",
                    description=(
                        "Der Bot konnte keine Mitglieder finden.\n"
                        "Stelle sicher, dass der **Server Members Intent** aktiviert ist."
                    ),
                    color=discord.Color.orange(),
                ),
            )
            return

        status_embed = discord.Embed(
            title="📨 DM-Versand läuft...",
            description=f"Sende Nachricht an **{len(members)}** Mitglieder...",
            color=discord.Color.blue(),
        )
        status_msg = await interaction.followup.send(embed=status_embed, wait=True)

        success = 0
        failed = 0
        failed_names: list[str] = []

        dm_embed = discord.Embed(
            title=f"📢 Nachricht von {interaction.guild.name}",
            description=nachricht,
            color=discord.Color.blue(),
        )
        dm_embed.set_footer(text=f"Gesendet von {interaction.user.display_name}")

        for i, member in enumerate(members):
            try:
                await member.send(embed=dm_embed)
                success += 1
            except discord.Forbidden:
                failed += 1
                failed_names.append(member.display_name)
                log.warning("DM an %s nicht möglich (DMs deaktiviert)", member.display_name)
            except Exception:
                failed += 1
                failed_names.append(member.display_name)
                log.exception("DM-Fehler bei %s", member.display_name)

            await asyncio.sleep(0.5)

            if (i + 1) % 5 == 0:
                progress_embed = discord.Embed(
                    title="📨 DM-Versand läuft...",
                    description=f"Fortschritt: **{i + 1}/{len(members)}** Mitglieder",
                    color=discord.Color.blue(),
                )
                try:
                    await status_msg.edit(embed=progress_embed)
                except Exception:
                    pass

        result_embed = discord.Embed(
            title="✅ DM-Versand abgeschlossen",
            color=discord.Color.green() if failed == 0 else discord.Color.orange(),
        )
        result_embed.add_field(name="✉️ Erfolgreich", value=str(success), inline=True)
        result_embed.add_field(name="❌ Fehlgeschlagen", value=str(failed), inline=True)
        result_embed.add_field(name="👥 Gesamt", value=str(len(members)), inline=True)

        if failed_names:
            names_str = ", ".join(failed_names[:10])
            if len(failed_names) > 10:
                names_str += f" … und {len(failed_names) - 10} weitere"
            result_embed.add_field(
                name="⚠️ Nicht erreichbar (DMs deaktiviert)",
                value=names_str,
                inline=False,
            )

        result_embed.set_footer(text=f"Gesendet von {interaction.user.display_name}")
        await status_msg.edit(embed=result_embed)

    @app_commands.command(
        name="meeting-dm",
        description="Erinnere alle per DM an das nächste anstehende Meeting.",
    )
    async def meeting_dm(self, interaction: discord.Interaction) -> None:
        """Sendet eine Meeting-Erinnerung als DM an alle Mitglieder."""
        await interaction.response.defer(thinking=True)

        if not interaction.guild:
            await interaction.followup.send("❌ Nur auf Servern verfügbar.", ephemeral=True)
            return

        meetings = await db.get_meetings(status="scheduled")
        now = datetime.now().isoformat()
        upcoming = [m for m in meetings if m["scheduled_at"] > now]

        if not upcoming:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="📅 Keine anstehenden Meetings",
                    description="Es gibt aktuell kein geplantes Meeting.",
                    color=discord.Color.orange(),
                ),
            )
            return

        meeting = upcoming[0]
        try:
            scheduled = datetime.fromisoformat(meeting["scheduled_at"])
            time_str = scheduled.strftime("%d.%m.%Y um %H:%M Uhr")
        except ValueError:
            time_str = meeting["scheduled_at"]

        members = [m for m in interaction.guild.members if not m.bot]

        status_embed = discord.Embed(
            title="📨 Meeting-DM läuft...",
            description=f'Erinnere **{len(members)}** Mitglieder an **„{meeting["topic"]}"**',
            color=discord.Color.blue(),
        )
        status_msg = await interaction.followup.send(embed=status_embed, wait=True)

        dm_embed = discord.Embed(
            title=f"📅 Meeting-Erinnerung: {meeting['topic']}",
            description=(
                f"Hey! Vergiss nicht unser Meeting:\n\n"
                f"**Thema:** {meeting['topic']}\n"
                f"**Wann:** {time_str}\n\n"
                f"Bitte sei pünktlich! 🙏"
            ),
            color=discord.Color.blue(),
        )

        success = 0
        failed = 0

        for member in members:
            try:
                await member.send(embed=dm_embed)
                success += 1
            except (discord.Forbidden, Exception):
                failed += 1
            await asyncio.sleep(0.5)

        await db.update_meeting(meeting["id"], dm_sent=1)

        result_embed = discord.Embed(
            title="✅ Meeting-Erinnerung gesendet",
            description=f'**{meeting["topic"]}** – {time_str}',
            color=discord.Color.green(),
        )
        result_embed.add_field(name="✉️ Gesendet", value=str(success), inline=True)
        result_embed.add_field(name="❌ Fehlgeschlagen", value=str(failed), inline=True)
        await status_msg.edit(embed=result_embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NotifyCog(bot))
