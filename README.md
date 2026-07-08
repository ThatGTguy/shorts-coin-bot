# 📉 Discord Prediction Logger Bot

Same powerful prediction tracking system as the Telegram version, built for Discord with beautiful slash commands and embeds.

## Features
- `/predict` — Log leverage calls (long or short) with nice embeds
- `/resolve` — Close calls as win (+1) or loss (-1)
- `/stats` — Personal performance
- `/leaderboard` — Community rankings
- `/active` — See open calls
- Admin support (user IDs or roles named Admin/Moderator/Mod/Owner)

## Quick Setup

### 1. Create a Discord Bot
1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name
3. Go to **Bot** tab on the left → **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - Server Members Intent
   - Message Content Intent
5. Copy the **Token** (click Reset Token if needed)

### 2. Invite the Bot to Your Server
1. Go to **OAuth2** → **URL Generator**
2. Select scopes: `bot` and `applications.commands`
3. Select permissions: 
   - Send Messages
   - Embed Links
   - Read Message History
   - Use Slash Commands (automatic)
4. Copy the generated URL and open it to invite the bot.

### 3. Configure & Run
```bash
cd discord_prediction_bot

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your DISCORD_BOT_TOKEN + your Discord User ID
```

### 4. Run the Bot
```bash
python bot.py
```

You should see:
```
✅ Logged in as YourBotName
✅ Database ready
✅ Synced X slash commands
```

The slash commands should appear in your Discord server within a minute.

## How Community Members Use It

Use the slash commands directly in any channel:

- `/predict BTC short 98000 10 "Breakdown setup"`
- `/resolve 42 win`
- `/stats`, `/leaderboard`, `/active`, `/help`

Everything is formatted with nice colored embeds.

## Admin Setup

Add your Discord User ID to `ADMIN_USER_IDS` in `.env`.

You can also give users the role **Admin**, **Moderator**, **Mod**, or **Owner** — they will automatically be able to resolve any call.

## Database

Same SQLite file (`predictions.db`) as the Telegram version. You can even share the same database file between both bots if you want unified stats across platforms.

## Next Steps / Customization

Want me to add any of these?
- Target price & stop loss fields
- Auto price checking (current price + rough P&L)
- Require screenshot / proof when resolving
- Different scoring weights (higher leverage = more points)
- Daily/weekly leaderboards
- Export to Google Sheet or CSV
- Web dashboard

Just tell me and I’ll update the code.

Enjoy tracking those calls! 🏆
