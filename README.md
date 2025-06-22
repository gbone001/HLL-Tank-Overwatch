# 🎯 HLL Tank Overwatch Discord Bot

A Discord bot for Hell Let Loose communities that tracks time control of the center point during matches. Win by controlling the center point longest!

![Discord](https://img.shields.io/badge/Discord-Bot-7289da?style=flat-square&logo=discord)
![Python](https://img.shields.io/badge/Python-3.8+-3776ab?style=flat-square&logo=python)
![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway)

## ✨ Features

- **⏱️ Time Control Tracking** - Tracks how long each team controls the center point
- **🤖 Auto-Detection** - Automatically switches when points are captured (via CRCON)
- **🎮 Live Game Integration** - Shows current map, players, and game time
- **📊 Real-time Stats** - Live Discord embeds with current standings
- **🏆 Match Results** - Automatic results posting when matches end
- **⚔️ In-Game Messages** - Notifications sent to all players with current times

## 🖼️ Preview

The bot creates interactive Discord embeds showing:
- Current map and player count
- Control time for both Allies and Axis
- Who's currently defending/attacking
- Time advantages and match leader
- Live game time remaining

## 🚀 Quick Deploy to Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new/template?template=https://github.com/StoneyRebel/HLL-Tank-Overwatch)

### Railway Deployment Steps:

1. **Click the Railway deploy button above** (or follow manual steps below)

2. **Set Environment Variables in Railway:**
   ```
   DISCORD_TOKEN=your_discord_bot_token
   CRCON_API_KEY=your_crcon_api_key
   CRCON_URL=http://your-server-ip:8010
   ```

3. **Deploy!** Railway will automatically build and start your bot.

### Manual Railway Setup:

1. **Fork this repository** to your GitHub account

2. **Create a new Railway project:**
   - Go to [Railway](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your forked repository

3. **Add Environment Variables:**
   - In Railway dashboard, go to your project
   - Click "Variables" tab
   - Add the required variables (see [Environment Variables](#-environment-variables) below)

4. **Deploy:**
   - Railway will automatically detect Python and deploy
   - Check the deployment logs for any errors

## 🛠️ Local Development Setup

### Prerequisites
- Python 3.8 or higher
- A Discord bot token
- CRCON server with API access

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/StoneyRebel/HLL-Tank-Overwatch.git
   cd HLL-Tank-Overwatch
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment file:**
   ```bash
   cp .env.template .env
   ```

4. **Edit `.env` with your settings:**
   ```bash
   nano .env  # or use your preferred editor
   ```

5. **Run the bot:**
   ```bash
   python enhanced_discord_bot.py
   ```

## ⚙️ Environment Variables

### Required Variables

| Variable | Description | Where to Get |
|----------|-------------|--------------|
| `DISCORD_TOKEN` | Your Discord bot token | [Discord Developer Portal](https://discord.com/developers/applications) |
| `CRCON_API_KEY` | Your CRCON API key | CRCON web interface → Settings |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRCON_URL` | `http://localhost:8010` | Your CRCON server URL |
| `CRCON_TIMEOUT` | `15` | API timeout in seconds |
| `CRCON_AUTO_SWITCH` | `true` | Auto-switch on point captures |
| `UPDATE_INTERVAL` | `15` | Discord update frequency (seconds) |
| `ADMIN_ROLE_NAME` | `admin` | Discord role required to control bot |
| `BOT_NAME` | `HLLTankBot` | Name shown in game messages |
| `BOT_AUTHOR` | `YourCommunityName` | Author shown in embed footer |
| `LOG_CHANNEL_ID` | `0` | Discord channel for match logs (0 = disabled) |

## 🎮 Discord Setup

### 1. Create Discord Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Give it a name like "HLL Tank Overwatch"

### 2. Create Bot

1. Go to the "Bot" section
2. Click "Add Bot"
3. Copy the token for your `.env` file

### 3. Set Permissions

1. In "OAuth2" → "URL Generator"
2. Select "bot" and "applications.commands"
3. Select permissions:
   - Send Messages
   - Use Slash Commands
   - Embed Links
   - Manage Messages
4. Use the generated URL to invite bot to your server

### 4. Create Admin Role

Create a Discord role named "admin" (or customize with `ADMIN_ROLE_NAME`) and assign it to users who should control the bot.

## 🖥️ CRCON Setup

### 1. Get API Key

1. Open your CRCON web interface
2. Go to Settings/Admin panel
3. Find and copy your API key

### 2. Configure URL

- **Local CRCON:** `http://localhost:8010`
- **Remote CRCON:** `http://your-server-ip:8010`
- **HTTPS:** `https://your-domain.com:8010`

Make sure to include `http://` or `https://`

## 📖 Usage

### Starting a Match

1. Use `/reverse_clock` in any Discord channel
2. Click "▶️ Start Match" to begin
3. The bot will connect to CRCON and start tracking

### Controlling the Clock

- **Manual Control:** Use "Allies" and "Axis" buttons
- **Auto Control:** Toggle "🤖 Auto" for automatic switching
- **View Stats:** Click "📊 Stats" for detailed information
- **Stop Match:** Click "⏹️ Stop" to end and show results

### Commands

| Command | Description |
|---------|-------------|
| `/reverse_clock` | Create a new match clock |
| `/crcon_status` | Check CRCON connection |
| `/server_info` | Get current server information |
| `/send_message` | Send message to game (admin only) |
| `/help_clock` | Show help information |

## 🏆 How It Works

### Time Control System

- **Objective:** Control the center point longer than the enemy
- **Tracking:** Bot tracks time each team holds the center point
- **Winning:** Team with most control time wins
- **Auto-Detection:** Automatically detects point captures via CRCON

### Game Integration

- **Live Updates:** Shows current map, players, game time
- **Auto-Switch:** Detects captures and switches control automatically
- **Player Notifications:** Sends control time updates to all players
- **Match End:** Automatically stops when game time expires

## 🐛 Troubleshooting

### Common Issues

**Bot won't start:**
- Check `DISCORD_TOKEN` and `CRCON_API_KEY` in environment variables
- Verify token hasn't expired

**No admin permissions:**
- Ensure you have the role specified in `ADMIN_ROLE_NAME`
- Default role name is "admin"

**CRCON not connecting:**
- Verify `CRCON_URL` is correct and accessible
- Check `CRCON_API_KEY` is valid
- Ensure CRCON server is running

**Auto-switch not working:**
- Set `CRCON_AUTO_SWITCH=true`
- Verify CRCON connection is stable
- Check game is on a Warfare map

### Logs

Check Railway logs or local `logs/bot.log` file for detailed error information.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for the Hell Let Loose community
- Uses CRCON for game server integration
- Designed for competitive tank-focused gameplay

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/StoneyRebel/HLL-Tank-Overwatch/issues)
- **Discord:** Join our community server [link]
- **Documentation:** See [SETUP.md](SETUP.md) for detailed setup instructions

---

**Made with ❤️ for the HLL Tank Community**