"""
Populate Channels Script – Befüllt alle Discord-Kanäle mit den echten Inhalten,
Modellen und Richtlinien für das Fach:
"Organisation & Projektmanagement" (OPM - Modul 53183, Dr. Axel Emunds, FH Aachen).
"""

import certifi
import os

os.environ["SSL_CERT_FILE"] = certifi.where()

import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

CHANNELS = {
    "termine": int(os.getenv("CHANNEL_TERMINE", 1560255601798291577)),
    "orga-bot": int(os.getenv("CHANNEL_ORGA_BOT", 1560255747986559027)),
    "vorlesung-material": int(os.getenv("CHANNEL_VORLESUNG_MATERIAL", 1560255397754048609)),
    "meeting-protokolle": int(os.getenv("CHANNEL_MEETING_PROTOKOLLE", 1560255397754048610)),
    "research-log": int(os.getenv("CHANNEL_RESEARCH_LOG", 1560255397754048611)),
    "praktikum-quiz": int(os.getenv("CHANNEL_PRAKTIKUM_QUIZ", 1560255397754048605)),
}

DASHBOARD_URL = "https://discord-orga-bot-production.up.railway.app"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)


async def setup_orga_bot_channel(channel: discord.TextChannel):
    """Befüllt #orga-bot mit der zentralen Onboarding-Nachricht für OPM."""
    embed = discord.Embed(
        title="🤖 OPM Projekt-Manager – Zentrale & Onboarding",
        description=(
            "Herzlich willkommen im Arbeitsbereich unserer **OPM-Projektgruppe (Gruppe 4)**!\n"
            "Modul: **Organisation & Projektmanagement (53183)** • Dozent: **Dr. Axel Emunds**\n\n"
            "Der Bot unterstützt uns autonom bei der Projektorganisation, Aufgabenverteilung und Stand-ups.\n\n"
            f"🌐 **Unser Live Web-Dashboard:**\n"
            f"👉 **[{DASHBOARD_URL}]({DASHBOARD_URL})**\n"
            "*(Hier könnt ihr Aufgaben per Mausklick abhaken, Stand-ups nachlesen und Meetings planen!)*"
        ),
        color=discord.Color.blue(),
    )

    embed.add_field(
        name="1️⃣ SCHRITT 1: Bitte einmalig vorstellen (Pflicht für alle 8!)",
        value=(
            "Tippe folgenden Befehl im Chat ein:\n"
            "👉 `/introduce voller_name:Dein Vorname Nachname`\n"
            "*(Beispiel: `/introduce voller_name:Max Mustermann`)*\n"
            "Damit verknüpft der Bot deinen Discord-Account mit deinem echten Namen für Aufgaben und Protokolle."
        ),
        inline=False,
    )

    embed.add_field(
        name="2️⃣ Tägliches Asynchrones Stand-up (Mo–Fr)",
        value=(
            "• **09:00 Uhr:** Der Bot schreibt dir eine kurze DM: *„Was ist dein Fokus für heute und gibt es Blocker?“*\n"
            "• **Antwort:** Antworte einfach direkt im privaten Chat an den Bot.\n"
            "• **10:00 Uhr:** Der Bot postet eine zusammengefasste Statusübersicht hier in diesen Kanal."
        ),
        inline=False,
    )

    embed.add_field(
        name="3️⃣ Die wichtigsten Slash-Commands",
        value=(
            "`/introduce [voller_name]` ➔ Registriere deinen Klarnamen\n"
            "`/team` ➔ Teamübersicht & offene Aufgaben aller 8 Gruppenmitglieder\n"
            "`/my-tasks` ➔ Deine persönlichen offenen Aufgaben anzeigen\n"
            "`/task-done [id]` ➔ Aufgabe als erledigt markieren (z. B. `/task-done id:2`)\n"
            "`/delegate [ziel]` ➔ Projektziel via KI in Teilaufgaben zerlegen und rotierend zuweisen\n"
            "`/meeting [datum] [thema]` ➔ Meeting mit 24h/1h Erinnerungen & VC-Protokoll planen\n"
            "`/recap [text]` ➔ Protokoll analysieren (Beschlüsse & To-Dos extrahieren)\n"
            "`/quiz` ➔ OPM-Prüfungsfragen zu Skripten & Vorlesung (AFB I–III)"
        ),
        inline=False,
    )
    embed.set_footer(text="Organisation & Projektmanagement • Gruppe 4")
    await channel.send(embed=embed)


