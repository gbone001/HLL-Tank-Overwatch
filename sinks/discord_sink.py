from __future__ import annotations

from typing import Optional

import discord

from broadcaster import EventSink
from events import KillEvent, PlayerScore, ScoreboardSnapshot, TeamScore


class DiscordSink(EventSink):
    def __init__(self, channel: discord.abc.Messageable):
        self.channel = channel

    async def handle_kill(self, event: KillEvent) -> None:
        # TODO: Replace with richer embed/formatting if desired.
        text_parts = []

        if event.suicide:
            text_parts.append(f"{event.victim or 'Unknown'} [SUICIDE]")
        elif event.teamkill:
            text_parts.append(f"{event.killer or 'Unknown'} [TK] {event.victim or 'Unknown'}")
        else:
            text_parts.append(f"{event.killer or 'Unknown'} \u2192 {event.victim or 'Unknown'}")

        if event.weapon:
            weapon_text = f"{event.weapon}"
            if event.distance is not None:
                weapon_text += f", {event.distance}m"
            text_parts.append(f"({weapon_text})")

        message = " ".join(text_parts)
        await self.channel.send(message)

    async def handle_scoreboard(self, snapshot: ScoreboardSnapshot) -> None:
        # TODO: Replace with your existing rich scoreboard embed if you have one.
        lines: list[str] = [f"Scoreboard \u2013 Match {snapshot.match_id}"]

        for team in snapshot.teams:
            lines.append(f"\n**{team.name}** (Score: {team.score})")
            top_players = sorted(team.players, key=lambda player: player.score, reverse=True)[:10]
            for player in top_players:
                lines.append(f"- {player.name}: {player.kills}/{player.deaths} ({player.score})")

        message = "\n".join(lines)
        await self.channel.send(message)
