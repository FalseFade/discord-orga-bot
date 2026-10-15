"""
Cog: team – Team-Registrierung mit Klarnamen und Team-Übersicht.

Slash-Commands:
  /introduce [voller_name] – Stellt das Mitglied dem Bot mit echtem Namen vor
  /team                    – Zeigt alle registrierten 8 Teammitglieder und deren Status
"""

from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands

import database as db

log = logging.getLogger(__name__)


class TeamCog(commands.Cog):
    """Verwaltet Klarnamen der Teammitglieder und Team-Übersichten."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="introduce",
        description="Stelle dich dem Bot mit deinem vollständigen Namen vor.",
    )
    @app_commands.describe(voller_name="Dein vollständiger Vor- und Nachname (z.B. Max Mustermann)")
    async def introduce(self, interaction: discord.Interaction, voller_name: str) -> None:
        """Registriert den echten Namen des Mitglieds."""
        await interaction.response.defer(thinking=True)

        user = interaction.user
        voller_name_clean = voller_name.strip()

        if len(voller_name_clean) < 3 or " " not in voller_name_clean:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⚠️ Bitte vollständigen Namen angeben",
                    description="Bitte gib deinen kompletten Vor- und Nachnamen an (z. B. `Max Mustermann`).",
                    color=discord.Color.orange(),
                ),
                ephemeral=True,
            )
            return

        # In DB speichern
        await db.add_or_update_team_member(
            user_id=user.id,
            full_name=voller_name_clean,
            discord_name=user.display_name,
        )

        embed = discord.Embed(
            title="👋 Willkommen im Team!",
            description=(
                f"Freut mich sehr, **{voller_name_clean}**!\n\n"
                f"Ich habe dich erfolgreich mit deinem Discord-Account {user.mention} verknüpft.\n"
                "Ich werde deinen Namen künftig in Meeting-Protokollen, Stand-ups und Aufgabenverteilungen verwenden."
            ),
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Team-Registrierung • ORGA Bot")

        await interaction.followup.send(embed=embed)
        log.info("Teammitglied registriert: %s (ID: %d) als '%s'", user.display_name, user.id, voller_name_clean)

    @app_commands.command(
        name="team",
        description="Zeige alle registrierten Teammitglieder und deren Status an.",
    )
    async def team_overview(self, interaction: discord.Interaction) -> None:
        """Listet alle Team-Mitglieder mit Klarnamen auf."""
        await interaction.response.defer(thinking=True)

        registered = await db.get_team_members()
        tasks = await db.get_tasks()

        guild = interaction.guild
        total_server_members = [m for m in guild.members if not m.bot] if guild else []

        embed = discord.Embed(
            title="👥 Unser Team (8er-Gruppe)",
            description=f"Übersicht aller registrierten Mitglieder ({len(registered)}/{len(total_server_members) or 8}):",
            color=discord.Color.blue(),
        )

        if registered:
            for member in registered:
                user_id = member["user_id"]
                full_name = member["full_name"]
                discord_name = member["discord_name"]

                # Offene Aufgaben für diesen Nutzer zählen
                user_tasks = [t for t in tasks if t["user_id"] == user_id and t["status"] != "done"]

                discord_user = guild.get_member(user_id) if guild else None
                mention = discord_user.mention if discord_user else f"@{discord_name}"

                embed.add_field(
                    name=f"👤 {full_name}",
                    value=f"Discord: {mention}\nOffene Aufgaben: **{len(user_tasks)}**",
                    inline=True,
                )
        else:
            embed.description = (
                "Es hat sich noch niemand vorgestellt!\n"
                "Nutzt `/introduce [voller_name]`, um euch mit eurem echten Namen zu registrieren."
            )

        # Noch nicht vorgestellte Mitglieder auflisten
        reg_ids = {m["user_id"] for m in registered}
        unregistered = [m.mention for m in total_server_members if m.id not in reg_ids]
        if unregistered:
            embed.add_field(
                name="⏳ Noch nicht registriert",
                value=", ".join(unregistered) + "\n*(Bitte `/introduce` nutzen)*",
                inline=False,
            )

        embed.set_footer(text="ORGA Bot Team-Manager")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TeamCog(bot))
