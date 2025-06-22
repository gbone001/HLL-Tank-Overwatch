# HLL Tank Overwatch Bot Setup Guide

## Quick Start

1. **Copy the environment template:**
   ```bash
   cp .env.template .env
   ```

2. **Edit the .env file with your settings:**
   - Get your Discord bot token from [Discord Developer Portal](https://discord.com/developers/applications)
   - Get your CRCON API key from your CRCON web interface
   - Update other settings as needed

3. **Install Python dependencies:**
   ```bash
   pip install discord.py aiohttp python-dotenv
   ```

4. **Run the bot:**
   ```bash
   python enhanced_discord_bot.py
   ```

## Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DISCORD_TOKEN` | Your Discord bot token | `MTIzNDU2Nzg5...` |
| `CRCON_API_KEY` | Your CRCON API key | `d1c56ecf-eac1-...` |

## Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRCON_URL` | `http://localhost:8010` | Your CRCON server URL |
| `CRCON_TIMEOUT` | `15` | API timeout in seconds |
| `CRCON_AUTO_SWITCH` | `true` | Auto-switch on point captures |
| `UPDATE_INTERVAL` | `15` | Discord update frequency (seconds) |
| `ADMIN_ROLE_NAME` | `admin` | Discord role required to control bot |
| `BOT_NAME` | `HLLTankBot` | Name shown in game messages |
| `BOT_AUTHOR` | `StoneyRebel` | Author shown in embed footer |
| `LOG_CHANNEL_ID` | `0` | Discord channel for match logs (0 = disabled) |

## Discord Setup

1. **Create a Discord Application:**
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Click "New Application"
   - Give it a name like "HLL Tank Overwatch"

2. **Create a Bot:**
   - Go to the "Bot" section
   - Click "Add Bot"
   - Copy the token and put it in your `.env` file

3. **Set Bot Permissions:**
   - In "OAuth2" > "URL Generator"
   - Select "bot" and "applications.commands"
   - Select permissions: "Send Messages", "Use Slash Commands", "Embed Links"
   - Use the generated URL to invite the bot to your server

4. **Create Admin Role:**
   - In your Discord server, create a role named "admin" (or whatever you set in `ADMIN_ROLE_NAME`)
   - Give this role to users who should control the bot

## CRCON Setup

1. **Get your API Key:**
   - Open your CRCON web interface
   - Go to Settings/Admin panel
   - Find your API key
   - Put it in your `.env` file

2. **Set CRCON URL:**
   - If CRCON is on the same machine: `http://localhost:8010`
   - If CRCON is remote: `http://your-server-ip:8010`
   - Include `http://` or `https://`

## Usage

1. **Start a match:**
   - Use `/reverse_clock` in Discord
   - Click "▶️ Start Match"

2. **Control the clock:**
   - Use "Allies" and "Axis" buttons to manually switch control
   - Toggle "🤖 Auto" for automatic switching on point captures
   - Click "⏹️ Stop" to end the match

3. **View stats:**
   - Click "📊 Stats" for live match statistics
   - Use `/server_info` for current server information

## Troubleshooting

- **Bot won't start:** Check your `.env` file has valid `DISCORD_TOKEN` and `CRCON_API_KEY`
- **No admin permissions:** Make sure you have the role specified in `ADMIN_ROLE_NAME`
- **CRCON not connecting:** Verify `CRCON_URL` and `CRCON_API_KEY` are correct
- **Auto-switch not working:** Enable `CRCON_AUTO_SWITCH=true` and ensure CRCON connection is stable

## Support

Check the logs in the `logs/bot.log` file for detailed error information.