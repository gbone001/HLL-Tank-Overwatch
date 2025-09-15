from __future__ import annotations
import os, time, threading
from typing import Dict, Literal, Optional, DefaultDict
from collections import defaultdict

Team = Literal["ALLIES","AXIS"]
VehicleClass = Literal["LIGHT","MEDIUM","HEAVY","TD"]

class ScoreEngine:
    """
    Centralised match-scoring state:
      - Phase 1: mid hold (3rd point) + '4th point held'(>=4 sectors) — per-second accrual
      - Phase 2: tank kills (event driven)
      - Phase 3: streak tracking + awards at end (configured now, used in Milestone 3+)
    """
    def __init__(self):
        self.mid_ppm = float(os.getenv("MID_POINTS_PER_MINUTE", "1.0"))
        self.fourth_ppm = float(os.getenv("FOURTH_POINTS_PER_MINUTE", "1.5"))
        self.tank_kill_pts = int(os.getenv("TANK_KILL_POINTS", "10"))
        self.vet_thresh = int(os.getenv("AWARD_VETERAN_THRESHOLD","3"))
        self.vet_pts = int(os.getenv("AWARD_VETERAN_POINTS","15"))
        self.ace_thresh = int(os.getenv("AWARD_ACE_THRESHOLD","5"))
        self.ace_pts = int(os.getenv("AWARD_ACE_POINTS","20"))
        self.ironhide_pts = int(os.getenv("AWARD_IRONHIDE_POINTS","25"))

        self.control: Dict[Team, set[int]] = {"ALLIES": set(), "AXIS": set()}
        self.holding_mid_team: Optional[Team] = None
        self.last_tick = time.monotonic()

        self.score_mid_fourth: Dict[Team, float] = {"ALLIES": 0.0, "AXIS": 0.0}
        self.score_tanks: Dict[Team, int] = {"ALLIES": 0, "AXIS": 0}
        self.kills_by_class: Dict[Team, DefaultDict[VehicleClass, int]] = {
            "ALLIES": defaultdict(int),
            "AXIS": defaultdict(int),
        }

        # squad streaks: key = (team, squad_id)
        self.squads = {}
        self._lock = threading.RLock()
        # optional observers; callables that accept a string reason
        self._listeners = []  # type: ignore[var-annotated]

    def add_listener(self, func):
        """Register a callback invoked on important scoring changes.
        func(reason: str) will be called from the originating thread.
        Reasons: 'mid_change', 'tank_kill'
        """
        with self._lock:
            self._listeners.append(func)

    def _notify(self, reason: str):
        # fire-and-forget; never raise out
        for fn in list(self._listeners):
            try:
                fn(reason)
            except Exception:
                pass

    # ---------- Phase 1 ----------
    def set_sector_owner(self, sector_id: int, new_team: Optional[Team]):
        """Call this from your capture/ownership change handler."""
        with self._lock:
            prev_mid = self.holding_mid_team
            self.control["ALLIES"].discard(sector_id)
            self.control["AXIS"].discard(sector_id)
            if new_team:
                self.control[new_team].add(sector_id)
            # mid assumed sector_id == 3; change here if your map abstraction differs
            self.holding_mid_team = None
            if 3 in self.control["ALLIES"]:
                self.holding_mid_team = "ALLIES"
            elif 3 in self.control["AXIS"]:
                self.holding_mid_team = "AXIS"
        # notify outside lock
        if self.holding_mid_team != prev_mid:
            self._notify('mid_change')

    def tick(self):
        """Accrue per-second points for mid & '4th point held'."""
        with self._lock:
            now = time.monotonic()
            dt = now - self.last_tick
            self.last_tick = now
            if dt <= 0:
                return
            per_sec_mid = self.mid_ppm / 60.0
            per_sec_fourth = self.fourth_ppm / 60.0
            if self.holding_mid_team:
                self.score_mid_fourth[self.holding_mid_team] += per_sec_mid * dt
            for t in ("ALLIES","AXIS"):
                if len(self.control[t]) >= 4:
                    self.score_mid_fourth[t] += per_sec_fourth * dt

    # ---------- Phase 2 ----------
    def on_tank_kill(self, killer_team: Team, victim_class: VehicleClass):
        with self._lock:
            self.score_tanks[killer_team] += self.tank_kill_pts
            self.kills_by_class[killer_team][victim_class] += 1
        self._notify('tank_kill')

    # ---------- Phase 3 (squad streaks & awards) ----------
    def _squad_key(self, team: Team, squad_id: str):
        return (team, squad_id)

    def _ensure_squad(self, team: Team, squad_id: str):
        k = self._squad_key(team, squad_id)
        if k not in self.squads:
            self.squads[k] = {
                "tank_kills": 0,
                "current_streak": 0,
                "longest_streak": 0,
            }
        return self.squads[k]

    def on_squad_tank_kill(self, team: Team, squad_id: str):
        with self._lock:
            S = self._ensure_squad(team, squad_id)
            S["tank_kills"] += 1
            S["current_streak"] += 1
            if S["current_streak"] > S["longest_streak"]:
                S["longest_streak"] = S["current_streak"]

    def on_squad_member_death(self, team: Team, squad_id: str):
        with self._lock:
            S = self._ensure_squad(team, squad_id)
            S["current_streak"] = 0

    def reset(self):
        with self._lock:
            self.control = {"ALLIES": set(), "AXIS": set()}
            self.holding_mid_team = None
            self.last_tick = time.monotonic()
            self.score_mid_fourth = {"ALLIES": 0.0, "AXIS": 0.0}
            self.score_tanks = {"ALLIES": 0, "AXIS": 0}
            self.kills_by_class = {"ALLIES": defaultdict(int), "AXIS": defaultdict(int)}
            self.squads = {}

    def compute_awards(self):
        """Return (award_points_by_team, details) at match end."""
        with self._lock:
            award_pts = {"ALLIES": 0, "AXIS": 0}
            details = {"veteran": [], "ace": [], "ironhide": None}
            ironhide_best = None  # (score, team, squad_id)

            for (team, squad_id), S in self.squads.items():
                if S["longest_streak"] >= self.vet_thresh:
                    award_pts[team] += self.vet_pts
                    details["veteran"].append((team, squad_id))
                if S["longest_streak"] >= self.ace_thresh:
                    award_pts[team] += self.ace_pts
                    details["ace"].append((team, squad_id))
                score_formula = 10 * S["tank_kills"] + S["longest_streak"]
                tup = (score_formula, team, squad_id)
                if not ironhide_best or tup > ironhide_best:
                    ironhide_best = tup
            if ironhide_best:
                _, team, squad_id = ironhide_best
                award_pts[team] += self.ironhide_pts
                details["ironhide"] = (team, squad_id)

            return award_pts, details

    # ---------- Reporting ----------
    def totals(self):
        with self._lock:
            phase1 = {t: round(self.score_mid_fourth[t], 2) for t in ("ALLIES","AXIS")}
            phase2 = {t: self.score_tanks[t] for t in ("ALLIES","AXIS")}
            return phase1, phase2, self.kills_by_class
