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

BOT_COLOR = 0x8B0000  # Deep Bear Red


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


# ==================== NEW HELLO COMMAND ====================

@bot.tree.command(name="hello", description="Greet the Shorts Coin Bear")
async def hello_slash(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🐻 Hello from Shorts Coin!",
        description="What's good, trader? Hope you're crushing it today 🔥",
        color=BOT_COLOR,
        timestamp=datetime.utcnow()
    )
    embed.add_field(
        name="What I Do",
        value="I help the community log **leverage calls** (longs & shorts), track who’s actually profitable, and keep a clean leaderboard.",
        inline=False
    )
    embed.add_field(
        name="Quick Commands",
        value="`/predict` • `/resolve` • `/stats` • `/leaderboard` • `/active`",
        inline=False
    )
    embed.set_footer(text="Have a wonderful day in these bear markets 🐻💪")
    
    await interaction.response.send_message(embed=embed)


# ==================== EXISTING COMMANDS (unchanged) ====================

@bot.tree.command(name="predict", description="Log a new leverage prediction call")
@app_commands.describe(
    asset="The asset (e.g. BTC, ETH, SOL)",
    direction="Long or Short",
    entry_price="Entry price",
    leverage="Leverage (default 1, max 100)",
    notes="Optional notes or reasoning"
)
@app_commands.choices(direction=[
    app_commands.Choice(name="Long 📈", value="long"),
    app_commands.Choice(name="Short 📉", value="short"),
])
async def predict_slash(
    interaction: discord.Interaction,
    asset: str,
    direction: Literal["long", "short"],
    entry_price: float,
    leverage: Optional[int] = 1,
    notes: Optional[str] = None
):
    await interaction.response.defer()
    user = interaction.user
    if leverage is None or leverage < 1 or leverage > 100:
        leverage = 1

    await upsert_user(user.id, str(user), user.display_name)

    try:
        pred_id = await create_prediction(
            user_id=user.id,
            username=str(user),
            first_name=user.display_name,
            asset=asset.upper(),
            direction=direction,
            entry_price=entry_price,
            leverage=leverage,
            notes=notes
        )
    except Exception as e:
        logger.error(f"DB error: {e}")
        await interaction.followup.send("⚠️ Failed to log prediction.", ephemeral=True)
        return

    color = discord.Color.red() if direction == "short" else discord.Color.green()
    embed = discord.Embed(
        title=f"{'📉' if direction == 'short' else '📈'} New {direction.upper()} Call Logged",
        color=color,
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Asset", value=f"**{asset.upper()}** @ `${entry_price:,.4f}`", inline=True)
    embed.add_field(name="Leverage", value=f"{leverage}x", inline=True)
    embed.add_field(name="Prediction ID", value=f"**#{pred_id}**", inline=True)
    embed.add_field(name="Posted by", value=user.mention, inline=False)
    if notes:
        embed.add_field(name="Notes", value=notes, inline=False)

    embed.set_footer(text="Use /resolve when the call plays out • Shorts Coin")
    await interaction.followup.send(embed=embed)


# (The rest of your commands like /resolve, /stats, etc. stay the same)

# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        print("❌ DISCORD_BOT_TOKEN not found in .env!")
    else:
        bot.run(TOKEN)
