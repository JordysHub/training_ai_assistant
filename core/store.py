import os
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "./data"))
DATA.mkdir(parents=True, exist_ok=True)
DB = DATA / "training.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    entry_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    sport        TEXT NOT NULL,
    type         TEXT,
    duration_min INTEGER,
    distance_km  REAL,
    elev_gain_m  INTEGER,
    avg_hr       INTEGER,
    avg_power_w  INTEGER,
    rpe          REAL,
    srpe_tl      REAL,
    detail       TEXT,
    source       TEXT NOT NULL DEFAULT 'manual',
    activity_id  TEXT UNIQUE,
    status       TEXT NOT NULL DEFAULT 'normal',
    notes        TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS plans (
    plan_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT NOT NULL,
    sport        TEXT NOT NULL,
    type         TEXT,
    target       TEXT,
    duration_min INTEGER,
    status       TEXT NOT NULL DEFAULT 'planned',
    notes        TEXT
);
CREATE TABLE IF NOT EXISTS checkins (
    date         TEXT PRIMARY KEY,
    body_mass_kg REAL,
    sleep_h      REAL,
    fatigue_1_5  INTEGER,
    soreness_1_5 INTEGER,
    notes        TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions(date);
CREATE INDEX IF NOT EXISTS idx_plans_date ON plans(date);
"""

SPORTS = {"climb", "boulder", "bike", "run", "swim", "strength", "mobility", "other"}


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def add_session(
    date, sport, type=None, duration_min=None, distance_km=None,
    elev_gain_m=None, avg_hr=None, avg_power_w=None, rpe=None,
    detail=None, source="manual", activity_id=None, notes=None,
):
    if sport not in SPORTS:
        raise ValueError(f"sport must be one of {sorted(SPORTS)}")
    datetime.strptime(date, "%Y-%m-%d")
    srpe = round(rpe * duration_min, 1) if rpe and duration_min else None

    with conn() as c:
        if activity_id:
            hit = c.execute(
                "SELECT entry_id FROM sessions WHERE activity_id = ?", (activity_id,)
            ).fetchone()
            if hit:
                return {"skipped": "duplicate activity_id", "entry_id": hit["entry_id"]}
        before = c.execute("SELECT COUNT(*) n FROM sessions").fetchone()["n"]
        cur = c.execute(
            """INSERT INTO sessions
               (date, sport, type, duration_min, distance_km, elev_gain_m,
                avg_hr, avg_power_w, rpe, srpe_tl, detail, source, activity_id, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, sport, type, duration_min, distance_km, elev_gain_m,
             avg_hr, avg_power_w, rpe, srpe, detail, source, activity_id, notes),
        )
        return {
            "entry_id": cur.lastrowid, "srpe_tl": srpe,
            "rows_before": before, "rows_after": before + 1,
        }


def add_plans(rows):
    with conn() as c:
        before = c.execute("SELECT COUNT(*) n FROM plans").fetchone()["n"]
        for r in rows:
            if r["sport"] not in SPORTS:
                raise ValueError(f"sport must be one of {sorted(SPORTS)}")
            datetime.strptime(r["date"], "%Y-%m-%d")
            c.execute(
                """INSERT INTO plans (date, sport, type, target, duration_min, notes)
                   VALUES (?,?,?,?,?,?)""",
                (r["date"], r["sport"], r.get("type"), r.get("target"),
                 r.get("duration_min"), r.get("notes")),
            )
        after = c.execute("SELECT COUNT(*) n FROM plans").fetchone()["n"]
    return {"rows_before": before, "rows_after": after}


def set_plan_status(plan_id, status):
    if status not in {"planned", "done", "missed", "moved"}:
        raise ValueError("status must be planned, done, missed or moved")
    with conn() as c:
        c.execute("UPDATE plans SET status = ? WHERE plan_id = ?", (status, plan_id))
        return _rows(c.execute("SELECT * FROM plans WHERE plan_id = ?", (plan_id,)))[0]


