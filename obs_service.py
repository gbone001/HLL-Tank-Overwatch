from __future__ import annotations

import uvicorn
from datetime import datetime
import os
from typing import List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from pydantic import BaseModel


class KillEventIn(BaseModel):
    type: str = "kill"
    time: datetime
    killer: Optional[str] = None
    victim: Optional[str] = None
    weapon: Optional[str] = None
    distance: Optional[int] = None
    teamkill: bool = False
    suicide: bool = False


class PlayerScoreIn(BaseModel):
    name: str
    kills: int
    deaths: int
    score: int
    squad: Optional[str] = None


class TeamScoreIn(BaseModel):
    name: str
    score: int
    players: List[PlayerScoreIn]


class ScoreboardIn(BaseModel):
    type: str = "scoreboard"
    match_id: str
    updated_at: datetime
    teams: List[TeamScoreIn]


class WSManager:
    def __init__(self) -> None:
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead: List[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


app = FastAPI(title="OBS Overlay Service")

kill_manager = WSManager()
scoreboard_manager = WSManager()
latest_scoreboard: Optional[ScoreboardIn] = None
OBS_SECRET = os.getenv("OBS_SECRET", "")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def _require_obs_secret(request: Request) -> None:
    if not OBS_SECRET:
        return
    provided = request.headers.get("X-Obs-Secret", "")
    if provided != OBS_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")


@app.post("/obs/kill")
async def post_kill(event: KillEventIn, request: Request) -> dict:
    """Overwatch bot calls this to push a kill event."""
    _require_obs_secret(request)
    await kill_manager.broadcast({"type": "kill", "data": event.dict()})
    return {"status": "ok"}


@app.post("/obs/scoreboard")
async def post_scoreboard(snapshot: ScoreboardIn, request: Request) -> dict:
    """Overwatch bot calls this to push a scoreboard snapshot."""
    _require_obs_secret(request)
    global latest_scoreboard
    latest_scoreboard = snapshot
    await scoreboard_manager.broadcast({"type": "scoreboard", "data": snapshot.dict()})
    return {"status": "ok"}


@app.websocket("/ws/killfeed")
async def ws_killfeed(ws: WebSocket):
    await kill_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        kill_manager.disconnect(ws)


@app.websocket("/ws/scoreboard")
async def ws_scoreboard(ws: WebSocket):
    await scoreboard_manager.connect(ws)
    if latest_scoreboard is not None:
        await ws.send_json({"type": "scoreboard", "data": latest_scoreboard.dict()})

    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        scoreboard_manager.disconnect(ws)


if __name__ == "__main__":
    uvicorn.run("obs_service:app", host="0.0.0.0", port=8000)
