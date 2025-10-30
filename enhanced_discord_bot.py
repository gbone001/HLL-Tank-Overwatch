#!/usr/bin/env python3
"""
HLL Discord Bot with DMT Scoring System
Combines Combat Scores and Center Point Control Time
"""

import asyncio
import os
import discord
import datetime
import json
import aiohttp
import logging
from pathlib import Path
from dotenv import load_dotenv
from discord.ext import commands, tasks
from discord import app_commands
from datetime import timezone, timedelta
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create directories if running locally
if not os.getenv('RAILWAY_ENVIRONMENT'):
    for directory in ['logs', 'match_reports', 'match_data', 'backups']:
        os.makedirs(directory, exist_ok=True)

load_dotenv()

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

clocks = {}
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', '0')) if os.getenv('LOG_CHANNEL_ID', '0').isdigit() else 0

class PlayerScore:
    """Track individual player scores"""
    def __init__(self, name: str, player_id: str):
        self.name = name
        self.player_id = player_id
        self.combat_score = 0
        self.kills = 0
        self.deaths = 0
        self.role = ""
        self.squad = ""
        self.is_commander = False
        self.precision_strike_score = 0

class TeamScores:
    """Track team scores for DMT system"""
    def __init__(self):
        self.crew_scores = []  # List of highest scores from each tank crew
        self.commander_score = 0
        self.commander_pstrike_score = 0
        self.center_point_seconds = 0
        self.total_combat_score = 0
        self.total_cap_score = 0
        self.total_dmt_score = 0
        self.players = {}  # player_id -> PlayerScore
        
    def calculate_dmt_score(self):
        """Calculate DMT total score"""
        # Get top 4 crew scores (highest CS from each crew)
        top_4_crews = sorted(self.crew_scores, reverse=True)[:4]
        while len(top_4_crews) < 4:
            top_4_crews.append(0)  # Pad with 0 if less than 4 crews
        
        # TOTAL COMBAT SCORE = (3 × (sum of top 4 crew scores)) + Commander P-Strike CS
        self.total_combat_score = (3 * sum(top_4_crews)) + self.commander_pstrike_score
        
        # TOTAL CENTER POINT CAP SCORE = seconds × 0.5
        self.total_cap_score = self.center_point_seconds * 0.5
        
        # TOTAL SCORE
        self.total_dmt_score = self.total_combat_score + self.total_cap_score
        
        return self.total_dmt_score

