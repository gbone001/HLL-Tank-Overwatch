from __future__ import annotations

from typing import List, Protocol

from events import KillEvent, ScoreboardSnapshot


class EventSink(Protocol):
    async def handle_kill(self, event: KillEvent) -> None:
        ...

    async def handle_scoreboard(self, snapshot: ScoreboardSnapshot) -> None:
        ...


class Broadcaster:
    def __init__(self, sinks: List[EventSink]) -> None:
        self.sinks = sinks

    async def publish_kill(self, event: KillEvent) -> None:
        for sink in self.sinks:
            await sink.handle_kill(event)

    async def publish_scoreboard(self, snapshot: ScoreboardSnapshot) -> None:
        for sink in self.sinks:
            await sink.handle_scoreboard(snapshot)
