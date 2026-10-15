"""
Datenbank-Modul – Persistente Speicherung von Meetings, Recaps, Tasks, Stand-ups,
Team-Mitgliedern (Klarnamen) und Meeting-Anwesenheitsprotokollen.
Nutzt aiosqlite für vollständig asynchronen Zugriff.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import aiosqlite

log = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "orga_bot.db"

# ── Schema ─────────────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meetings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    topic           TEXT    NOT NULL,
    scheduled_at    TEXT    NOT NULL,
    created_by      TEXT    NOT NULL,
    created_by_id   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'scheduled',
    reminder_24h    INTEGER NOT NULL DEFAULT 0,
    reminder_1h     INTEGER NOT NULL DEFAULT 0,
    dm_sent         INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recaps (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text   TEXT    NOT NULL,
    summary         TEXT    NOT NULL,
    created_by      TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    user_name       TEXT    NOT NULL,
    task_desc       TEXT    NOT NULL,
    project         TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'open',
    deadline        TEXT,
    created_at      TEXT    NOT NULL,
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS standups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    user_name       TEXT    NOT NULL,
    response_raw    TEXT    NOT NULL,
    date            TEXT    NOT NULL,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS team_members (
    user_id         INTEGER PRIMARY KEY,
    full_name       TEXT    NOT NULL,
    discord_name    TEXT    NOT NULL,
    registered_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS attendance (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id      INTEGER NOT NULL DEFAULT 0,
    topic           TEXT    NOT NULL,
    scheduled_at    TEXT    NOT NULL,
    recorded_at     TEXT    NOT NULL,
    present_count   INTEGER NOT NULL,
    present_names   TEXT    NOT NULL,
    absent_names    TEXT    NOT NULL
);
"""


async def init_db() -> None:
    """Erstellt die Datenbanktabellen, falls sie nicht existieren."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.executescript(_SCHEMA)
        await conn.commit()
    log.info("💾 Datenbank initialisiert: %s", DB_PATH)


# ═══════════════════════════════════════════════════════════════════════════
# Team Members (Klarnamen-Zuordnung)
# ═══════════════════════════════════════════════════════════════════════════

async def add_or_update_team_member(user_id: int, full_name: str, discord_name: str) -> None:
    """Speichert oder aktualisiert den vollständigen Namen eines Teammitglieds."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO team_members (user_id, full_name, discord_name, registered_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                full_name = excluded.full_name,
                discord_name = excluded.discord_name,
                registered_at = excluded.registered_at
            """,
            (user_id, full_name, discord_name, datetime.now().isoformat()),
        )
        await conn.commit()


async def get_team_members() -> list[dict]:
    """Gibt alle registrierten Team-Mitglieder zurück."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM team_members ORDER BY full_name ASC")
        return [dict(r) for r in await cur.fetchall()]


async def get_team_member(user_id: int) -> dict | None:
    """Gibt das Profil eines einzelnen Teammitglieds zurück."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM team_members WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


# ═══════════════════════════════════════════════════════════════════════════
# Attendance (VC-Anwesenheitsprotokoll)
# ═══════════════════════════════════════════════════════════════════════════

async def add_attendance(
    meeting_id: int,
    topic: str,
    scheduled_at: str,
    present_count: int,
    present_names: str,
    absent_names: str,
) -> int:
    """Speichert ein automatisches VC-Anwesenheitsprotokoll."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            """
            INSERT INTO attendance
            (meeting_id, topic, scheduled_at, recorded_at, present_count, present_names, absent_names)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meeting_id,
                topic,
                scheduled_at,
                datetime.now().isoformat(),
                present_count,
                present_names,
                absent_names,
            ),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_attendances() -> list[dict]:
    """Gibt alle Anwesenheitsprotokolle zurück."""
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM attendance ORDER BY recorded_at DESC")
        return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════
# Meetings
# ═══════════════════════════════════════════════════════════════════════════

