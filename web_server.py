"""
Web-Dashboard – aiohttp-basierte Weboberfläche für den ORGA Bot.

Stellt eine Single-Page-App bereit, die über REST-API-Endpunkte mit der
Datenbank und dem Discord-Bot interagiert.
Inklusive:
- Meetings CRUD + DM Notification Trigger
- Recaps History
- Task Board (Aufgabenverwaltung pro User / Projekt)
- Stand-up Übersicht (Tagesstatus, Blocker, Antworten)
- Live Stats & Server-Mitglieder
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import discord
from aiohttp import web

import database as db

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


# ═══════════════════════════════════════════════════════════════════════════
# HTML-Seite
# ═══════════════════════════════════════════════════════════════════════════

async def index(request: web.Request) -> web.Response:
    """Liefert die Dashboard-SPA aus."""
    html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
    return web.Response(text=html, content_type="text/html")


# ═══════════════════════════════════════════════════════════════════════════
# API – Meetings
# ═══════════════════════════════════════════════════════════════════════════

async def api_meetings_list(request: web.Request) -> web.Response:
    """GET /api/meetings – Alle Meetings abrufen."""
    meetings = await db.get_meetings()
    now = datetime.now().isoformat()
    for m in meetings:
        if m["status"] == "scheduled" and m["scheduled_at"] < now:
            await db.update_meeting(m["id"], status="completed")
            m["status"] = "completed"
    return web.json_response(meetings)


async def api_meeting_create(request: web.Request) -> web.Response:
    """POST /api/meetings – Neues Meeting erstellen."""
    try:
        data = await request.json()
        topic = data.get("topic", "").strip()
        scheduled_at_str = data.get("scheduled_at", "").strip()

        if not topic or not scheduled_at_str:
            return web.json_response({"error": "Topic und Zeitpunkt sind erforderlich."}, status=400)

        scheduled_at = datetime.fromisoformat(scheduled_at_str)
        if scheduled_at <= datetime.now():
            return web.json_response({"error": "Zeitpunkt muss in der Zukunft liegen."}, status=400)

        meeting_id = await db.add_meeting(
            topic=topic,
            scheduled_at=scheduled_at,
            created_by="Web-Dashboard",
            created_by_id=0,
        )

        _schedule_meeting_reminders(request.app, meeting_id, topic, scheduled_at)

        return web.json_response({"status": "ok", "id": meeting_id})
    except (json.JSONDecodeError, ValueError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


async def api_meeting_update(request: web.Request) -> web.Response:
    """PUT /api/meetings/{id} – Meeting aktualisieren."""
    meeting_id = int(request.match_info["id"])
    existing = await db.get_meeting(meeting_id)
    if not existing:
        return web.json_response({"error": "Meeting nicht gefunden."}, status=404)

    try:
        data = await request.json()
        topic = data.get("topic", existing["topic"]).strip()
        scheduled_at_str = data.get("scheduled_at", existing["scheduled_at"]).strip()
        scheduled_at = datetime.fromisoformat(scheduled_at_str)

        await db.update_meeting(meeting_id, topic=topic, scheduled_at=scheduled_at.isoformat())

        scheduler = request.app.get("scheduler")
        if scheduler:
            for suffix in ("24h", "1h"):
                job_id = f"meeting-{suffix}-{meeting_id}"
                if scheduler.get_job(job_id):
                    scheduler.remove_job(job_id)
            _schedule_meeting_reminders(request.app, meeting_id, topic, scheduled_at)

        return web.json_response({"status": "ok"})
    except (json.JSONDecodeError, ValueError) as exc:
        return web.json_response({"error": str(exc)}, status=400)


async def api_meeting_delete(request: web.Request) -> web.Response:
    """DELETE /api/meetings/{id} – Meeting löschen."""
    meeting_id = int(request.match_info["id"])
    existing = await db.get_meeting(meeting_id)
    if not existing:
        return web.json_response({"error": "Meeting nicht gefunden."}, status=404)

    scheduler = request.app.get("scheduler")
    if scheduler:
        for suffix in ("24h", "1h"):
            job_id = f"meeting-{suffix}-{meeting_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

    await db.delete_meeting(meeting_id)
    return web.json_response({"status": "ok"})


async def api_meeting_notify(request: web.Request) -> web.Response:
    """POST /api/meetings/{id}/notify – DM an alle Mitglieder senden."""
    meeting_id = int(request.match_info["id"])
    meeting = await db.get_meeting(meeting_id)
    if not meeting:
        return web.json_response({"error": "Meeting nicht gefunden."}, status=404)

    bot: discord.Client = request.app["bot"]
    results = await _send_dm_to_all_members(bot, meeting["topic"], meeting["scheduled_at"])
    await db.update_meeting(meeting_id, dm_sent=1)

    return web.json_response(results)


# ═══════════════════════════════════════════════════════════════════════════
# API – Recaps
# ═══════════════════════════════════════════════════════════════════════════

async def api_recaps_list(request: web.Request) -> web.Response:
    """GET /api/recaps – Alle Recaps abrufen."""
    recaps = await db.get_recaps()
    return web.json_response(recaps)


# ═══════════════════════════════════════════════════════════════════════════
# API – Tasks (Task Board)
# ═══════════════════════════════════════════════════════════════════════════

async def api_tasks_list(request: web.Request) -> web.Response:
    """GET /api/tasks – Alle Aufgaben abrufen (optional mit Filtern)."""
    status = request.query.get("status")
    user_id_str = request.query.get("user_id")
    user_id = int(user_id_str) if user_id_str and user_id_str.isdigit() else None

    tasks = await db.get_tasks(status=status, user_id=user_id)
    return web.json_response(tasks)


async def api_task_create(request: web.Request) -> web.Response:
    """POST /api/tasks – Neue Aufgabe erstellen."""
    try:
        data = await request.json()
        task_desc = data.get("task_desc", "").strip()
        user_name = data.get("user_name", "").strip() or "Unzugewiesen"
        user_id = int(data.get("user_id", 0))
        project = data.get("project", "").strip()
        deadline = data.get("deadline", "").strip() or None

        if not task_desc:
            return web.json_response({"error": "Aufgabenbeschreibung ist erforderlich."}, status=400)

        task_id = await db.add_task(
            user_id=user_id,
            user_name=user_name,
            task_desc=task_desc,
            project=project,
            deadline=deadline,
        )
        return web.json_response({"status": "ok", "id": task_id})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)


async def api_task_update(request: web.Request) -> web.Response:
    """PUT /api/tasks/{id} – Aufgabe aktualisieren (z.B. Status ändern)."""
    task_id = int(request.match_info["id"])
    task = await db.get_task(task_id)
    if not task:
        return web.json_response({"error": "Aufgabe nicht gefunden."}, status=404)

    try:
        data = await request.json()
        updates = {}
        for key in ("task_desc", "status", "deadline", "project", "user_name", "user_id"):
            if key in data:
                updates[key] = data[key]

        if updates.get("status") == "done" and not task.get("completed_at"):
            updates["completed_at"] = datetime.now().isoformat()
        elif updates.get("status") == "open":
            updates["completed_at"] = None

        await db.update_task(task_id, **updates)
        return web.json_response({"status": "ok"})
    except Exception as exc:
        return web.json_response({"error": str(exc)}, status=400)


async def api_task_delete(request: web.Request) -> web.Response:
    """DELETE /api/tasks/{id} – Aufgabe löschen."""
    task_id = int(request.match_info["id"])
    task = await db.get_task(task_id)
    if not task:
        return web.json_response({"error": "Aufgabe nicht gefunden."}, status=404)

    await db.delete_task(task_id)
    return web.json_response({"status": "ok"})


# ═══════════════════════════════════════════════════════════════════════════
# API – Stand-ups
# ═══════════════════════════════════════════════════════════════════════════

async def api_standups_list(request: web.Request) -> web.Response:
    """GET /api/standups – Stand-up Antworten für ein Datum (default: heute)."""
    today = datetime.now().strftime("%Y-%m-%d")
    date = request.query.get("date", today)

    standups = await db.get_standups(date=date)
    dates = await db.get_standup_dates(limit=14)

    bot: discord.Client = request.app["bot"]
    all_members: list[dict] = []
    for guild in bot.guilds:
        for m in guild.members:
            if not m.bot:
                all_members.append({"id": m.id, "name": m.display_name})

    answered_ids = {s["user_id"] for s in standups}
    missing_members = [m for m in all_members if m["id"] not in answered_ids]

    return web.json_response({
        "date": date,
        "available_dates": dates,
        "standups": standups,
        "total_team": len(all_members),
        "answered_count": len(standups),
        "missing_members": missing_members,
    })


# ═══════════════════════════════════════════════════════════════════════════
# API – Server Members & Stats
# ═══════════════════════════════════════════════════════════════════════════

async def api_members_list(request: web.Request) -> web.Response:
    """GET /api/members – Liste aller Nicht-Bot-Mitglieder (inkl. Klarnamen)."""
    bot: discord.Client = request.app["bot"]
    team_dict = {m["user_id"]: m["full_name"] for m in await db.get_team_members()}
    members = []
    seen = set()
    for guild in bot.guilds:
        for m in guild.members:
            if not m.bot and m.id not in seen:
                seen.add(m.id)
                full_name = team_dict.get(m.id)
                display_label = f"{full_name} (@{m.display_name})" if full_name else m.display_name
                members.append({
                    "id": m.id,
                    "name": display_label,
                    "discord_name": m.display_name,
                    "full_name": full_name or "",
                    "guild": guild.name,
                })
    return web.json_response(members)


async def api_stats(request: web.Request) -> web.Response:
    """GET /api/stats – Umfassende Dashboard-Statistiken."""
    meetings = await db.get_meetings()
    recaps = await db.get_recaps()
    tasks = await db.get_tasks()
    today = datetime.now().strftime("%Y-%m-%d")
    today_standups = await db.get_standups(date=today)
    now = datetime.now().isoformat()

    upcoming = [m for m in meetings if m["status"] == "scheduled" and m["scheduled_at"] > now]
    completed = [m for m in meetings if m["status"] == "completed" or m["scheduled_at"] <= now]

    bot: discord.Client = request.app["bot"]
    member_count = 0
    guild_name = "–"
    for guild in bot.guilds:
        member_count += sum(1 for m in guild.members if not m.bot)
        guild_name = guild.name

    open_tasks = [t for t in tasks if t["status"] != "done"]
    done_tasks = [t for t in tasks if t["status"] == "done"]

    return web.json_response({
        "total_meetings": len(meetings),
        "upcoming_meetings": len(upcoming),
        "completed_meetings": len(completed),
        "total_recaps": len(recaps),
        "total_tasks": len(tasks),
        "open_tasks": len(open_tasks),
        "done_tasks": len(done_tasks),
        "today_standups_count": len(today_standups),
        "member_count": member_count,
        "guild_name": guild_name,
        "next_meeting": upcoming[0] if upcoming else None,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Hilfsfunktionen
# ═══════════════════════════════════════════════════════════════════════════

def _schedule_meeting_reminders(
    app: web.Application,
    meeting_id: int,
    topic: str,
    scheduled_at: datetime,
) -> None:
    scheduler = app.get("scheduler")
    bot = app.get("bot")
    if not scheduler or not bot:
        return

    from config import ORGA_CHANNEL_ID

    now = datetime.now(tz=scheduled_at.tzinfo) if scheduled_at.tzinfo else datetime.now()

    async def _send_reminder(prefix: str, send_dms: bool = False) -> None:
        time_str = scheduled_at.strftime("%d.%m.%Y um %H:%M Uhr")
        channel = bot.get_channel(ORGA_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"📅 Meeting-Erinnerung: {topic}",
                description=f"{prefix}\n\n**Thema:** {topic}\n**Wann:** {time_str}",
                color=discord.Color.blue(),
            )
            await channel.send(content="@everyone", embed=embed)

        if send_dms:
            await _send_dm_to_all_members(bot, topic, scheduled_at.isoformat())

    reminder_24h = scheduled_at - timedelta(hours=24)
    reminder_1h = scheduled_at - timedelta(hours=1)

    if reminder_24h > now:
        scheduler.add_job(
            _send_reminder,
            "date",
            run_date=reminder_24h,
            args=["⏳ Noch **24 Stunden** bis zum Meeting!", True],
            id=f"meeting-24h-{meeting_id}",
            replace_existing=True,
        )
    if reminder_1h > now:
        scheduler.add_job(
            _send_reminder,
            "date",
            run_date=reminder_1h,
            args=["🔔 Noch **1 Stunde** bis zum Meeting!", True],
            id=f"meeting-1h-{meeting_id}",
            replace_existing=True,
        )


async def _send_dm_to_all_members(
    bot: discord.Client,
    topic: str,
    scheduled_at_str: str,
) -> dict:
    try:
        scheduled_at = datetime.fromisoformat(scheduled_at_str)
        time_str = scheduled_at.strftime("%d.%m.%Y um %H:%M Uhr")
    except (ValueError, TypeError):
        time_str = scheduled_at_str

    embed = discord.Embed(
        title="📅 Meeting-Erinnerung",
        description=(
            f"Hey! Nicht vergessen:\n\n"
            f"**Thema:** {topic}\n"
            f"**Wann:** {time_str}\n\n"
            f"Bitte sei pünktlich! 🙏"
        ),
        color=discord.Color.blue(),
    )

    success = 0
    failed = 0
    skipped = 0

    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                skipped += 1
                continue
            try:
                await member.send(embed=embed)
                success += 1
                await asyncio.sleep(0.5)
            except discord.Forbidden:
                failed += 1
                log.warning("DM an %s nicht möglich", member.display_name)
            except Exception:
                failed += 1
                log.exception("DM-Fehler bei %s", member.display_name)

    log.info("DM-Benachrichtigung: %d gesendet, %d fehlgeschlagen", success, failed)
    return {"success": success, "failed": failed, "skipped_bots": skipped}


# ═══════════════════════════════════════════════════════════════════════════
# App-Factory
# ═══════════════════════════════════════════════════════════════════════════

async def create_web_app(bot: discord.Client, scheduler=None) -> web.Application:
    """Erstellt die aiohttp-Web-App mit allen Routen."""
    app = web.Application()
    app["bot"] = bot
    if scheduler:
        app["scheduler"] = scheduler

    # ── Routen ─────────────────────────────────────────────────────────────
    app.router.add_get("/", index)

    # Meetings
    app.router.add_get("/api/meetings", api_meetings_list)
    app.router.add_post("/api/meetings", api_meeting_create)
    app.router.add_put("/api/meetings/{id}", api_meeting_update)
    app.router.add_delete("/api/meetings/{id}", api_meeting_delete)
    app.router.add_post("/api/meetings/{id}/notify", api_meeting_notify)

    # Recaps
    app.router.add_get("/api/recaps", api_recaps_list)

    # Tasks (Task Board)
    app.router.add_get("/api/tasks", api_tasks_list)
    app.router.add_post("/api/tasks", api_task_create)
    app.router.add_put("/api/tasks/{id}", api_task_update)
    app.router.add_delete("/api/tasks/{id}", api_task_delete)

    # Stand-ups
    app.router.add_get("/api/standups", api_standups_list)

    # Members & Stats
    app.router.add_get("/api/members", api_members_list)
    app.router.add_get("/api/stats", api_stats)

    return app
