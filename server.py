import json
import os
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from core import store

DATA = Path(os.environ.get("DATA_DIR", "./data"))
PROFILE = DATA / "profile.json"
SECRET = os.environ.get("MCP_SECRET", "dev")

mcp = FastMCP("training-log")


@mcp.tool
def get_athlete_profile() -> dict:
    """Athlete profile: benchmarks, goal allocation, constraints, injury history, equipment."""
    if not PROFILE.exists():
        return {"error": "profile not set", "hint": "call set_athlete_profile"}
    return json.loads(PROFILE.read_text())


@mcp.tool
def set_athlete_profile(profile: dict) -> dict:
    """Overwrite the athlete profile. Pass the complete object, not a partial update."""
    PROFILE.write_text(json.dumps(profile, indent=2))
    return {"saved": profile}


@mcp.tool
def log_session(
    date: str,
    sport: str,
    type: str = None,
    duration_min: int = None,
    distance_km: float = None,
    elev_gain_m: int = None,
    avg_hr: int = None,
    avg_power_w: int = None,
    rpe: float = None,
    detail: str = None,
    source: str = "manual",
    activity_id: str = None,
    notes: str = None,
) -> dict:
    """Append one completed session. Append-only; sRPE-TL is computed from rpe x duration_min.
    sport: climb, boulder, bike, run, swim, strength, mobility, other.
    detail holds grades and style for climbing, or the hang protocol for fingerboard work.
    Returns entry_id and row count before and after, or a skip notice on duplicate activity_id."""
    return store.add_session(
        date=date, sport=sport, type=type, duration_min=duration_min,
        distance_km=distance_km, elev_gain_m=elev_gain_m, avg_hr=avg_hr,
        avg_power_w=avg_power_w, rpe=rpe, detail=detail, source=source,
        activity_id=activity_id, notes=notes,
    )


@mcp.tool
def add_plans(rows: list[dict]) -> dict:
    """Write planned sessions for a block. Each row needs date and sport; optionally
    type, target, duration_min, notes. Show the rows to the athlete before calling this."""
    return store.add_plans(rows)


@mcp.tool
def set_plan_status(plan_id: int, status: str) -> dict:
    """Mark a planned session as planned, done, missed or moved."""
    return store.set_plan_status(plan_id, status)


@mcp.tool
def get_week(start: str = None) -> dict:
    """Planned and completed sessions for the week containing the given date.
    Defaults to the current week. Use this before answering anything about the schedule."""
    return store.get_week(start)


@mcp.tool
def get_rollup(weeks: int = 6) -> dict:
    """Weekly load summary: hours, sRPE-TL total and per sport, ramp rate vs the prior
    4 weeks, acute:chronic ratio, and flags for breaches. Use this instead of computing
    load from raw sessions."""
    return store.rollup(weeks)


@mcp.tool
def log_checkin(
    date: str,
    body_mass_kg: float = None,
    sleep_h: float = None,
    fatigue_1_5: int = None,
    soreness_1_5: int = None,
    notes: str = None,
) -> dict:
    """Record the morning check-in. One row per date; calling again for the same date
    replaces it. This is the only tool that overwrites."""
    return store.upsert_checkin(
        date, body_mass_kg, sleep_h, fatigue_1_5, soreness_1_5, notes)


@mcp.tool
def recent_checkins(n: int = 14) -> list[dict]:
    """The most recent n check-ins, oldest first."""
    return store.recent_checkins(n)


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        path=f"/{SECRET}/mcp",
    )