async def add_meeting(
    topic: str, scheduled_at: datetime, created_by: str, created_by_id: int = 0,
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO meetings (topic, scheduled_at, created_by, created_by_id, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (topic, scheduled_at.isoformat(), created_by, created_by_id, datetime.now().isoformat()),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_meetings(*, status: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if status:
            cur = await conn.execute(
                "SELECT * FROM meetings WHERE status = ? ORDER BY scheduled_at ASC", (status,)
            )
        else:
            cur = await conn.execute("SELECT * FROM meetings ORDER BY scheduled_at DESC")
        return [dict(r) for r in await cur.fetchall()]


async def get_meeting(meeting_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_meeting(meeting_id: int, **kw: str | int) -> None:
    allowed = {"topic", "scheduled_at", "status", "reminder_24h", "reminder_1h", "dm_sent"}
    async with aiosqlite.connect(DB_PATH) as conn:
        for k, v in kw.items():
            if k in allowed:
                await conn.execute(f"UPDATE meetings SET {k} = ? WHERE id = ?", (v, meeting_id))
        await conn.commit()


async def delete_meeting(meeting_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
        await conn.commit()


# ═══════════════════════════════════════════════════════════════════════════
# Recaps
# ═══════════════════════════════════════════════════════════════════════════

async def add_recap(original_text: str, summary: str, created_by: str) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO recaps (original_text, summary, created_by, created_at) VALUES (?, ?, ?, ?)",
            (original_text, summary, created_by, datetime.now().isoformat()),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_recaps() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM recaps ORDER BY created_at DESC")
        return [dict(r) for r in await cur.fetchall()]


# ═══════════════════════════════════════════════════════════════════════════
# Tasks
# ═══════════════════════════════════════════════════════════════════════════

async def add_task(
    user_id: int,
    user_name: str,
    task_desc: str,
    project: str = "",
    deadline: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO tasks (user_id, user_name, task_desc, project, deadline, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, user_name, task_desc, project, deadline, datetime.now().isoformat()),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_tasks(
    *, status: str | None = None, user_id: int | None = None,
) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if user_id is not None:
            query += " AND user_id = ?"
            params.append(user_id)
        query += " ORDER BY created_at DESC"
        cur = await conn.execute(query, params)
        return [dict(r) for r in await cur.fetchall()]


async def get_task(task_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def update_task(task_id: int, **kw: str | int | None) -> None:
    allowed = {"task_desc", "status", "deadline", "completed_at", "project", "user_id", "user_name"}
    async with aiosqlite.connect(DB_PATH) as conn:
        for k, v in kw.items():
            if k in allowed:
                await conn.execute(f"UPDATE tasks SET {k} = ? WHERE id = ?", (v, task_id))
        await conn.commit()


async def delete_task(task_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await conn.commit()


async def get_task_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status"
        )
        rows = await cur.fetchall()
        stats = {"open": 0, "in_progress": 0, "done": 0}
        for status, cnt in rows:
            stats[status] = cnt
        return stats


# ═══════════════════════════════════════════════════════════════════════════
# Stand-ups
# ═══════════════════════════════════════════════════════════════════════════

async def add_standup(
    user_id: int, user_name: str, response_raw: str, date: str,
) -> int:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "INSERT INTO standups (user_id, user_name, response_raw, date, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, user_name, response_raw, date, datetime.now().isoformat()),
        )
        await conn.commit()
        return cur.lastrowid  # type: ignore[return-value]


async def get_standups(date: str | None = None) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        if date:
            cur = await conn.execute(
                "SELECT * FROM standups WHERE date = ? ORDER BY created_at ASC", (date,)
            )
        else:
            cur = await conn.execute("SELECT * FROM standups ORDER BY date DESC, created_at ASC")
        return [dict(r) for r in await cur.fetchall()]


async def get_standup_for_user(user_id: int, date: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cur = await conn.execute(
            "SELECT * FROM standups WHERE user_id = ? AND date = ?", (user_id, date)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_standup_dates(limit: int = 14) -> list[str]:
    async with aiosqlite.connect(DB_PATH) as conn:
        cur = await conn.execute(
            "SELECT DISTINCT date FROM standups ORDER BY date DESC LIMIT ?", (limit,)
        )
        return [row[0] for row in await cur.fetchall()]
