from __future__ import annotations
import hmac, hashlib, os, typing as T
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from .score_engine import ScoreEngine, Team, VehicleClass

app = FastAPI()
ENGINE: ScoreEngine | None = None  # set by caller
SECRET = os.getenv("HLU_WEBHOOK_SHARED_SECRET","").encode()

class Killer(BaseModel):
    name: str
    steam_id: str
    team: Team
    squad_id: str | None = None

class VictimVehicle(BaseModel):
    side: Team
    class_: VehicleClass = Field(alias="class")
    name: str

class VehicleDestroyed(BaseModel):
    type: T.Literal["vehicle_destroyed"]
    timestamp: str
    killer: Killer
    victim_vehicle: VictimVehicle
    map: str | None = None
    match_id: str | None = None

class PlayerDeath(BaseModel):
    type: T.Literal["player_death"]
    timestamp: str
    team: Team
    squad_id: str | None = None

def _verify(req_body: bytes, signature: str | None):
    if not SECRET:
        return
    if not signature:
        raise HTTPException(401, "missing signature")
    mac = hmac.new(SECRET, req_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, signature):
        raise HTTPException(401, "bad signature")

@app.post("/event")
async def event(request: Request):
    raw = await request.body()
    _verify(raw, request.headers.get("X-HLU-Signature"))
    data = await request.json()
    global ENGINE
    if ENGINE is None:
        raise HTTPException(503, "engine not ready")

    t = data.get("type")
    if t == "vehicle_destroyed":
        evt = VehicleDestroyed.model_validate(data)
        ENGINE.on_tank_kill(evt.killer.team, evt.victim_vehicle.class_)
        if evt.killer.squad_id:
            ENGINE.on_squad_tank_kill(evt.killer.team, evt.killer.squad_id)
        return {"ok": True}
    elif t == "player_death":
        evt = PlayerDeath.model_validate(data)
        if evt.squad_id:
            ENGINE.on_squad_member_death(evt.team, evt.squad_id)
        return {"ok": True}
    else:
        return {"ignored": t}
