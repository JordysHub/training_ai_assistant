import asyncio
from datetime import date, timedelta
from fastmcp import Client

today = date.today().isoformat()
monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()


async def main():
    async with Client("http://localhost:8000/dev/mcp") as c:
        print("TOOLS:", sorted(t.name for t in await c.list_tools()))

        await c.call_tool("set_athlete_profile", {
            "profile": {"body_mass_kg": 74, "height_m": 1.83, "ftp_w": 220}})
        print("PROFILE:", (await c.call_tool("get_athlete_profile", {})).data)

        print("SESSION:", (await c.call_tool("log_session", {
            "date": today, "sport": "bike", "type": "Z2",
            "duration_min": 120, "rpe": 5, "activity_id": "test-1"})).data)

        print("DUP:", (await c.call_tool("log_session", {
            "date": today, "sport": "bike", "duration_min": 120,
            "rpe": 5, "activity_id": "test-1"})).data)

        print("PLANS:", (await c.call_tool("add_plans", {"rows": [
            {"date": monday, "sport": "climb", "type": "hangboard",
             "target": "80% max, 3x5x7s", "duration_min": 40}]})).data)

        w = (await c.call_tool("get_week", {})).data
        print("WEEK:", w["week_start"], "plans", len(w["plans"]),
              "sessions", len(w["sessions"]))

        print("CHECKIN:", (await c.call_tool("log_checkin", {
            "date": today, "body_mass_kg": 74.2, "sleep_h": 7.5,
            "fatigue_1_5": 2, "soreness_1_5": 2})).data)

        print("ROLLUP:", (await c.call_tool("get_rollup", {"weeks": 2})).data["acwr"])


asyncio.run(main())