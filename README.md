# 🤖 Discord ORGA Bot – Autonomer Projektmanager & Web-Dashboard

Produktionsreifer Discord-Bot (v2.x) mit integrierter **KI:Connect-API** (OpenAI-kompatibel), **SQLite-Datenbank**, asynchroner Stand-up Routine, Aufgabenverteilung, VC-Anwesenheitserfassung und einem reaktiven **Web-Dashboard** (Dark Mode). Entwickelt für studentische Teams (8 Personen).

---

## 🌟 Kernfunktionen

### 1. 📅 Meetings & VC-Anwesenheit (`cogs/meeting.py`)
- `/meeting [datum_uhrzeit] [thema]`: Parst natürliches Deutsch (z. B. "morgen 15:00") und plant Erinnerungen.
- **Erinnerungen**:
  - 24 Stunden vorher: Ankündigung in `#termine` + persönliche DM an alle 8 Mitglieder.
  - 1 Stunde vorher: Ankündigung in `#termine` + persönliche DM an alle 8 Mitglieder.
- **VC-Anwesenheitsprotokoll zu Meeting-Beginn**:
  - Genau zum Startzeitpunkt scannt der Bot alle Sprachkanäle (VC).
  - Ermittelt, wie viele Personen anwesend sind und gleicht dies mit den Klarnamen ab.
  - Postet das fertige Anwesenheitsprotokoll direkt in `#meeting-protokolle`.
  - Sendet einen Start-Ping mit `@everyone` in `#termine`.

### 2. 👥 Team-Vorstellung & Klarnamen (`cogs/team.py`)
- `/introduce [voller_name]`: Jedes Mitglied stellt sich dem Bot mit vollständigem Namen vor (z. B. "Max Mustermann"). Der Bot verknüpft Discord-Account und Klarname in der Datenbank.
- `/team`: Zeigt die komplette Übersicht aller 8 Mitglieder mit Klarnamen, Discord-Tags und offenen Aufgaben.

### 3. 📋 Aufgabenverteilung (`cogs/delegate.py`)
- `/delegate [projekt_ziel]`: Zerlegt ein Projektziel via KI:Connect in konkrete Unteraufgaben und weist sie im Round-Robin-Verfahren den 8 Mitgliedern mit Pings zu.
- `/my-tasks`: Zeigt die persönlichen offenen Aufgaben des Nutzers.
- `/task-done [id]`: Schließt eine Aufgabe ab.

### 4. 🌅 Asynchrone Stand-ups (`cogs/notify.py`)
- **Mo–Fr 09:00 Uhr**: Automatische DM an jedes Teammitglied (*"Morgen! Was ist dein Fokus für heute und gibt es Blocker?"*).
- **DM-Listener**: Eingehende Antworten werden erfasst und gespeichert.
- **Mo–Fr 10:00 Uhr**: Automatischer Tagesbericht in `#orga-bot` mit allen Antworten und ausstehenden Mitgliedern.

### 5. 😈 Devil's Advocate / Investor Review (`cogs/critique.py`)
- `/critique [idee_text]`: Prüft Geschäftsideen gnadenlos nach **Desirability**, **Viability**, **Feasibility** und logischen Lücken.

### 6. 📝 Smart Protocol Parser (`cogs/recap.py`)
- `/recap [text]`: Analysiert lange Markdown-Protokolle (bis zu 4096 Tokens) und extrahiert Beschlüsse, personenspezifische To-Dos und offene Fragen.

### 7. 🎓 Vorlesungs-Quiz (`cogs/quiz.py`)
- `/quiz`: Liest Vorlesungsskripte aus `data/` ein, stellt anspruchsvolle Verständnisfragen und bewertet Antworten interaktiv über Discord-Buttons und Modals.

---

## 🌐 Web-Dashboard (`localhost:8080`)

- **📊 Dashboard**: Übersicht über Aufgaben, Stand-up Status, anstehende Meetings und Teamstatistiken.
- **📋 Task Board**: Aufgaben filtern, neue Aufgaben anlegen, Status wechseln (`Offen` ➔ `Erledigt`).
- **🌅 Stand-up Monitor**: Antworten des Tages mit Fokus & Blockern einsehen, Datumswahl.
- **📅 Meetings**: Meetings anlegen, bearbeiten, löschen oder 1-Klick DM-Broadcast an alle 8 senden.
- **📝 Recaps**: Archiv aller KI-Protokoll-Analysen.

---

## 🚀 Deployment (24/7 in der Cloud)

### Mit Railway.app (Empfohlen):
1. Auf [railway.app](https://railway.app) einloggen.
2. **New Project** ➔ **Deploy from GitHub repo** ➔ `FalseFade/discord-orga-bot` auswählen.
3. Im Tab **Variables** folgende Werte eintragen:
   - `DISCORD_TOKEN`
   - `KICONNECT_API_KEY`
   - `KICONNECT_BASE_URL`
   - `KICONNECT_MODEL`
   - `CHANNEL_TERMINE`
   - `CHANNEL_ORGA_BOT`
   - `CHANNEL_VORLESUNG_MATERIAL`
   - `CHANNEL_MEETING_PROTOKOLLE`
   - `CHANNEL_RESEARCH_LOG`
   - `CHANNEL_PRAKTIKUM_QUIZ`
   - `WEB_PORT` (z.B. `8080`)
4. Unter **Settings** ➔ **Networking** ➔ **Generate Domain** klicken, um die Web-Dashboard URL zu erhalten.

---

## 💻 Lokaler Start

```bash
# Virtuelle Umgebung
python3 -m venv venv
source venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt

# .env ausfüllen
cp .env.example .env

# Starten
python bot.py
```
