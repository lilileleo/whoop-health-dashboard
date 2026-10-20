"""SQLite persistence. Raw source files remain the audit trail."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DB = Path(os.environ.get("WHOOP_DB_PATH", str(DATA / "whoop.sqlite")))
KINDS = ("cycle", "recovery", "sleep", "workout")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=30)
    try:
        with conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS records (
          kind TEXT NOT NULL, record_id TEXT NOT NULL, occurred_at TEXT NOT NULL,
          version_at TEXT NOT NULL, source TEXT NOT NULL, payload TEXT NOT NULL,
          PRIMARY KEY(kind, record_id)
        );
        CREATE INDEX IF NOT EXISTS records_time ON records(kind, occurred_at);
        CREATE TABLE IF NOT EXISTS sync_runs (
          id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
          state TEXT NOT NULL, message TEXT NOT NULL, counts TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS annotations (
          day TEXT PRIMARY KEY, text TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS weights (day TEXT PRIMARY KEY, kg REAL NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, day TEXT NOT NULL, time TEXT NOT NULL DEFAULT '', category TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS training_templates (id INTEGER PRIMARY KEY, name TEXT NOT NULL, weekday INTEGER, kind TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS training_checks (week TEXT NOT NULL, template_id INTEGER NOT NULL REFERENCES training_templates(id), workout_id TEXT, state TEXT NOT NULL, scheduled_day TEXT, note TEXT NOT NULL DEFAULT '', PRIMARY KEY(week,template_id));
        """)
        conn.executemany("INSERT OR IGNORE INTO training_templates VALUES (?,?,?,?)", [
            (1,"第1练（待配置）",None,"any"),(2,"第2练（待配置）",None,"any"),
            (3,"第3练（待配置）",None,"any"),(4,"第4练（待配置）",None,"any")])
    os.chmod(DB, 0o600)
    # A killed process cannot finish its old sync. Existing WHOOP process locks
    # still serialize CLI and web refreshes.
    with connection() as conn:
        conn.execute("UPDATE sync_runs SET state='interrupted', finished_at=?, message='服务重启，上次同步已中断，请重新同步' WHERE state='running'", (now(),))


def identity(kind, row):
    return str(row.get("id") or (row.get("cycle_id") if kind == "recovery" else None)
               or "|".join(str(row.get(k, "")) for k in ("created_at", "start", "end")))


def import_snapshots():
    paths = sorted((DATA / "weeks").glob("*.json"))
    if (DATA / "latest.json").exists():
        paths.append(DATA / "latest.json")
    errors = []
    with connection() as conn:
        latest_fetch = None
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                stamp = data.get("fetched_at") or data.get("updated_at") or ""
                if stamp and (not latest_fetch or stamp > latest_fetch):
                    latest_fetch = stamp
                for kind in KINDS:
                    for row in data.get(kind, []):
                        occurred = row.get("start") or row.get("created_at")
                        if not occurred:
                            continue
                        version = row.get("updated_at") or stamp or occurred
                        conn.execute("""INSERT INTO records VALUES (?,?,?,?,?,?)
                        ON CONFLICT(kind, record_id) DO UPDATE SET
                          occurred_at=excluded.occurred_at,version_at=excluded.version_at,
                          source=excluded.source,payload=excluded.payload
                        WHERE julianday(excluded.version_at) >= julianday(records.version_at)""",
                        (kind, identity(kind, row), occurred, version, str(path.relative_to(ROOT)),
                         json.dumps(row, ensure_ascii=False)))
            except (ValueError, OSError, TypeError) as exc:
                errors.append(f"{path.name}: {type(exc).__name__}")
        if latest_fetch:
            conn.execute("INSERT OR REPLACE INTO metadata VALUES ('last_fetch', ?)", (latest_fetch,))
        conn.execute("INSERT OR REPLACE INTO metadata VALUES ('import_errors', ?)", (json.dumps(errors),))
    return counts()


def records():
    result = {k: [] for k in KINDS}
    with connection() as conn:
        for row in conn.execute("SELECT kind,payload FROM records ORDER BY occurred_at"):
            result[row["kind"]].append(json.loads(row["payload"]))
    return result


def counts():
    with connection() as conn:
        return {row[0]: row[1] for row in conn.execute("SELECT kind,COUNT(*) FROM records GROUP BY kind")}


def metadata():
    with connection() as conn:
        return {row[0]: row[1] for row in conn.execute("SELECT key,value FROM metadata")}


def sync_history():
    with connection() as conn:
        return [dict(r) | {"counts": json.loads(r["counts"])} for r in conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 10")]


def annotations():
    with connection() as conn:
        return {r["day"]: r["text"] for r in conn.execute("SELECT day,text FROM annotations")}


def save_annotation(day, text):
    with connection() as conn:
        if text.strip():
            conn.execute("INSERT OR REPLACE INTO annotations VALUES (?,?,?)", (day, text.strip(), now()))
        else:
            conn.execute("DELETE FROM annotations WHERE day=?", (day,))
