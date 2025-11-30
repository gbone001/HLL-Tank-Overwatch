from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class KillEvent:
    time: datetime
    killer: Optional[str]
    victim: Optional[str]
    weapon: Optional[str]
    distance: Optional[int]
    teamkill: bool
    suicide: bool


@dataclass
class PlayerScore:
    name: str
    kills: int
    deaths: int
    score: int
    squad: Optional[str] = None


@dataclass
class TeamScore:
    name: str
    score: int
    players: List[PlayerScore]


@dataclass
class ScoreboardSnapshot:
    match_id: str
    updated_at: datetime
    teams: List[TeamScore]
