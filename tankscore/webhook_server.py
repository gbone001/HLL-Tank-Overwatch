from __future__ import annotations
import hmac, hashlib, os, typing as T
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from .score_engine import ScoreEngine, Team
from .vehicle_map import classify_by_name
from .store import append_jsonl, now_ts

app = FastAPI()
ENGINE: ScoreEngine | None = None
SECRET = os.getenv("HLU_WEBHOOK_SHARED_SECRET","").encode()

# Pydantic v1/v2 helper
def _validate(model_cls, data: dict):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)   # v2
    return model_cls.parse_obj(data)            # v1

# --- Models ---
class Killer(BaseModel):
    name: str
    steam_id: str
    team: Team
    squad_id: str | None = None

class VictimVehicle(BaseModel):
    side: Team
    # make class optional and accept any string; we'll normalize later
    class_: str | None = Field(default=None, alias="class")
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
    if ENGINE is None:
        raise HTTPException(503, "engine not ready")

    t = data.get("type")
    if t == "vehicle_destroyed":
        evt = _validate(VehicleDestroyed, data)
        # --- fallback classification by name if class is missing/None ---
        raw_cls = evt.victim_vehicle.class_
        mapped_cls = classify_by_name(evt.victim_vehicle.name) if raw_cls is None else None
        victim_cls = (raw_cls or mapped_cls or "MEDIUM").upper()
        # Log when we truly couldn't classify by provided class or name
        if raw_cls is None and mapped_cls is None:
            print(f"[TankScore] Add to vehicles.yml: '{evt.victim_vehicle.name}': <LIGHT|MEDIUM|HEAVY|TD>")
        if victim_cls not in {"LIGHT","MEDIUM","HEAVY","TD"}:
            print(f"[TankScore] Unknown vehicle class '{victim_cls}' for name '{evt.victim_vehicle.name}'")
            # ignore non-tank classes safely
            return {"ignored": f"non-tank class: {victim_cls}"}
        # scoring & streak
        ENGINE.on_tank_kill(evt.killer.team, victim_cls)  # type: ignore[arg-type]
        if evt.killer.squad_id:
            ENGINE.on_squad_tank_kill(evt.killer.team, evt.killer.squad_id)
        # persist
        append_jsonl("tank_kills.jsonl", {
            "ts": now_ts(),
            "killer_team": evt.killer.team,
            "killer_squad": evt.killer.squad_id,
            "victim_team": evt.victim_vehicle.side,
            "victim_class": victim_cls,
            "victim_name": evt.victim_vehicle.name,
            "map": evt.map,
            "match_id": evt.match_id,
        })
        return {"ok": True}

    if t == "player_death":
        evt = _validate(PlayerDeath, data)
        if evt.squad_id:
            ENGINE.on_squad_member_death(evt.team, evt.squad_id)
        return {"ok": True}

    return {"ignored": t}
