"""
Server Audit Script – Überprüft den Discord-Server des Bots,
alle Kanäle, Berechtigungen und Mitglieder.
"""

import certifi
import os

os.environ["SSL_CERT_FILE"] = certifi.where()

import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

TARGET_CHANNELS = {
    "termine": int(os.getenv("CHANNEL_TERMINE", 1560255601798291577)),
    "orga-bot": int(os.getenv("CHANNEL_ORGA_BOT", 1560255747986559027)),
    "vorlesung-material": int(os.getenv("CHANNEL_VORLESUNG_MATERIAL", 1560255397754048609)),
    "meeting-protokolle": int(os.getenv("CHANNEL_MEETING_PROTOKOLLE", 1560255397754048610)),
    "research-log": int(os.getenv("CHANNEL_RESEARCH_LOG", 1560255397754048611)),
    "praktikum-quiz": int(os.getenv("CHANNEL_PRAKTIKUM_QUIZ", 1560255397754048605)),
}

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"\n=======================================================")
    print(f"🤖 Bot erfolgreich eingeloggt als: {client.user} (ID: {client.user.id})")
    print(f"📡 Verbundene Server: {len(client.guilds)}")
    print(f"=======================================================\n")

    if not client.guilds:
        print("⚠️ DER BOT WURDE NOCH AUF KEINEN SERVER EINGELADEN!")
        print("Bitte nutze den OAuth2-Einladelink, um den Bot auf deinen Server zu holen.")
        await client.close()
        return

    for guild in client.guilds:
        print(f"🏰 Server: '{guild.name}' (ID: {guild.id})")
        print(f"👑 Owner: {guild.owner}")
        print(f"👥 Mitglieder gesamt: {guild.member_count}")
        
        # Mitglieder auflisten
        human_members = [m for m in guild.members if not m.bot]
        bot_members = [m for m in guild.members if m.bot]
        print(f"   └── Echte Personen ({len(human_members)}): {', '.join(m.display_name for m in human_members)}")
        print(f"   └── Bots ({len(bot_members)}): {', '.join(m.display_name for m in bot_members)}")
        print()

        print("🔍 KANAL-ÜBERPRÜFUNG:")
        for key, chan_id in TARGET_CHANNELS.items():
            channel = guild.get_channel(chan_id)
            if channel:
                perms = channel.permissions_for(guild.me)
                can_send = perms.send_messages
                can_embed = perms.embed_links
                status = "✅ Gefunden & Schreibrechte OK" if (can_send and can_embed) else "⚠️ Eingeschränkte Rechte"
                print(f"   • #{key} (ID: {chan_id}): {status} [Name: #{channel.name}]")
            else:
                print(f"   • #{key} (ID: {chan_id}): ❌ NICHT GEFUNDEN auf Server '{guild.name}'")

        print("\n🔊 SPRACHKANÄLE (VC):")
        if guild.voice_channels:
            for vc in guild.voice_channels:
                active_users = [m.display_name for m in vc.members]
                users_str = f"({len(active_users)} online: {', '.join(active_users)})" if active_users else "(leer)"
                print(f"   • 🔊 {vc.name} (ID: {vc.id}) {users_str}")
        else:
            print("   ⚠️ Keine Sprachkanäle gefunden!")

    print("\n=======================================================")
    print("Audit abgeschlossen!")
    print("=======================================================\n")
    await client.close()


if __name__ == "__main__":
    client.run(TOKEN)
