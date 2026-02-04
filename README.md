# Discord ↔ Telegram Bridge Bot

A lightweight, self-hosted bridge that relays messages between selected Discord channels and Telegram group chats.

## Features

- **Two-way relay**: Discord → Telegram and Telegram → Discord
- **Reply threading**: replies stay replies across platforms (when possible)
- **Multiple channels & groups**: add more than one Discord channel and more than one Telegram chat
- **Multiple bridges**: use an optional bridge name to keep separate “rooms”
- **Safe mentions**: Discord messages are sent with `AllowedMentions.none()` to avoid accidental mass pings
- **Persistent mapping**: uses a small SQLite DB to map message IDs for reply threading

## How it works

You “register” endpoints using `/here`:

- In a Discord channel run `/here` (or `/here bridge-name`) to add that channel
- In a Telegram chat send `/here` (or `/here bridge-name`) to add that chat

If a message is sent in any registered Discord channel, it is forwarded to the registered Telegram chats in the same bridge name (and vice versa).

Reply threading works only for messages that were relayed by this bot (because it needs stored ID mappings).

## Requirements

- Python 3.11+ recommended
- A Discord bot with **Message Content Intent** enabled
- A Telegram bot added to your group chat (see Telegram setup below)

## Setup

### 1) Create `.env`

Copy `.env.example` to `.env` and fill in tokens:

- `DISCORD_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- (optional) `DISCORD_GUILD_ID` for instant slash-command sync during development

### 2) Install dependencies

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 3) Run

```powershell
python main.py
```

### Windows autostart

If you want the bridge to start automatically when you log in (Windows), run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/install_autostart.ps1
```

This installs a small file in your Startup folder that launches the bridge in the background and writes logs to `data/bridge.log`.

To remove autostart:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/uninstall_autostart.ps1
```

## Discord setup (Developer Portal)

1. Go to Discord Developer Portal → **Applications** → **New Application**
2. Open **Bot** → **Add Bot**
3. In **Bot**:
   - click **Reset Token** → copy the token → set `DISCORD_TOKEN`
   - enable **Message Content Intent** (required for reading messages)
4. Invite the bot to your server:
   - open **OAuth2** → **URL Generator**
   - **Scopes**: `bot`, `applications.commands`
   - **Bot Permissions** (minimum):
     - `View Channels`
     - `Send Messages`
     - `Read Message History`
     - (optional) `Embed Links`
   - open the generated URL and invite the bot to your server

### About `DISCORD_GUILD_ID`

- If you set `DISCORD_GUILD_ID`, slash commands sync to that server almost instantly.
- If it’s wrong or the bot is not in that server, you may get:
  - `403 Forbidden (50001): Missing Access`
- Fix: set the correct server ID or remove `DISCORD_GUILD_ID` to use global sync (which can take longer to appear).

## Telegram setup

1. Create a bot via **@BotFather** (`/newbot`) and copy the token → set `TELEGRAM_BOT_TOKEN`
2. Add the bot to your group chat
3. If the bot does not receive group messages, do one of these:
   - disable privacy mode in BotFather: `/setprivacy` → `Disable`
   - or make the bot an admin in the group

## Usage

### Add endpoints

- Discord: run slash command `/here` in a channel you want to bridge
- Telegram: send `/here` in the group chat you want to bridge

Optional: keep separate bridges by naming them:

- Discord: `/here gaming`
- Telegram: `/here gaming`

### Remove endpoints

- Discord: `/unhere` (or `/unhere bridge-name`)
- Telegram: `/unhere` (or `/unhere bridge-name`)

### List bridges

- Discord: `/bridges`
- Telegram: `/bridges`

## Data files

- `data/config.json` – bridge configuration (channels/chats per bridge name)
- `data/message_map.sqlite3` – message ID mapping for reply threading

Both paths can be overridden via `.env`:

- `CONFIG_PATH`
- `DB_PATH`

## Troubleshooting

- **Discord: slash commands don’t show up**
  - if using global sync, wait (can take time)
  - set `DISCORD_GUILD_ID` to your server ID for fast sync
  - ensure the bot was invited with `applications.commands`
- **Discord: `Missing Access` / `403 (50001)`**
  - the `DISCORD_GUILD_ID` is wrong, or the bot is not in that server
  - fix the ID or remove `DISCORD_GUILD_ID`
- **Telegram: bot doesn’t see group messages**
  - disable privacy mode (`/setprivacy`) or make the bot an admin
- **Replies are not threaded**
  - replies only work for messages that were relayed by this bot (needs stored mapping)

## Security notes

- Never commit `.env` (it’s in `.gitignore`)
- If a token is ever leaked, rotate it immediately (Discord Developer Portal / BotFather)

## License

MIT (see `LICENSE`).
