from __future__ import annotations
from discord import app_commands
import discord

def is_admin():
    # Simple check; customize to your needs (role ID, user ID, etc.)
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.manage_guild
    return app_commands.check(predicate)

def register_slash_commands(bot, engine):
    @bot.tree.command(name="tankscore_start", description="Start a new match (reset scores)")
    @is_admin()
    async def tankscore_start(interaction: discord.Interaction):
        engine.reset()
        await interaction.response.send_message("✅ New match started. Scores reset.", ephemeral=True)

    @bot.tree.command(name="tankscore_reset", description="Reset scores (admin)")
    @is_admin()
    async def tankscore_reset(interaction: discord.Interaction):
        engine.reset()
        await interaction.response.send_message("♻️ Scores reset.", ephemeral=True)

