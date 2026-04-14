from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch

from enhanced_discord_bot import ClockState, TimerControls, clocks


class ClockMessageLifecycleTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.channel_id = 4242
        clocks[self.channel_id] = ClockState(self.channel_id)

    async def asyncTearDown(self):
        clocks.pop(self.channel_id, None)

    async def test_reset_timer_stores_channel_message_not_interaction_response(self):
        posted_message = object()
        interaction = SimpleNamespace(
            response=SimpleNamespace(send_message=AsyncMock()),
            channel=SimpleNamespace(send=AsyncMock(return_value=posted_message)),
            followup=SimpleNamespace(send=AsyncMock()),
            original_response=AsyncMock(),
            user=SimpleNamespace(roles=[]),
        )

        with patch("enhanced_discord_bot.user_is_admin", return_value=True), \
             patch("enhanced_discord_bot.release_kill_feed_channel"), \
             patch("enhanced_discord_bot.build_embed", return_value=Mock(name="embed")), \
             patch("enhanced_discord_bot.StartControls", return_value=Mock(name="view")):
            controls = TimerControls(self.channel_id)
            reset_button = next(child for child in controls.children if child.label == "↺ Reset")
            await reset_button.callback(interaction)

        interaction.response.send_message.assert_awaited_once_with("✅ Clock reset.", ephemeral=True)
        interaction.channel.send.assert_awaited_once()
        interaction.followup.send.assert_not_awaited()
        interaction.original_response.assert_not_awaited()
        self.assertIs(clocks[self.channel_id].message, posted_message)