class APIKeyCRCONClient:
    """CRCON client using API key authentication"""
    
    def __init__(self):
        self.base_url = os.getenv('CRCON_URL', 'http://localhost:8010')
        self.api_key = os.getenv('CRCON_API_KEY')
        self.session = None
        self.timeout = aiohttp.ClientTimeout(total=int(os.getenv('CRCON_TIMEOUT', '15')))
    
    async def __aenter__(self):
        """Async context manager entry"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        self.session = aiohttp.ClientSession(
            timeout=self.timeout,
            headers=headers
        )
        
        # Test connection
        try:
            async with self.session.get(f"{self.base_url}/api/get_status") as response:
                if response.status != 200:
                    await self.session.close()
                    raise Exception(f"CRCON connection failed: {response.status}")
        except Exception as e:
            if self.session:
                await self.session.close()
            raise e
        
        logger.info("Successfully connected to CRCON with API key")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def get_live_game_state(self):
        """Get comprehensive live game state"""
        try:
            # Get data concurrently
            tasks = [
                self._get_endpoint('/api/get_gamestate'),
                self._get_endpoint('/api/get_team_view'),
                self._get_endpoint('/api/get_map'),
                self._get_endpoint('/api/get_players'),
                self._get_endpoint('/api/get_detailed_players'),
                self._get_endpoint('/api/get_live_game_stats')
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results safely
            game_state = results[0] if not isinstance(results[0], Exception) else {}
            team_view = results[1] if not isinstance(results[1], Exception) else {}
            map_info = results[2] if not isinstance(results[2], Exception) else {}
            players = results[3] if not isinstance(results[3], Exception) else {}
            detailed_players = results[4] if not isinstance(results[4], Exception) else {}
            live_stats = results[5] if not isinstance(results[5], Exception) else {}
            
            return {
                'game_state': game_state,
                'team_view': team_view,
                'map_info': map_info,
                'players': players,
                'detailed_players': detailed_players,
                'live_stats': live_stats,
                'timestamp': datetime.datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"Error getting game state: {e}")
            return None
    
    async def _get_endpoint(self, endpoint):
        """Helper to get data from an endpoint"""
        try:
            async with self.session.get(f"{self.base_url}{endpoint}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"Endpoint {endpoint} returned {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting {endpoint}: {e}")
            return {}
    
    async def send_message(self, message: str):
        """Send message to all players individually"""
        try:
            logger.info(f"Getting player list to send message: {message}")
            
            async with self.session.get(f"{self.base_url}/api/get_player_ids") as response:
                if response.status != 200:
                    logger.warning(f"Failed to get player list: {response.status}")
                    return False
                
                player_data = await response.json()
                logger.info(f"Player data response: {player_data}")
                
                if isinstance(player_data, dict) and 'result' in player_data:
                    players = player_data['result']
                else:
                    players = player_data
                
                if not players:
                    logger.info("No players online to send message to")
                    return True
                
                success_count = 0
                total_players = len(players)
                
                for player in players:
                    try:
                        if isinstance(player, list) and len(player) >= 2:
                            player_name = player[0]
                            player_id = player[1]
                        elif isinstance(player, dict):
                            player_name = player.get('name', '')
                            player_id = player.get('steam_id_64', '')
                        else:
                            continue
                        
                        payload = {
                            "player_name": player_name,
                            "player_id": player_id,
                            "message": message,
                            "by": os.getenv('BOT_NAME', 'HLLTankBot')
                        }
                        
                        async with self.session.post(f"{self.base_url}/api/message_player", json=payload) as msg_response:
                            if msg_response.status == 200:
                                success_count += 1
                                logger.debug(f"Message sent to {player_name}")
                            else:
                                logger.debug(f"Failed to message {player_name}: {msg_response.status}")
                                
                    except Exception as e:
                        logger.debug(f"Error messaging individual player: {e}")
                        continue
                
                logger.info(f"Message sent to {success_count}/{total_players} players")
                return success_count > 0
                
        except Exception as e:
            logger.error(f"Error sending message to all players: {e}")
            return False

class ClockState:
    """Enhanced clock state with DMT scoring"""
    
    def __init__(self):
        # Time tracking
        self.time_a = 0  # Allies center point seconds
        self.time_b = 0  # Axis center point seconds
        self.active = None
        self.last_switch = None
        self.match_start_time = None
        self.countdown_end = None
        self.message = None
        self.started = False
        self.clock_started = False
        
        # DMT Scoring
        self.allies_scores = TeamScores()
        self.axis_scores = TeamScores()
        
        # CRCON integration
        self.crcon_client = None
        self.game_data = None
        self.auto_switch = False
        self.last_scores = {'allied': 0, 'axis': 0}
        self.switches = []
        self.last_update = None
        
        # Score tracking
        self.score_tracking_enabled = os.getenv('DMT_SCORING', 'true').lower() == 'true'

    def get_current_elapsed(self):
        """Get elapsed time since last switch"""
        if self.last_switch and self.clock_started and self.active:
            return (datetime.datetime.now(timezone.utc) - self.last_switch).total_seconds()
        return 0

    def total_time(self, team):
        """Get total time for a team INCLUDING current elapsed time"""
        if team == "A":
            base_time = self.time_a
            if self.active == "A" and self.clock_started:
                base_time += self.get_current_elapsed()
            return base_time
        elif team == "B":
            base_time = self.time_b
            if self.active == "B" and self.clock_started:
                base_time += self.get_current_elapsed()
            return base_time
        return 0

    def get_live_status(self, team):
        """Get live status with current timing info"""
        total = self.total_time(team)
        
        if self.active == team and self.clock_started:
            current_elapsed = self.get_current_elapsed()
            return {
                'total_time': total,
                'status': '🛡️ Defending',
                'current_session': current_elapsed,
                'is_active': True
            }
        else:
            return {
                'total_time': total,
                'status': '⚔️ Attacking',
                'current_session': 0,
                'is_active': False
            }

    async def connect_crcon(self):
        """Connect to CRCON with API key"""
        try:
            if self.crcon_client:
                try:
                    await self.crcon_client.__aexit__(None, None, None)
                except:
                    pass
            
            self.crcon_client = APIKeyCRCONClient()
            await self.crcon_client.__aenter__()
            logger.info("Connected to CRCON successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CRCON: {e}")
            self.crcon_client = None
            return False
    
    async def update_from_game(self):
        """Update from CRCON game data including player scores"""
        if not self.crcon_client:
            return
        
        try:
            live_data = await self.crcon_client.get_live_game_state()
            if not live_data:
                return
            
            self.game_data = live_data
            self.last_update = datetime.datetime.now(timezone.utc)
            
            # Update player scores for DMT scoring
            if self.score_tracking_enabled:
                await self._update_player_scores()
            
            # Check for auto-switch
            if self.auto_switch and self.started and hasattr(self, '_first_update_done'):
                await self._check_score_changes()
            else:
                game_state = self.game_data.get('game_state', {})
                if isinstance(game_state, dict) and 'result' in game_state:
                    result = game_state['result']
                    if isinstance(result, dict):
                        self.last_scores = {
                            'allied': result.get('allied_score', 0),
                            'axis': result.get('axis_score', 0)
                        }
                self._first_update_done = True
                
        except Exception as e:
            logger.error(f"Error updating from game: {e}")
    
    async def _update_player_scores(self):
        """Update player combat scores for DMT calculation"""
        if not self.game_data:
            return
        
        try:
            detailed_players = self.game_data.get('detailed_players', {})
            team_view = self.game_data.get('team_view', {})
            
            if isinstance(detailed_players, dict) and 'result' in detailed_players:
                players_data = detailed_players['result']
                
                # Process teams
                if 'teams' in players_data:
                    for team_name, team_data in players_data['teams'].items():
                        team_scores = self.allies_scores if team_name == 'allies' else self.axis_scores
                        
                        # Track squads for crew identification
                        squad_scores = {}  # squad_name -> highest_score
                        
                        if 'squads' in team_data:
                            for squad_name, squad_data in team_data['squads'].items():
                                highest_squad_score = 0
                                
                                # Check if this is a tank crew squad (contains "tank" or specific squad names)
                                is_tank_crew = any(keyword in squad_name.lower() for keyword in ['tank', 'armor', 'crew'])
                                
                                if 'players' in squad_data:
                                    for player in squad_data['players']:
                                        player_name = player.get('name', '')
                                        player_id = player.get('steam_id_64', '')
                                        combat_score = player.get('combat', 0)
                                        kills = player.get('kills', 0)
                                        deaths = player.get('deaths', 0)
                                        role = player.get('role', '')
                                        
                                        # Create or update player score
                                        if player_id not in team_scores.players:
                                            team_scores.players[player_id] = PlayerScore(player_name, player_id)
                                        
                                        ps = team_scores.players[player_id]
                                        ps.combat_score = combat_score
                                        ps.kills = kills
                                        ps.deaths = deaths
                                        ps.role = role
                                        ps.squad = squad_name
                                        
                                        # Check if commander
                                        if role.lower() == 'commander' or squad_name.lower() == 'command':
                                            ps.is_commander = True
                                            team_scores.commander_score = combat_score
                                            # Extract P-Strike score if available
                                            # This might need adjustment based on CRCON data format
                                            team_scores.commander_pstrike_score = player.get('offensive', 0)
                                        
                                        # Track highest score in tank crew
                                        if is_tank_crew and combat_score > highest_squad_score:
                                            highest_squad_score = combat_score
                                
                                # Add highest crew score
                                if is_tank_crew and highest_squad_score > 0:
                                    squad_scores[squad_name] = highest_squad_score
                        
                        # Update crew scores list
                        team_scores.crew_scores = list(squad_scores.values())
                        
            logger.debug(f"Updated player scores - Allies crews: {len(self.allies_scores.crew_scores)}, Axis crews: {len(self.axis_scores.crew_scores)}")
            
        except Exception as e:
            logger.error(f"Error updating player scores: {e}")
    
    async def _check_score_changes(self):
        """Check for captures to trigger auto-switch"""
        if not self.game_data or 'game_state' not in self.game_data:
            return
        
        game_state = self.game_data['game_state']
        
        current_allied = 0
        current_axis = 0
        
        if isinstance(game_state, dict) and 'result' in game_state:
            result = game_state['result']
            if isinstance(result, dict):
                current_allied = result.get('allied_score', 0)
                current_axis = result.get('axis_score', 0)
        
        logger.info(f"Score check - Allied: {self.last_scores['allied']} -> {current_allied}, Axis: {self.last_scores['axis']} -> {current_axis}")
        
        if current_allied > self.last_scores['allied']:
            logger.info(f"Allied score increased! Switching to Allies")
            await self._auto_switch_to('A', "Allies captured the center point")
        elif current_axis > self.last_scores['axis']:
            logger.info(f"Axis score increased! Switching to Axis") 
            await self._auto_switch_to('B', "Axis captured the center point")
        else:
            logger.debug(f"No score changes detected")
        
        self.last_scores = {'allied': current_allied, 'axis': current_axis}
    
    async def _auto_switch_to(self, team: str, reason: str = "Auto-switch"):
        """Auto-switch teams with proper time tracking"""
        if self.active == team:
            return
        
        now = datetime.datetime.now(timezone.utc)
        
        if self.active == "A" and self.last_switch:
            elapsed = (now - self.last_switch).total_seconds()
            self.time_a += elapsed
        elif self.active == "B" and self.last_switch:
            elapsed = (now - self.last_switch).total_seconds()
            self.time_b += elapsed
        
        switch_data = {
            'from_team': self.active,
            'to_team': team,
            'timestamp': now,
            'method': 'auto',
            'reason': reason
        }
        self.switches.append(switch_data)
        
        self.active = team
        self.last_switch = now
        
        if not self.clock_started:
            self.clock_started = True
        
        if self.crcon_client:
            team_name = "Allies" if team == "A" else "Axis"
            allies_time = self.format_time(self.total_time('A'))
            axis_time = self.format_time(self.total_time('B'))
            await self.crcon_client.send_message(f"🔄 {team_name} captured the center point! | Allies: {allies_time} | Axis: {axis_time}")
        
        if self.message:
            try:
                await self.message.edit(embed=build_embed(self))
                logger.info(f"Discord embed updated after auto-switch to {team}")
            except Exception as e:
                logger.error(f"Failed to update Discord embed: {e}")
            
        logger.info(f"Auto-switched to team {team}: {reason}")
    
    def calculate_final_scores(self):
        """Calculate final DMT scores when match ends"""
        # Update center point seconds
        self.allies_scores.center_point_seconds = int(self.time_a)
        self.axis_scores.center_point_seconds = int(self.time_b)
        
        # Calculate DMT scores
        self.allies_scores.calculate_dmt_score()
        self.axis_scores.calculate_dmt_score()
        
        return {
            'allies': {
                'center_seconds': self.allies_scores.center_point_seconds,
                'crew_scores': self.allies_scores.crew_scores[:4],  # Top 4
                'commander_pstrike': self.allies_scores.commander_pstrike_score,
                'total_combat': self.allies_scores.total_combat_score,
                'total_cap': self.allies_scores.total_cap_score,
                'total_dmt': self.allies_scores.total_dmt_score
            },
            'axis': {
                'center_seconds': self.axis_scores.center_point_seconds,
                'crew_scores': self.axis_scores.crew_scores[:4],  # Top 4
                'commander_pstrike': self.axis_scores.commander_pstrike_score,
                'total_combat': self.axis_scores.total_combat_score,
                'total_cap': self.axis_scores.total_cap_score,
                'total_dmt': self.axis_scores.total_dmt_score
            }
        }
    
    def get_game_info(self):
        """Get formatted game information"""
        if not self.game_data:
            return {
                'map': 'No Connection',
                'players': 0,
                'game_time': 0,
                'connection_status': 'Disconnected'
            }
        
        game_state = self.game_data.get('game_state', {})
        map_info = self.game_data.get('map_info', {})
        
        current_map = 'Unknown'
        
        if isinstance(map_info, dict) and 'result' in map_info:
            result = map_info['result']
            if isinstance(result, dict):
                if 'pretty_name' in result:
                    current_map = result['pretty_name']
                elif 'map' in result and isinstance(result['map'], dict):
                    current_map = result['map'].get('pretty_name', result['map'].get('name', 'Unknown'))
        
        player_count = 0
        if isinstance(game_state, dict) and 'result' in game_state:
            result = game_state['result']
            if isinstance(result, dict):
                allied_players = result.get('num_allied_players', 0)
                axis_players = result.get('num_axis_players', 0)
                player_count = allied_players + axis_players
        
        game_time_remaining = 0
        if isinstance(game_state, dict) and 'result' in game_state:
            result = game_state['result']
            if isinstance(result, dict):
                raw_time = result.get('time_remaining', 0)
                if raw_time > 0:
                    game_time_remaining = raw_time
        
        allied_score = 0
        axis_score = 0
        
        if isinstance(game_state, dict) and 'result' in game_state:
            result = game_state['result']
            if isinstance(result, dict):
                allied_score = result.get('allied_score', 0)
                axis_score = result.get('axis_score', 0)
        
        self.last_scores = {'allied': allied_score, 'axis': axis_score}
        
        return {
            'map': current_map,
            'players': player_count,
            'game_time': game_time_remaining,
            'connection_status': 'Connected',
            'last_update': self.last_update.strftime('%H:%M:%S') if self.last_update else 'Never'
        }

    def format_time(self, secs):
        return str(datetime.timedelta(seconds=max(0, int(secs))))

def user_is_admin(interaction: discord.Interaction):
    admin_role = os.getenv('ADMIN_ROLE_NAME', 'admin').lower()
    return any(role.name.lower() == admin_role for role in interaction.user.roles)

def build_embed(clock: ClockState):
    """Build Discord embed with DMT scoring info"""
    embed = discord.Embed(
        title="🎯 🔥 HLL Tank Overwatch - DMT Scoring 🔥 🎯",
        description="**Control the center point & maximize combat scores to win!**",
        color=0x800020
    )
    
    game_info = clock.get_game_info()
    
    embed.description += f"\n🗺️ **Map:** {game_info['map']}\n👥 **Players:** {game_info['players']}/100"
    
    if game_info['game_time'] > 0:
        embed.description += f"\n⏰ **Server Game Time:** `{clock.format_time(game_info['game_time'])}`"
    
    # Center point control times
    allies_status = clock.get_live_status('A')
    axis_status = clock.get_live_status('B')
    
    allies_value = f"**Control Time:** `{clock.format_time(allies_status['total_time'])}`\n**Status:** {allies_status['status']}"
    axis_value = f"**Control Time:** `{clock.format_time(axis_status['total_time'])}`\n**Status:** {axis_status['status']}"
    
    if allies_status['is_active'] and allies_status['current_session'] > 0:
        allies_value += f"\n**Current Hold:** `{clock.format_time(allies_status['current_session'])}`"
    elif axis_status['is_active'] and axis_status['current_session'] > 0:
        axis_value += f"\n**Current Hold:** `{clock.format_time(axis_status['current_session'])}`"
    
    # Add preliminary DMT scores if scoring is enabled
    if clock.score_tracking_enabled and clock.started:
        # Calculate current scores
        clock.allies_scores.center_point_seconds = int(clock.total_time('A'))
        clock.axis_scores.center_point_seconds = int(clock.total_time('B'))
        
        allies_cap_score = clock.allies_scores.center_point_seconds * 0.5
        axis_cap_score = clock.axis_scores.center_point_seconds * 0.5
        
        allies_value += f"\n**Cap Points:** `{allies_cap_score:.1f}`"
        axis_value += f"\n**Cap Points:** `{axis_cap_score:.1f}`"
        
        # Add crew count if available
        if len(clock.allies_scores.crew_scores) > 0:
            allies_value += f"\n**Tank Crews:** `{len(clock.allies_scores.crew_scores)}`"
        if len(clock.axis_scores.crew_scores) > 0:
            axis_value += f"\n**Tank Crews:** `{len(clock.axis_scores.crew_scores)}`"
    
    embed.add_field(name="🇺🇸 Allies", value=allies_value, inline=True)
    embed.add_field(name="🇩🇪 Axis", value=axis_value, inline=True)
    
    # Current leader by time
    time_diff = abs(allies_status['total_time'] - axis_status['total_time'])
    if allies_status['total_time'] > axis_status['total_time']:
        leader_text = f"🏆 **Time Leader:** Allies (+{clock.format_time(time_diff)})"
    elif axis_status['total_time'] > allies_status['total_time']:
        leader_text = f"🏆 **Time Leader:** Axis (+{clock.format_time(time_diff)})"
    else:
        leader_text = "⚖️ **Status:** Tied"
    
    embed.add_field(name="🎯 Point Control", value=leader_text, inline=False)
    
    # Footer
    connection_status = f"🟢 CRCON Connected" if clock.crcon_client else "🔴 CRCON Disconnected"
    auto_status = " | 🤖 Auto ON" if clock.auto_switch else " | 🤖 Auto OFF"
    dmt_status = " | 📊 DMT ON" if clock.score_tracking_enabled else ""
    
    footer_text = f"Match Clock by {os.getenv('BOT_AUTHOR', 'StoneyRebel')} | {connection_status}{auto_status}{dmt_status}"
    if game_info.get('last_update'):
        footer_text += f" | Updated: {game_info['last_update']}"
    
    embed.set_footer(text=footer_text)
    return embed

def build_final_dmt_embed(clock: ClockState, scores: dict):
    """Build final match embed with DMT scores"""
    embed = discord.Embed(
        title="🏁 Match Complete - DMT Scoring Results!",
        color=0x800020
    )
    
    game_info = clock.get_game_info()
    if game_info['connection_status'] == 'Connected':
        embed.add_field(name="🗺️ Map", value=game_info['map'], inline=True)
        embed.add_field(name="👥 Players", value=f"{game_info['players']}/100", inline=True)
        embed.add_field(name="🔄 Switches", value=str(len(clock.switches)), inline=True)
    
    # DMT Scoring Breakdown
    embed.add_field(name="━━━━━ DMT SCORING ━━━━━", value="", inline=False)
    
    # Allies scores
    allies_scores = scores['allies']
    allies_breakdown = f"**Center Point Time:** `{allies_scores['center_seconds']}s`\n"
    allies_breakdown += f"**Cap Score:** `{allies_scores['total_cap']:.1f}` (× 0.5)\n"
    allies_breakdown += f"**Top 4 Crews:** `{sum(allies_scores['crew_scores'])}`\n"
    allies_breakdown += f"**Combat Score:** `{allies_scores['total_combat']}`\n"
    if allies_scores['commander_pstrike'] > 0:
        allies_breakdown += f"**Cmdr P-Strike:** `{allies_scores['commander_pstrike']}`\n"
    allies_breakdown += f"**TOTAL DMT:** `{allies_scores['total_dmt']:.1f}`"
    
    embed.add_field(name="🇺🇸 Allies", value=allies_breakdown, inline=True)
    
    # Axis scores
    axis_scores = scores['axis']
    axis_breakdown = f"**Center Point Time:** `{axis_scores['center_seconds']}s`\n"
    axis_breakdown += f"**Cap Score:** `{axis_scores['total_cap']:.1f}` (× 0.5)\n"
    axis_breakdown += f"**Top 4 Crews:** `{sum(axis_scores['crew_scores'])}`\n"
    axis_breakdown += f"**Combat Score:** `{axis_scores['total_combat']}`\n"
    if axis_scores['commander_pstrike'] > 0:
        axis_breakdown += f"**Cmdr P-Strike:** `{axis_scores['commander_pstrike']}`\n"
    axis_breakdown += f"**TOTAL DMT:** `{axis_scores['total_dmt']:.1f}`"
    
    embed.add_field(name="🇩🇪 Axis", value=axis_breakdown, inline=True)
    
    # Determine winner
    if allies_scores['total_dmt'] > axis_scores['total_dmt']:
        winner_text = f"🏆 **ALLIES VICTORY**\n"
        winner_text += f"**Winning Margin:** `{allies_scores['total_dmt'] - axis_scores['total_dmt']:.1f}` points"
        embed.color = 0x0066CC  # Blue for Allies
    elif axis_scores['total_dmt'] > allies_scores['total_dmt']:
        winner_text = f"🏆 **AXIS VICTORY**\n"
        winner_text += f"**Winning Margin:** `{axis_scores['total_dmt'] - allies_scores['total_dmt']:.1f}` points"
        embed.color = 0xCC0000  # Red for Axis
    else:
        winner_text = "🤝 **DRAW**\nPerfectly balanced!"
        embed.color = 0x808080  # Gray for draw
    
    embed.add_field(name="🎯 DMT MATCH WINNER", value=winner_text, inline=False)
    
    # Scoring formula reminder
    embed.add_field(
        name="📐 DMT Formula",
        value="Combat: (3×Top4Crews) + CmdrPStrike | Cap: Seconds×0.5",
        inline=False
    )
    
    embed.timestamp = datetime.datetime.now(timezone.utc)
    return embed

class StartControls(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="▶️ Start Match", style=discord.ButtonStyle.success)
    async def start_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_is_admin(interaction):
            return await interaction.response.send_message("❌ Admin role required.", ephemeral=True)

        await interaction.response.defer()

        clock = clocks[self.channel_id]
        clock.match_start_time = datetime.datetime.now(timezone.utc)
        clock.started = True

        if not match_updater.is_running():
            match_updater.start(self.channel_id)

        view = TimerControls(self.channel_id)
        
        await clock.message.edit(embed=build_embed(clock), view=view)
        await interaction.followup.send("✅ Match started! Connecting to CRCON...", ephemeral=True)

        crcon_connected = await clock.connect_crcon()
        
        if crcon_connected:
            clock.auto_switch = os.getenv('CRCON_AUTO_SWITCH', 'false').lower() == 'true'
            await clock.crcon_client.send_message("🎯 HLL Tank Overwatch Match Started! DMT Scoring Active!")
            await interaction.edit_original_response(content="✅ Match started with CRCON!")
        else:
            await interaction.edit_original_response(content="✅ Match started (CRCON connection failed)")

    @discord.ui.button(label="🔗 Test CRCON", style=discord.ButtonStyle.secondary)
    async def test_crcon(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            test_client = APIKeyCRCONClient()
            async with test_client as client:
                live_data = await client.get_live_game_state()
                
                if live_data:
                    game_state = live_data.get('game_state', {})
                    embed = discord.Embed(title="🟢 CRCON Test - SUCCESS", color=0x00ff00)
                    embed.add_field(name="Status", value="✅ Connected", inline=True)
                    embed.add_field(name="DMT Scoring", value="✅ Ready", inline=True)
                else:
                    embed = discord.Embed(title="🟡 CRCON Test - PARTIAL", color=0xffaa00)
                    embed.add_field(name="Status", value="Connected but no data", inline=False)
                    
        except Exception as e:
            embed = discord.Embed(title="🔴 CRCON Test - FAILED", color=0xff0000)
            embed.add_field(name="Error", value=str(e)[:1000], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

class TimerControls(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id

    @discord.ui.button(label="Allies", style=discord.ButtonStyle.success, emoji="🇺🇸")
    async def switch_to_a(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_team(interaction, "A")

    @discord.ui.button(label="Axis", style=discord.ButtonStyle.secondary, emoji="🇩🇪")
    async def switch_to_b(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._switch_team(interaction, "B")

    @discord.ui.button(label="🤖 Auto", style=discord.ButtonStyle.secondary)
    async def toggle_auto_switch(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_is_admin(interaction):
            return await interaction.response.send_message("❌ Admin role required.", ephemeral=True)
        
        clock = clocks[self.channel_id]
        clock.auto_switch = not clock.auto_switch
        
        status = "enabled" if clock.auto_switch else "disabled"
        
        await interaction.response.defer()
        await clock.message.edit(embed=build_embed(clock), view=self)
        
        if clock.crcon_client:
            await clock.crcon_client.send_message(f"🤖 Auto-switch {status}")

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary)
    async def show_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        clock = clocks[self.channel_id]
        await interaction.response.defer(ephemeral=True)
        
        if not clock.crcon_client:
            return await interaction.followup.send("❌ CRCON not connected.", ephemeral=True)
        
        try:
            await clock.update_from_game()
            game_info = clock.get_game_info()
            
            embed = discord.Embed(title="📊 Live DMT Match Stats", color=0x00ff00)
            embed.add_field(name="🗺️ Map", value=game_info['map'], inline=True)
            embed.add_field(name="👥 Players", value=f"{game_info['players']}/100", inline=True)
            embed.add_field(name="🔄 Switches", value=str(len(clock.switches)), inline=True)
            
            # Current DMT score preview
            if clock.score_tracking_enabled:
                clock.allies_scores.center_point_seconds = int(clock.total_time('A'))
                clock.axis_scores.center_point_seconds = int(clock.total_time('B'))
                
                # Calculate preliminary scores
                allies_prelim = (clock.allies_scores.center_point_seconds * 0.5) + \
                               (3 * sum(clock.allies_scores.crew_scores[:4]))
                axis_prelim = (clock.axis_scores.center_point_seconds * 0.5) + \
                             (3 * sum(clock.axis_scores.crew_scores[:4]))
                
                embed.add_field(
                    name="🇺🇸 Allies DMT (Prelim)",
                    value=f"`{allies_prelim:.1f}` points",
                    inline=True
                )
                embed.add_field(
                    name="🇩🇪 Axis DMT (Prelim)",
                    value=f"`{axis_prelim:.1f}` points",
                    inline=True
                )
            
            embed.add_field(name="🤖 Auto-Switch", value="On" if clock.auto_switch else "Off", inline=True)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="↺ Reset", style=discord.ButtonStyle.primary)
    async def reset_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_is_admin(interaction):
            return await interaction.response.send_message("❌ Admin role required.", ephemeral=True)

        old_clock = clocks[self.channel_id]
        if old_clock.crcon_client:
            await old_clock.crcon_client.__aexit__(None, None, None)

        clocks[self.channel_id] = ClockState()
        clock = clocks[self.channel_id]
        view = StartControls(self.channel_id)

        await interaction.response.defer()
        embed = build_embed(clock)
        await interaction.followup.send(embed=embed, view=view)
        clock.message = await interaction.original_response()

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop_timer(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not user_is_admin(interaction):
            return await interaction.response.send_message("❌ Admin role required.", ephemeral=True)

        clock = clocks[self.channel_id]
        
        # Finalize times
        if clock.active and clock.last_switch:
            elapsed = (datetime.datetime.now(timezone.utc) - clock.last_switch).total_seconds()
            if clock.active == "A":
                clock.time_a += elapsed
            elif clock.active == "B":
                clock.time_b += elapsed

        clock.active = None
        clock.started = False

        # Calculate final DMT scores
        final_scores = clock.calculate_final_scores()
        
        # Send final message to game
        if clock.crcon_client:
            allies_dmt = final_scores['allies']['total_dmt']
            axis_dmt = final_scores['axis']['total_dmt']
            
            if allies_dmt > axis_dmt:
                winner_msg = f"Allies WIN by DMT Score! {allies_dmt:.1f} - {axis_dmt:.1f}"
            elif axis_dmt > allies_dmt:
                winner_msg = f"Axis WIN by DMT Score! {axis_dmt:.1f} - {allies_dmt:.1f}"
            else:
                winner_msg = f"DRAW by DMT Score! {allies_dmt:.1f} - {axis_dmt:.1f}"
            
            await clock.crcon_client.send_message(f"🏁 Match Complete! {winner_msg}")

        # Create final embed with DMT scores
        embed = build_final_dmt_embed(clock, final_scores)
        
        await interaction.response.defer()
        await clock.message.edit(embed=embed, view=None)

        # Log results
        await log_dmt_results(clock, final_scores)

    async def _switch_team(self, interaction: discord.Interaction, team: str):
        if not user_is_admin(interaction):
            return await interaction.response.send_message("❌ Admin role required.", ephemeral=True)

        clock = clocks[self.channel_id]
        now = datetime.datetime.now(timezone.utc)

        switch_data = {
            'from_team': clock.active,
            'to_team': team,
            'timestamp': now,
            'method': 'manual'
        }

        if not clock.clock_started:
            clock.clock_started = True
            clock.last_switch = now
            clock.active = team
            clock.switches = [switch_data]
        else:
            elapsed = (now - clock.last_switch).total_seconds()
            
            if clock.active == "A":
                clock.time_a += elapsed
            elif clock.active == "B":
                clock.time_b += elapsed
            
            clock.active = team
            clock.last_switch = now
            clock.switches.append(switch_data)

        if clock.crcon_client:
            team_name = "Allies" if team == "A" else "Axis"
            allies_time = clock.format_time(clock.total_time('A'))
            axis_time = clock.format_time(clock.total_time('B'))
            await clock.crcon_client.send_message(f"⚔️ {team_name} captured! | Allies: {allies_time} | Axis: {axis_time}")

        await interaction.response.defer()
        await clock.message.edit(embed=build_embed(clock), view=self)

async def log_dmt_results(clock: ClockState, scores: dict):
    """Log DMT match results"""
    if not LOG_CHANNEL_ID:
        return
        
    results_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not results_channel:
        return
    
    embed = discord.Embed(title="🏁 DMT Match Complete", color=0x800020)
    
    # Quick summary
    allies_total = scores['allies']['total_dmt']
    axis_total = scores['axis']['total_dmt']
    
    embed.add_field(name="🇺🇸 Allies DMT", value=f"`{allies_total:.1f}`", inline=True)
    embed.add_field(name="🇩🇪 Axis DMT", value=f"`{axis_total:.1f}`", inline=True)
    
    if allies_total > axis_total:
        winner = f"🏆 Allies (+{allies_total - axis_total:.1f})"
    elif axis_total > allies_total:
        winner = f"🏆 Axis (+{axis_total - allies_total:.1f})"
    else:
        winner = "🤝 Draw"
    
    embed.add_field(name="Winner", value=winner, inline=True)
    
    # Breakdown
    embed.add_field(
        name="Allies Breakdown",
        value=f"Combat: `{scores['allies']['total_combat']}`\nCap: `{scores['allies']['total_cap']:.1f}`",
        inline=True
    )
    embed.add_field(
        name="Axis Breakdown",
        value=f"Combat: `{scores['axis']['total_combat']}`\nCap: `{scores['axis']['total_cap']:.1f}`",
        inline=True
    )
    
    embed.timestamp = datetime.datetime.now(timezone.utc)
    
    await results_channel.send(embed=embed)

@tasks.loop(seconds=int(os.getenv('UPDATE_INTERVAL', '15')))
async def match_updater(channel_id):
    """Update match display with live game time and scores"""
    clock = clocks.get(channel_id)
    if not clock or not clock.started or not clock.message:
        return

    try:
        if clock.crcon_client:
            try:
                await clock.update_from_game()
            except Exception as e:
                logger.warning(f"CRCON update failed, attempting reconnect: {e}")
                await clock.connect_crcon()

        game_info = clock.get_game_info()
        if game_info['connection_status'] == 'Connected' and game_info['game_time'] <= 30:
            logger.info("Game time ended, automatically stopping match")
            await auto_stop_match(clock, game_info)
            return

        try:
            await clock.message.edit(embed=build_embed(clock))
        except discord.HTTPException as e:
            logger.warning(f"Could not update message: {e}")

    except Exception as e:
        logger.error(f"Error in match updater: {e}")

async def auto_stop_match(clock: ClockState, game_info: dict):
    """Automatically stop match when game time ends"""
    try:
        if clock.active and clock.last_switch:
            elapsed = (datetime.datetime.now(timezone.utc) - clock.last_switch).total_seconds()
            if clock.active == "A":
                clock.time_a += elapsed
            elif clock.active == "B":
                clock.time_b += elapsed

        clock.active = None
        clock.started = False

        # Calculate final DMT scores
        final_scores = clock.calculate_final_scores()
        
        # Send final message to game
        if clock.crcon_client:
            allies_dmt = final_scores['allies']['total_dmt']
            axis_dmt = final_scores['axis']['total_dmt']
            
            if allies_dmt > axis_dmt:
                winner_msg = f"Allies WIN by DMT Score! {allies_dmt:.1f} - {axis_dmt:.1f}"
            elif axis_dmt > allies_dmt:
                winner_msg = f"Axis WIN by DMT Score! {axis_dmt:.1f} - {allies_dmt:.1f}"
            else:
                winner_msg = f"DRAW by DMT Score! {allies_dmt:.1f} - {axis_dmt:.1f}"
            
            await clock.crcon_client.send_message(f"🏁 Match Complete! {winner_msg}")

        # Create final embed
        embed = build_final_dmt_embed(clock, final_scores)
        embed.add_field(name="🕐 End Reason", value="⏰ Game Time Expired", inline=False)

        await clock.message.edit(embed=embed, view=None)
        
        # Post to channel
        channel = clock.message.channel
        await channel.send("🏁 **MATCH COMPLETE - DMT SCORES CALCULATED!** 🏁", embed=embed)

        await log_dmt_results(clock, final_scores)
        
        logger.info("Match automatically stopped due to game time expiring")

    except Exception as e:
        logger.error(f"Error in auto_stop_match: {e}")

# Bot commands
@bot.tree.command(name="dmt_clock", description="Start the HLL Tank Overwatch DMT scoring clock")
async def dmt_clock(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    clocks[channel_id] = ClockState()

    embed = build_embed(clocks[channel_id])
    view = StartControls(channel_id)

    await interaction.response.send_message("✅ HLL Tank Overwatch DMT clock ready!", ephemeral=True)
    posted_message = await interaction.channel.send(embed=embed, view=view)
    clocks[channel_id].message = posted_message

@bot.tree.command(name="help_dmt", description="Show help for the DMT scoring system")
async def help_dmt(interaction: discord.Interaction):
    embed = discord.Embed(title="🎯 HLL Tank Overwatch - DMT Scoring Help", color=0x0099ff)
    
    embed.add_field(
        name="📐 DMT Scoring Formula",
        value=(
            "**Total Score = Combat Score + Cap Score**\n\n"
            "**Combat Score:** (3 × Top 4 Crew Scores) + Cmdr P-Strike\n"
            "**Cap Score:** Center Point Seconds × 0.5"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎮 How It Works",
        value=(
            "1. Track center point control time (already doing)\n"
            "2. Track combat scores from tank crews\n"
            "3. Track commander precision strike score\n"
            "4. Calculate final DMT score at match end\n"
            "5. Winner = highest DMT total score"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📋 Commands",
        value=(
            "`/dmt_clock` - Start a DMT scoring clock\n"
            "`/help_dmt` - Show this help message"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value=(
            "• Keep 4 tank crews active for max points\n"
            "• Commander P-strikes add directly to score\n"
            "• Every 2 seconds of center control = 1 point\n"
            "• Balance combat and objective play!"
        ),
        inline=False
    )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Error handling
@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Bot error in {event}: {args}")

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    error_msg = f"❌ Error: {str(error)}"
    try:
        if not interaction.response.is_done():
            await interaction.response.send_message(error_msg, ephemeral=True)
        else:
            await interaction.followup.send(error_msg, ephemeral=True)
    except:
        logger.error(f"Could not send error message: {error}")

@bot.event
async def on_ready():
    logger.info(f"✅ Bot logged in as {bot.user}")
    logger.info(f"🔗 CRCON URL: {os.getenv('CRCON_URL', 'Not configured')}")
    logger.info(f"📊 DMT Scoring: {os.getenv('DMT_SCORING', 'true')}")
    
    try:
        test_client = APIKeyCRCONClient()
        async with test_client as client:
            live_data = await client.get_live_game_state()
            if live_data:
                logger.info("✅ CRCON connection verified on startup")
            else:
                logger.warning("🟡 CRCON connected but no game data")
    except Exception as e:
        logger.warning(f"⚠️ CRCON connection test failed: {e}")
    
    await bot.wait_until_ready()
    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} slash commands")
        print(f"🎉 HLL Tank Overwatch with DMT Scoring ready! Use /dmt_clock to start")
    except Exception as e:
        logger.error(f"❌ Command sync failed: {e}")

if __name__ == "__main__":
    print("🚀 Starting HLL Tank Overwatch Bot with DMT Scoring...")
    print("📐 DMT Formula: (3×Top4Crews) + CmdrPStrike + (CenterSeconds×0.5)")
    
    token = os.getenv("DISCORD_TOKEN")
    if not token or token == "your_discord_bot_token_here":
        print("❌ DISCORD_TOKEN not configured!")
        exit(1)
    
    api_key = os.getenv("CRCON_API_KEY")
    if not api_key or api_key == "your_crcon_api_key_here":
        print("❌ CRCON_API_KEY not configured!")
        exit(1)
    
    print(f"🔗 CRCON: {os.getenv('CRCON_URL', 'http://localhost:8010')}")
    print(f"📊 DMT Scoring: {os.getenv('DMT_SCORING', 'true')}")
    print(f"🔄 Auto-Switch: {os.getenv('CRCON_AUTO_SWITCH', 'true')}")
    
    try:
        bot.run(token)
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"❌ Bot startup failed: {e}")
