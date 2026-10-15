# 🤖 Discord ORGA Bot – Autonomer Projektmanager & Web-Dashboard

[![Live Dashboard](https://img.shields.io/badge/Live_Dashboard-Railway-5865F2?style=for-the-badge&logo=railway)](https://discord-orga-bot-production.up.railway.app)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)](https://python.org)
[![discord.py v2](https://img.shields.io/badge/discord.py-v2.3-5865F2?style=for-the-badge&logo=discord)](https://discordpy.readthedocs.io)
[![OpenAI Compatible](https://img.shields.io/badge/LLM-KI:Connect-00A67E?style=for-the-badge&logo=openai)](https://chat.kiconnect.nrw)

Produktionsreifer, autonomer Discord-Projektmanager für ein 8-köpfiges Hochschul-Team. Integriert **KI:Connect** (OpenAI-kompatibles GPT-4o Modell der NRW-Hochschulen), **SQLite-Datenbank**, automatische **Sprachkanal-(VC)-Anwesenheitserfassung**, tägliche **asynchrone Stand-ups** und ein reaktives **Web-Dashboard**.

---

## 🌐 Live Web-Dashboard

Das Dashboard läuft 24/7 in der Cloud:
👉 **[https://discord-orga-bot-production.up.railway.app](https://discord-orga-bot-production.up.railway.app)**

- **📊 Dashboard**: Live-Statistiken, Stand-up Status, Countdown zum nächsten Meeting.
- **📋 Task Board**: Aufgabenverwaltung pro Teammitglied, Statusumschaltung (`Offen` ➔ `Erledigt`) und Task-Erstellung.
- **🌅 Stand-up Monitor**: Tägliche Antworten zu Fokus & Blockern, Ausstehenden-Liste und Datumshistorie.
- **📅 Meetings**: Meetings anlegen, bearbeiten, löschen oder 1-Klick DM-Broadcast an alle 8 senden.
- **📝 Recaps**: Durchsuchbares Archiv aller KI-Protokoll-Analysen mit ausklappbarem Originaltext.

---

## 🌟 Funktionsübersicht & Slash-Commands

| Command | Parameter | Beschreibung |
|---|---|---|
| `/introduce` | `voller_name` | **Wichtigster Schritt:** Registriert den echten Vor- und Nachnamen (z. B. `Max Mustermann`) in der Bot-Datenbank. |
| `/team` | *keine* | Zeigt die Übersicht aller 8 Teammitglieder mit Klarnamen, Discord-Tags und offenen Aufgaben. |
| `/meeting` | `datum_uhrzeit`, `thema` | Plant ein Meeting (z. B. `morgen 15:00`). Sendet 24h & 1h vorab DMs + Kanal-Ping. Erfasst zur Startzeit die VC-Anwesenheit! |
| `/vc-attendance` | `thema` *(optional)* | Prüft sofort den Sprachkanal und postet das Anwesenheitsprotokoll in `#meeting-protokolle`. |
| `/delegate` | `projekt_ziel`, `deadline` *(opt)* | Zerlegt ein Projektziel via KI in konkrete Teilaufgaben und verteilt sie rotierend an alle 8 mit Discord-Pings. |
| `/my-tasks` | *keine* | Zeigt die eigenen offenen Aufgaben an (nur für den Aufrufer sichtbar). |
| `/task-done` | `task_id` | Markiert eine Aufgabe als erledigt (z. B. `/task-done task_id:3`). |
| `/recap` | `text` | Analysiert ein langes Meeting-Protokoll, extrahiert Beschlüsse, ordnet To-Dos Personen zu und listet offene Fragen auf. |
| `/critique` | `idee_text` | **Devil's Advocate Modus:** Ein kritischer Investor prüft ein Konzept nach Desirability, Viability und Feasibility. |
| `/quiz` | *keine* | Stellt eine anspruchsvolle Verständnisfrage basierend auf den Vorlesungsfolien mit interaktivem Antwort-Modal und KI-Bewertung. |
| `/standup-ask` | *keine* | Löst die tägliche Stand-up Fragerunde sofort manuell per DM aus (normalerweise Mo–Fr 09:00 Uhr). |
| `/standup-summary`| *keine* | Postet die heutige Stand-up Auswertung sofort in `#orga-bot` (normalerweise Mo–Fr 10:00 Uhr). |
| `/dm-all` | `nachricht` | Sendet eine Direktnachricht an alle echten Server-Mitglieder. |
| `/meeting-dm` | *keine* | Erinnert alle Mitglieder per DM an das nächste anstehende Meeting. |

---

## 🤖 Automatisierte Workflows

### 1. Tägliche asynchrone Stand-ups (Mo–Fr)
```
09:00 Uhr ➔ Bot sendet DM an alle 8: "Was ist dein Fokus für heute und gibt es Blocker?"
09:00–10:00 Uhr ➔ Mitglieder antworten dem Bot einfach per DM.
10:00 Uhr ➔ Bot postet kompaktes Status-Embed in #orga-bot (inkl. ⏳ Ausstehend-Liste).
```

### 2. Meeting-Erinnerungen & VC-Anwesenheit
```
24h vorher ➔ Ankündigung in #termine + persönliche DM an alle 8 Mitglieder.
1h vorher  ➔ Ankündigung in #termine + persönliche DM an alle 8 Mitglieder.
Startzeit  ➔ Scan aller Sprachkanäle ➔ Anwesenheitsprotokoll (X/8) in #meeting-protokolle
            ➔ Start-Ping @everyone in #termine ("Meeting beginnt jetzt!").
```

---

## 📄 OCR & Dokumenten-Verarbeitung

Der Bot liest Vorlesungsskripte und Notizen aus dem Ordner `data/` ein:
- **Digitale PDFs & Textdateien**: Standardmäßig liest der Bot `.pdf` (via `PyPDF2`) und `.txt` Dateien direkt ein.
- **Gescannte Dokumente & OCR**: Falls Vorlesungsfolien nur als Scans oder Bilder vorliegen, nutzt der Bot KI:Connect (GPT-4o), das multimodale Bild- und OCR-Verarbeitung nativ unterstützt (Bilder können an GPT-4o übergeben werden, um Text, Diagramme oder Modelle direkt in Markdown / Code / Mermaid zu rekonstruieren).

---

## 📢 Discord-Kanal-Zuordnung

- `#termine` (`1560255601798291577`): Meeting-Termine, Erinnerungen & Start-Alarm
- `#orga-bot` (`1560255747986559027`): Bot-Interaktionen & 10:00 Uhr Stand-up Report
- `#meeting-protokolle` (`1560255397754048610`): Automatische VC-Anwesenheitsprotokolle & Recaps
- `#vorlesung-material` (`1560255397754048609`): Vorlesungsmaterialien & Zusammenfassungen
- `#research-log` (`1560255397754048611`): Forschung & Quellen
- `#praktikum-quiz` (`1560255397754048605`): Quizfragen & Prüfungsvorbereitung

---

## 🛠️ Lokale Entwicklung & Start

```bash
# 1. Repository klonen
git clone https://github.com/FalseFade/discord-orga-bot.git
cd discord-orga-bot

# 2. Virtual Environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Dependencies installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen anlegen
cp .env.example .env

# 5. Starten
python bot.py
```
