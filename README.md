# 🔗 Link Bypasser Bot (Updated)

A fully featured Telegram bot that bypasses 60+ shortlink services. Built on the original [bipinkrish/Link-Bypasser-Bot](https://github.com/bipinkrish/Link-Bypasser-Bot) with major upgrades.

## 🆕 What's New
- ✅ **No MongoDB** — lightweight file-based JSON storage
- ✅ **Admin Panel** — full command suite
- ✅ **Force Join** — your own channels
- ✅ **VIP System** — expiry-based with notifications
- ✅ **Cooldown & Daily Limits**
- ✅ **Render-ready** — no "no open ports" error
- ✅ **Auto-delete** bypass results after 10 minutes
- ✅ **Group auto-leave** (non-owner added)

## 🚀 Deploy on Render

### Step 1 — Get credentials
1. Create a bot via [@BotFather](https://t.me/BotFather) → copy **BOT TOKEN**
2. Get **API_ID** and **API_HASH** from [my.telegram.org](https://my.telegram.org)
3. Get your **OWNER_ID** from [@userinfobot](https://t.me/userinfobot)

### Step 2 — Deploy
1. Push this folder to a GitHub repo
2. Go to [render.com](https://render.com) → **New Web Service** → connect repo
3. Set **Start Command**: `python run.py`
4. Add Environment Variables:
   - `TOKEN` = bot token
   - `ID` = API ID
   - `HASH` = API hash
   - `OWNER_ID` = your user ID
   - `PORT` = `8080`
5. Click **Deploy** ✅

## 📋 Admin Commands

| Command | Who | Description |
|---|---|---|
| `/stats` | Admin | Bot statistics |
| `/maintenance on\|off` | Admin | Toggle maintenance mode |
| `/setcooldown <secs>` | Admin | Set cooldown between uses |
| `/removecooldown` | Admin | Remove cooldown |
| `/setlimit <n>` | Admin | Set daily usage limit |
| `/removelimit` | Admin | Remove daily limit |
| `/addadmin <id> [days]` | Owner | Add timed/permanent admin |
| `/removeadmin <id>` | Owner | Remove admin |
| `/addvip <id> [days]` | Admin | Grant VIP access |
| `/removevip <id>` | Admin | Remove VIP |
| `/ban <id>` | Admin | Ban user |
| `/unban <id>` | Admin | Unban user |
| `/broadcast <msg>` | Admin | Message all users |
| `/addforcejoin <@ch>` | Admin | Add force join channel |
| `/removeforcejoin <id>` | Admin | Remove force join channel |
| `/addbypass <domain>` | Admin | Add custom bypass domain |
| `/removebypass <domain>` | Admin | Remove custom bypass domain |

## 📁 Project Structure
```
finalbot/
├── run.py              ← Render entry point (web server + bot)
├── main.py             ← Bot logic + all commands
├── server.py           ← Flask web server (keeps port alive)
├── database.py         ← File-based JSON storage
├── middleware.py       ← Cooldown, limits, VIP, admin checks
├── bypasser.py         ← Original bypass engines (60+ sites)
├── ddl.py              ← Direct download link engines
├── freewall.py         ← Paywall bypass
├── texts.py            ← Help text
├── config.json         ← Config (use env vars on Render)
├── Procfile
├── render.yaml
├── requirements.txt
├── runtime.txt
├── .env.example
└── data/               ← Auto-created: users.json, settings.json
```
