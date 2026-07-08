#!/usr/bin/env python3
"""
Shorts Coin Prediction Bot
"""

import os
import logging
from datetime import datetime
from typing import Optional, Literal

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database import (
    init_db, upsert_user, create_prediction, get_prediction,
    resolve_prediction, get_user_stats, get_leaderboard, get_open_predictions
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_USER_IDS", "").split(",") if x.strip().isdigit()]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

BOT_COLOR = 0x8B0000
SHORTS_EMOJI = "📉"
BULL_EMOJI = "📈"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await init_db()
    print("✅ Database ready")
    
    # Force sync to your server
    try:
        guild = discord.Object(id=1513362879250956288)
        synced = await bot.tree.sync(guild=guild)
        print(f"✅ Successfully synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Sync error: {e}")


# ==================== HELLO ====================
@bot.tree.command(name="hello", description="Greet the Shorts Coin Bear")
async def hello_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🐻 Hello from Shorts Coin!",
        description="What's good, trader? Hope you're crushing it today 🔥",
        color=BOT_COLOR,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="What I Do", value="I help the community log **leverage calls** (longs & shorts), track who’s actually profitable, and keep a clean leaderboard.", inline=False)
    embed.add_field(name="Quick Commands", value="`/predict` • `/resolve` • `/stats` • `/leaderboard` • `/active`", inline=False)
    embed.set_footer(text="Have a wonderful day in these bear markets 🐻💪")
    await interaction.response.send_message(embed=embed)


# ==================== PREDICT ====================
@bot.tree.command(name="predict", description="Log a new leverage prediction call")
@app_commands.describe(asset="Asset", direction="Direction", entry_price="Entry price", leverage="Leverage", notes="Notes")
@app_commands.choices(direction=[
    app_commands.Choice(name="Long 📈", value="long"),
    app_commands.Choice(name="Short 📉", value="short")
])
async def predict_slash(interaction: discord.Interaction, asset: str, direction: Literal["long", "short"], entry_price: float, leverage: Optional[int] = 1, notes: Optional[str] = None):
    await interaction.response.defer()
    user = interaction.user
    if leverage is None or leverage < 1: leverage = 1

    await upsert_user(user.id, str(user), user.display_name)

    try:
        pred_id = await create_prediction(user.id, str(user), user.display_name, asset.upper(), direction, entry_price, leverage, notes)
        
        color = discord.Color.red() if direction == "short" else discord.Color.green()
        embed = discord.Embed(title=f"{'📉' if direction == 'short' else '📈'} New {direction.upper()} Call #{pred_id}", color=color)
        embed.add_field(name="Asset", value=asset.upper(), inline=True)
        embed.add_field(name="Entry", value=f"${entry_price:,.2f}", inline=True)
        embed.add_field(name="Leverage", value=f"{leverage}x", inline=True)
        embed.add_field(name="Trader", value=user.mention, inline=False)
        if notes: embed.add_field(name="Notes", value=notes, inline=False)
        
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.error(f"Predict error: {e}")
        await interaction.followup.send("❌ Failed to log prediction.", ephemeral=True)


# ==================== RESOLVE ====================
@bot.tree.command(name="resolve", description="Resolve a prediction")
@app_commands.describe(prediction_id="Prediction ID", outcome="win or loss")
@app_commands.choices(outcome=[app_commands.Choice(name="Win ✅", value="win"), app_commands.Choice(name="Loss ❌", value="loss")])
async def resolve_slash(interaction: discord.Interaction, prediction_id: int, outcome: Literal["win", "loss"]):
    await interaction.response.defer()
    try:
        prediction = await get_prediction(prediction_id)
        if not prediction or prediction["status"] != "open":
            await interaction.followup.send("Prediction not found or already resolved.", ephemeral=True)
            return

        if prediction["user_id"] != interaction.user.id and not is_admin(interaction.user.id):
            await interaction.followup.send("Only the trader or admin can resolve.", ephemeral=True)
            return

        success = await resolve_prediction(prediction_id, outcome, interaction.user.id)
        if success:
            await interaction.followup.send(f"✅ Call #{prediction_id} resolved as **{outcome.upper()}**!")
        else:
            await interaction.followup.send("Failed to resolve.", ephemeral=True)
    except Exception as e:
        logger.error(f"Resolve error: {e}")
        await interaction.followup.send("Error processing command.", ephemeral=True)


# ==================== STATS, LEADERBOARD, ACTIVE ====================
@bot.tree.command(name="stats", description="Your record")
async def stats_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    await upsert_user(interaction.user.id, str(interaction.user), interaction.user.display_name)
    stats = await get_user_stats(interaction.user.id)
    embed = discord.Embed(title="📊 YOUR SHORTS COIN RECORD", color=BOT_COLOR)
    embed.add_field(name="Net Score", value=f"**{stats['score']}**", inline=True)
    embed.add_field(name="Wins / Losses", value=f"✅ {stats['wins']} / ❌ {stats['losses']}", inline=True)
    embed.add_field(name="Win Rate", value=f"**{stats['win_rate']}%**", inline=True)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="leaderboard", description="Top traders")
async def leaderboard_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    top = await get_leaderboard(10)
    if not top:
        await interaction.followup.send("No resolved calls yet!")
        return
    embed = discord.Embed(title="🏆 SHORTS COIN LEADERBOARD", color=0xFFD700)
    lines = [f"{i+1}. <@{e['user_id']}> — **{e['score']}** pts ({e['win_rate']}%)" for i, e in enumerate(top)]
    embed.description = "\n".join(lines)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="active", description="Open calls")
async def active_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    opens = await get_open_predictions()
    if not opens:
        await interaction.followup.send("No open calls right now.")
        return
    embed = discord.Embed(title="📋 LIVE OPEN CALLS", color=BOT_COLOR)
    for p in opens:
        emoji = SHORTS_EMOJI if p["direction"] == "short" else BULL_EMOJI
        embed.add_field(
            name=f"{emoji} #{p['id']} {p['asset']} {p['direction'].upper()}", 
            value=f"<@{p['user_id']}> @ ${p['entry_price']:,.2f}", 
            inline=False
        )
    await interaction.followup.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in .env!")
    else:
        bot.run(TOKEN)