def get_week(start=None):
    d = date.fromisoformat(start) if start else date.today()
    monday = d - timedelta(days=d.weekday())
    sunday = monday + timedelta(days=6)
    a, b = monday.isoformat(), sunday.isoformat()
    with conn() as c:
        return {
            "week_start": a,
            "week_end": b,
            "plans": _rows(c.execute(
                "SELECT * FROM plans WHERE date BETWEEN ? AND ? ORDER BY date", (a, b))),
            "sessions": _rows(c.execute(
                "SELECT * FROM sessions WHERE date BETWEEN ? AND ? ORDER BY date", (a, b))),
        }


def upsert_checkin(date, body_mass_kg=None, sleep_h=None,
                   fatigue_1_5=None, soreness_1_5=None, notes=None):
    for v, name in ((fatigue_1_5, "fatigue_1_5"), (soreness_1_5, "soreness_1_5")):
        if v is not None and not 1 <= v <= 5:
            raise ValueError(f"{name} must be 1-5")
    with conn() as c:
        c.execute(
            """INSERT INTO checkins
               (date, body_mass_kg, sleep_h, fatigue_1_5, soreness_1_5, notes)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(date) DO UPDATE SET
                 body_mass_kg=excluded.body_mass_kg, sleep_h=excluded.sleep_h,
                 fatigue_1_5=excluded.fatigue_1_5, soreness_1_5=excluded.soreness_1_5,
                 notes=excluded.notes""",
            (date, body_mass_kg, sleep_h, fatigue_1_5, soreness_1_5, notes),
        )
        return _rows(c.execute("SELECT * FROM checkins WHERE date = ?", (date,)))[0]


def recent_checkins(n=14):
    with conn() as c:
        rows = _rows(c.execute("SELECT * FROM checkins ORDER BY date DESC LIMIT ?", (n,)))
    return list(reversed(rows))


def rollup(weeks=6):
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    first = monday - timedelta(weeks=weeks - 1)
    with conn() as c:
        rows = _rows(c.execute(
            "SELECT date, sport, duration_min, srpe_tl FROM sessions "
            "WHERE date >= ? AND status = 'normal'",
            ((first - timedelta(days=28)).isoformat(),)))

    out = []
    for i in range(weeks):
        wa = first + timedelta(weeks=i)
        wb = wa + timedelta(days=6)
        wk = [r for r in rows if wa.isoformat() <= r["date"] <= wb.isoformat()]
        by_sport = {}
        for r in wk:
            by_sport[r["sport"]] = round(
                by_sport.get(r["sport"], 0) + (r["srpe_tl"] or 0), 1)
        out.append({
            "week_start": wa.isoformat(),
            "hours": round(sum(r["duration_min"] or 0 for r in wk) / 60, 1),
            "srpe_tl": round(sum(r["srpe_tl"] or 0 for r in wk), 1),
            "by_sport": by_sport,
            "sessions": len(wk),
        })

    for i, w in enumerate(out):
        prior = [x["srpe_tl"] for x in out[max(0, i - 4):i] if x["srpe_tl"] > 0]
        base = sum(prior) / len(prior) if prior else 0
        w["ramp_pct"] = round((w["srpe_tl"] - base) / base * 100, 1) if base else None

    acute = sum(r["srpe_tl"] or 0 for r in rows
                if r["date"] > (today - timedelta(days=7)).isoformat())
    chronic = sum(r["srpe_tl"] or 0 for r in rows
                  if r["date"] > (today - timedelta(days=28)).isoformat()) / 4
    acwr = round(acute / chronic, 2) if chronic else None

    flags = []
    if acwr and not 0.8 <= acwr <= 1.3:
        flags.append(f"acute:chronic ratio {acwr} outside 0.8-1.3")
    if out and out[-1]["ramp_pct"] and out[-1]["ramp_pct"] > 10:
        flags.append(f"ramp {out[-1]['ramp_pct']}% exceeds 10%")

    return {"weeks": out, "acute_7d": round(acute, 1),
            "chronic_28d_avg": round(chronic, 1), "acwr": acwr, "flags": flags}