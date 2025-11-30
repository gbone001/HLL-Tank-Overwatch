from __future__ import annotations

from typing import Optional

import aiohttp

from broadcaster import EventSink
from events import KillEvent, ScoreboardSnapshot


class OBSSink(EventSink):
    """
    Sends killfeed and scoreboard events to the OBS-side service.

    base_url should point to the Cloudflare-exposed endpoint for the OBS PC,
    e.g. "https://jpkillfeed.anzr.org".
    """

    def __init__(self, base_url: str, secret: str = ""):
        self.base_url = base_url.rstrip("/")
        self.secret = secret
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _post(self, path: str, payload: dict) -> None:
        url = f"{self.base_url}{path}"
        session = await self._get_session()
        headers = {}
        if self.secret:
            headers["X-Obs-Secret"] = self.secret
        try:
            async with session.post(url, json=payload, headers=headers, timeout=3) as resp:
                if resp.status >= 400:
                    print(f"[OBS] POST {url} failed with status {resp.status}")
        except Exception as exc:
            print(f"[OBS] Error sending to {url}: {exc}")

    async def handle_kill(self, event: KillEvent) -> None:
        await self._post(
            "/obs/kill",
            {
                "type": "kill",
                "time": event.time.isoformat(),
                "killer": event.killer,
                "victim": event.victim,
                "weapon": event.weapon,
                "distance": event.distance,
                "teamkill": event.teamkill,
                "suicide": event.suicide,
            },
        )

    async def handle_scoreboard(self, snapshot: ScoreboardSnapshot) -> None:
        await self._post(
            "/obs/scoreboard",
            {
                "type": "scoreboard",
                "match_id": snapshot.match_id,
                "updated_at": snapshot.updated_at.isoformat(),
                "teams": [
                    {
                        "name": team.name,
                        "score": team.score,
                        "players": [
                            {
                                "name": player.name,
                                "kills": player.kills,
                                "deaths": player.deaths,
                                "score": player.score,
                                "squad": player.squad,
                            }
                            for player in team.players
                        ],
                    }
                    for team in snapshot.teams
                ],
            },
        )
