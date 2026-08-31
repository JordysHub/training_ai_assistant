import json
import os
from datetime import date
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier
from starlette.responses import JSONResponse

DATA = Path(os.environ.get("DATA_DIR", "./data"))
DATA.mkdir(parents=True, exist_ok=True)
PROFILE = DATA / "profile.json"
CHECKINS = DATA / "checkins.jsonl"
SECRET = os.environ.get("MCP_SECRET", "dev")
token = os.environ.get("MCP_AUTH_TOKEN")
mcp = FastMCP("training-log")


@mcp.tool
def get_athlete_profile() -> dict:
    """Return the athlete profile: benchmarks, goal allocation, constraints, injuries."""
    if not PROFILE.exists():
        return {"error": "profile.json not found", "expected_path": str(PROFILE)}
    return json.loads(PROFILE.read_text())


@mcp.tool
def log_checkin(
    body_mass_kg: float,
    sleep_h: float,
    fatigue_1_5: int,
    soreness_1_5: int,
    notes: str = "",
) -> dict:
    """Append one morning check-in. Append-only. Returns row count before and after."""
    if not 1 <= fatigue_1_5 <= 5 or not 1 <= soreness_1_5 <= 5:
        raise ValueError("fatigue_1_5 and soreness_1_5 must be integers from 1 to 5")
    if not 40 <= body_mass_kg <= 150:
        raise ValueError("body_mass_kg outside plausible range")

    before = sum(1 for _ in CHECKINS.open()) if CHECKINS.exists() else 0
    row = {
        "date": date.today().isoformat(),
        "body_mass_kg": body_mass_kg,
        "sleep_h": sleep_h,
        "fatigue_1_5": fatigue_1_5,
        "soreness_1_5": soreness_1_5,
        "notes": notes,
        "source": "manual",
    }
    with CHECKINS.open("a") as f:
        f.write(json.dumps(row) + "\n")
    return {"written": row, "rows_before": before, "rows_after": before + 1}


@mcp.tool
def recent_checkins(n: int = 14) -> list[dict]:
    """Return the most recent n check-ins, oldest first."""
    if not CHECKINS.exists():
        return []
    return [json.loads(line) for line in CHECKINS.read_text().splitlines()[-n:]]

@mcp.tool
def set_athlete_profile(profile: dict) -> dict:
    """Overwrite the athlete profile. Benchmarks, constraints, injury history, equipment."""
    PROFILE.write_text(json.dumps(profile, indent=2))
    return {"saved": profile}


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
