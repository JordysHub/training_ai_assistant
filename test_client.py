import asyncio
from fastmcp import Client


async def main():
    async with Client("http://localhost:8000/dev/mcp") as c:
        print([t.name for t in await c.list_tools()])
        print(await c.call_tool("get_athlete_profile", {}))
        print(await c.call_tool("log_checkin", {
            "body_mass_kg": 74.2,
            "sleep_h": 7.5,
            "fatigue_1_5": 2,
            "soreness_1_5": 2,
            "notes": "first test",
        }))
        print(await c.call_tool("recent_checkins", {"n": 5}))

asyncio.run(main())
