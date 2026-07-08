#!/usr/bin/env python3
"""
Shorts Coin Prediction Bot - Fire Edition with Streaks
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

BOT_COLOR = 0x8B0000  # Deep Red
SHORTS_EMOJI = "📉"
BULL_EMOJI = "📈"


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    await init_db()
    print("✅ Database ready")
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} commands")
    except Exception as e:
        print(f"Sync error: {e}")


# ==================== MAIN COMMANDS ====================

@bot.tree.command(name="predict", description="Log a new leverage call")
@app_commands.describe(asset="Asset", direction="Direction", entry_price="Entry price", leverage="Leverage", notes="Thesis")
@app_commands.choices(direction=[
    app_commands.Choice(name="Short 📉", value="short"),
    app_commands.Choice(name="Long 📈", value="long")
])
async def predict_slash(interaction: discord.Interaction, asset: str, direction: Literal["long", "short"], entry_price: float, leverage: Optional[int] = 1, notes: Optional[str] = None):
    await interaction.response.defer()
    user = interaction.user
    if not leverage or leverage < 1: leverage = 1

    await upsert_user(user.id, str(user), user.display_name)

    pred_id = await create_prediction(user.id, str(user), user.display_name, asset.upper(), direction, entry_price, leverage, notes)

    emoji = SHORTS_EMOJI if direction == "short" else BULL_EMOJI
    color = 0x8B0000 if direction == "short" else 0x00FF7F

    embed = discord.Embed(title=f"{emoji} NEW {direction.upper()} CALL #{pred_id}", color=color, timestamp=datetime.utcnow())
    embed.description = f"**{asset.upper()}** @ `${entry_price:,.4f}`"
    embed.add_field(name="Leverage", value=f"**{leverage}x**", inline=True)
    embed.add_field(name="Trader", value=user.mention, inline=True)
    if notes:
        embed.add_field(name="Thesis", value=notes, inline=False)

    embed.set_footer(text="Shorts Coin • Honest calls only")
    embed.set_thumbnail(url="https://i.imgur.com/YourBearLogo.png")  # We'll replace with hosted link

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="resolve", description="Close your call")
@app_commands.describe(prediction_id="ID", outcome="win or loss")
@app_commands.choices(outcome=[app_commands.Choice(name="Win ✅", value="win"), app_commands.Choice(name="Loss ❌", value="loss")])
async def resolve_slash(interaction: discord.Interaction, prediction_id: int, outcome: Literal["win", "loss"]):
    await interaction.response.defer()
    prediction = await get_prediction(prediction_id)
    if not prediction or prediction["status"] != "open":
        await interaction.followup.send("Prediction not found or already closed.", ephemeral=True)
        return

    if prediction["user_id"] != interaction.user.id and not is_admin(interaction.user.id):
        await interaction.followup.send("Only the trader or admin can resolve.", ephemeral=True)
        return

    success = await resolve_prediction(prediction_id, outcome, interaction.user.id)
    if success:
        embed = discord.Embed(
            title=f"{'🚀 WIN' if outcome == 'win' else '💀 LOSS'} — CALL #{prediction_id}",
            color=0x00FF00 if outcome == "win" else 0xFF0000
        )
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send("Failed to resolve.")


@bot.tree.command(name="stats", description="Your record + current streak")
async def stats_slash(interaction: discord.Interaction):
    await interaction.response.defer()
    await upsert_user(interaction.user.id, str(interaction.user), interaction.user.display_name)
    stats = await get_user_stats(interaction.user.id)  # We'll enhance this later for streaks

    embed = discord.Embed(title="📊 YOUR SHORTS COIN RECORD", color=BOT_COLOR)
    embed.add_field(name="Net Score", value=f"**{stats['score']}**", inline=True)
    embed.add_field(name="Wins / Losses", value=f"✅ {stats['wins']} / ❌ {stats['losses']}", inline=True)
    embed.add_field(name="Win Rate", value=f"**{stats['win_rate']}%**", inline=True)
    embed.set_footer(text="Shorts Coin Bear Market Division")
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
        embed.add_field(name=f"{emoji} #{p['id']} {p['asset']}", value=f"<@{p['user_id']}> @ ${p['entry_price']:,.2f}", inline=False)
    await interaction.followup.send(embed=embed)


@bot.tree.command(name="help", description="Bot commands")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="🔥 SHORTS COIN PREDICTION BOT", color=BOT_COLOR)
    embed.description = "Professional bear market call tracker with streaks."
    embed.add_field(name="Main Commands", value="/predict /resolve /stats /leaderboard /active", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("❌ DISCORD_BOT_TOKEN not found in .env file!")
        exit(1)
    
    print("🚀 Starting Shorts Coin Bot...")
    print(f"👤 Admin IDs: {ADMIN_IDS}")
    
    try:
        bot.run(token)
    except Exception as e:
        print(f"❌ Bot crashed: {e}")