async def setup_termine_channel(channel: discord.TextChannel):
    """Befüllt #termine mit OPM-Terminen & Meeting-Leitfaden."""
    embed = discord.Embed(
        title="📅 OPM Termine, Praktika & Meilensteine",
        description=(
            "In diesem Kanal werden alle Termine koordiniert.\n\n"
            "📌 **Feste Modul-Termine (Dr. Axel Emunds):**\n"
            "• **Vorlesung (V):** Do 13:45 – 15:15 Uhr\n"
            "• **Übung (Ü):** Do 15:30 – 16:15 Uhr (ab 22.10.)\n"
            "• **Praktikum (Gruppe 4):** alle 2 Wochen Do 16:30 – 18:00 Uhr\n"
            "  Termine: **15.10., 29.10., 12.11., 26.11., 10.12., 07.01., 21.01.**\n"
            "• **Pflicht-Probeklausur:** Do 17.12. (Teilnahme & Besprechung)\n\n"
            "🔊 **Unser Standard-Sprachkanal:** `🔊 ORGA-Meeting`"
        ),
        color=discord.Color.purple(),
    )

    embed.add_field(
        name="📌 Internes Team-Meeting planen",
        value=(
            "Nutze einfach den Slash-Command:\n"
            "👉 `/meeting datum_uhrzeit:morgen 15:00 thema:Vorbereitung Praktikum 2 & Auftragsklärung`\n"
            "Der Bot versteht natürliches Deutsch (z. B. `morgen 15:00`, `Freitag 11:30`, `29.10. 14:00`)."
        ),
        inline=False,
    )

    embed.add_field(
        name="🔔 Automatische Erinnerungen",
        value=(
            "• **24 Stunden vorher:** Ankündigung hier im Kanal + persönliche DM an alle 8.\n"
            "• **1 Stunde vorher:** Erinnerung hier im Kanal + persönliche DM an alle 8.\n"
            "• **Zur Startzeit:** Alarm mit `@everyone` und automatische VC-Anwesenheitserfassung!"
        ),
        inline=False,
    )
    embed.set_footer(text="Termin-Koordination • Gruppe 4 (OPM)")
    await channel.send(embed=embed)


async def setup_meeting_protokolle_channel(channel: discord.TextChannel):
    """Befüllt #meeting-protokolle mit OPM-spezifischem Protokoll-Template."""
    embed = discord.Embed(
        title="📝 OPM Meeting-Protokolle & VC-Anwesenheit",
        description=(
            "Im Praktikum gilt: **„Es zählt das WIE und nicht das WAS!“** (~60 % Projektmanagement / ≤ 40 % Inhalt).\n"
            "Deshalb dokumentieren wir hier alle Absprachen, Rollen und Beschlüsse sauber."
        ),
        color=discord.Color.teal(),
    )

    embed.add_field(
        name="🎙️ Automatisches VC-Anwesenheitsprotokoll",
        value=(
            "Sobald ein geplantes Meeting beginnt, prüft der Bot automatisch unseren Sprachkanal (`🔊 ORGA-Meeting`), "
            "zählt wie viele Gruppenmitglieder anwesend sind und postet das Anwesenheitsprotokoll direkt hier rein!"
        ),
        inline=False,
    )

    embed.add_field(
        name="⚡ Protokoll per KI zusammenfassen lassen (`/recap`)",
        value=(
            "Nach einem Meeting könnt ihr eure Stichpunkte mit `/recap text:[Notizen]` hier analysieren lassen.\n"
            "Die KI strukturiert automatisch:\n"
            "1. **📌 Verbindliche Beschlüsse**\n"
            "2. **✅ To-Dos mit Zuständigkeiten** (zugeordnet zu Gruppenmitgliedern)\n"
            "3. **❓ Offene Fragen & Risiken für das nächste Praktikum**"
        ),
        inline=False,
    )
    embed.set_footer(text="OPM Protokoll-Archiv • Gruppe 4")
    await channel.send(embed=embed)


async def setup_vorlesung_material_channel(channel: discord.TextChannel):
    """Befüllt #vorlesung-material mit den echten OPM-Konzepten & Folien H-101 bis H-148."""
    embed = discord.Embed(
        title="📚 Vorlesungsstoff: Organisation & Projektmanagement (OPM)",
        description=(
            "Hier findet ihr die zentralen Definitionen, Folien und Skripte (Folienreihe `H-101` bis `H-148`, Dr. Emunds).\n"
            "Der Bot greift auf diese Unterlagen zu, um Prüfungsfragen für `/quiz` zu generieren!"
        ),
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="🎯 Kern-Konzepte & Prüfungsstoff (AFB I–III)",
        value=(
            "• **Projektdefinition:** Multipersonales Vorhaben mit neuartigem Ziel, begrenzter Zeit/Ressourcen (Jakoby + ISO 21500)\n"
            "• **7 ZESPORT-Merkmale (0–3 Skala):** Zielexistenz, Einmaligkeit, Schwierigkeit, Prozesscharakter, Organisation, Ressourcenbegrenzung, Terminierung\n"
            "• **Kuster-Matrix:** Aufgabenstellung (offen/geschlossen) × soziale Komplexität (gering/hoch) ➔ Standard-, Akzeptanz-, Potenzial-, Pionier-Projekt\n"
            "• **Projekt als System:** Trivial (Fremdsteuerung) vs. Nicht-trivial (Selbststeuerung Menschen/Teams) • Arbeit *im* System (Inhalt) vs. *am* System (Organisation/Beziehung)\n"
            "• **Team-Dynamik:** Tuckman-Phasen (Forming, Storming, Norming, Performing), Belbin-Teamrollen, DISG-Modell, Gewinner-Gewinner-Modell\n"
            "• **Auftragsklärung:** Klient – Sinn – Ergebnis – Abnahmekriterien (zyklisch wiederholt)"
        ),
        inline=False,
    )

    embed.add_field(
        name="📁 Lokale Skripte im Bot hinterlegt",
        value=(
            "Alle Folien (`H-101` Syllabus, `H-104` Project, `H-137` Organisation, `H-143` TeamBuilding, `H-148` OrderClarification) "
            "sowie die Zusammenfassungen (`OPM - Lernstoff.md`, `OPM - Kernüberblick.md`) sind bereits im Bot-System hinterlegt!"
        ),
        inline=False,
    )
    embed.set_footer(text="OPM • Modul 53183 • Dr. Axel Emunds")
    await channel.send(embed=embed)


async def setup_research_log_channel(channel: discord.TextChannel):
    """Befüllt #research-log mit OPM-Forschungs- & Fallstudien-Format."""
    embed = discord.Embed(
        title="🔬 Research Log & Fallstudien-Dokumentation",
        description=(
            "In OPM ist unser **eigenes Gruppenprojekt die primäre Fallstudie**!\n"
            "Hier dokumentieren wir methodische Recherchen, Normen (DIN 69901, ISO 21500) und Best Practices."
        ),
        color=discord.Color.dark_purple(),
    )

    embed.add_field(
        name="📋 Dokumentations-Schema für Erkenntnisse",
        value=(
            "**Methode / Fragestellung:** z. B. Nutzwertanalyse vs. Paarweiser Vergleich\n"
            "**Fachlicher Bezug:** Bezug zu den Folien (z. B. H-104 oder H-148)\n"
            "**Anwendung im Gruppenprojekt:** Wie setzen wir es in Gruppe 4 um?\n"
            "**Quellen:** Jakoby, DIN-Normen oder Vorlesungsskript"
        ),
        inline=False,
    )
    embed.set_footer(text="Research & Methodology • Gruppe 4")
    await channel.send(embed=embed)


async def setup_praktikum_quiz_channel(channel: discord.TextChannel):
    """Befüllt #praktikum-quiz mit OPM-Prüfungstrainer."""
    embed = discord.Embed(
        title="🎓 OPM Prüfungsvorbereitung (Klausur-Trainer)",
        description=(
            "Die Klausur zählt **100 % der Modulnote** (90 Min, ~135 Punkte, 40 % = 4,0, nur Taschenrechner).\n"
            "Nutzt diesen Kanal, um euer Wissen nach den Anforderungsbereichen **AFB I (Reproduktion), AFB II (Transfer) und AFB III (Reflexion)** zu testen!"
        ),
        color=discord.Color.green(),
    )

    embed.add_field(
        name="❓ Wie starte ich das OPM-Quiz?",
        value=(
            "1. Tippe `/quiz` ein.\n"
            "2. Der Bot zieht Inhalte aus `OPM - Lernstoff.md` und den Emunds-Folien (`H-101` bis `H-148`) und stellt eine klausurrelevante Frage.\n"
            "3. Klicke auf **„✍️ Antworten“** und schreibe deine Begründung ins Pop-up.\n"
            "4. Der Bot bewertet deine Antwort nach den Kriterien von Dr. Emunds mit **deutscher Schulnote (1–6)** und detaillierter Musterlösung!"
        ),
        inline=False,
    )
    embed.set_footer(text="100% Klausurvorbereitung • OPM Gruppe 4")
    await channel.send(embed=embed)


@client.event
async def on_ready():
    print(f"\nStarte Befüllung aller Kanäle mit echtem OPM-Stoff auf Server '{client.guilds[0].name}'...")

    handlers = {
        "orga-bot": setup_orga_bot_channel,
        "termine": setup_termine_channel,
        "meeting-protokolle": setup_meeting_protokolle_channel,
        "vorlesung-material": setup_vorlesung_material_channel,
        "research-log": setup_research_log_channel,
        "praktikum-quiz": setup_praktikum_quiz_channel,
    }

    for key, handler in handlers.items():
        chan_id = CHANNELS[key]
        channel = client.get_channel(chan_id)
        if channel:
            print(f"Befülle #{key} mit OPM-Inhalten...")
            await handler(channel)
            await asyncio.sleep(1.0)
        else:
            print(f"❌ Kanal #{key} (ID: {chan_id}) nicht gefunden!")

    print("\n✅ Alle Kanäle wurden erfolgreich mit echten OPM-Inhalten aktualisiert!\n")
    await client.close()


if __name__ == "__main__":
    client.run(TOKEN)
