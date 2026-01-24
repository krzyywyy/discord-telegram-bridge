from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import discord
from discord import app_commands
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bridge_config import BridgeConfig, normalize_bridge_name
from message_store import MessageStore

TELEGRAM_MESSAGE_LIMIT = 4096
DISCORD_MESSAGE_LIMIT = 2000


def load_dotenv(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw_line in p.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if sep != "=":
            continue
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


def split_text(text: str, limit: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    out: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut < max(1, limit // 2):
            cut = limit
        out.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    if remaining:
        out.append(remaining)
    return out


def format_discord_message(message: discord.Message) -> str | None:
    parts: list[str] = []
    content = (message.content or "").strip()
    if content:
        parts.append(content)
    for att in message.attachments:
        parts.append(att.url)

    body = "\n".join(parts).strip()
    if not body:
        return None

    guild = message.guild.name if message.guild else "DM"
    channel_name = getattr(message.channel, "name", str(message.channel.id))
    author = message.author.display_name
    return f"[Discord {guild}#{channel_name}] {author}:\n{body}"


def format_telegram_message(message) -> str | None:
    parts: list[str] = []
    if getattr(message, "text", None):
        parts.append(message.text)
    elif getattr(message, "caption", None):
        parts.append(message.caption)
    else:
        kind = None
        if getattr(message, "photo", None):
            kind = "photo"
        elif getattr(message, "document", None):
            kind = "document"
        elif getattr(message, "sticker", None):
            kind = "sticker"
        elif getattr(message, "voice", None):
            kind = "voice"
        elif getattr(message, "video", None):
            kind = "video"
        if kind:
            parts.append(f"[{kind}]")

    body = "\n".join(p for p in parts if p).strip()
    if not body:
        return None

    chat = message.chat
    chat_name = chat.title or chat.username or str(chat.id)
    user = message.from_user
    if user is None:
        author = "Unknown"
    else:
        author = user.full_name or (user.username or str(user.id))
        if user.username:
            author = f"{author} (@{user.username})"
    return f"[Telegram {chat_name}] {author}:\n{body}"


class BridgeDiscordClient(discord.Client):
    def __init__(
        self,
        *,
        config: BridgeConfig,
        store: MessageStore,
        telegram_app: Application,
        guild_id: int | None = None,
    ) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._config = config
        self._store = store
        self._telegram_app = telegram_app
        self._guild_id = guild_id
        self._channel_cache: dict[int, discord.abc.Messageable] = {}

    async def setup_hook(self) -> None:
        self._register_commands()
        if self._guild_id:
            guild = discord.Object(id=self._guild_id)
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
                logging.info("Discord commands synced to guild id=%s", self._guild_id)
            except discord.Forbidden:
                logging.warning(
                    "Discord command sync failed for guild id=%s (Missing Access). "
                    "Invite the bot to that server or remove DISCORD_GUILD_ID to use global sync.",
                    self._guild_id,
                )
                await self.tree.sync()
        else:
            await self.tree.sync()

    def _register_commands(self) -> None:
        @self.tree.command(
            name="here", description="Add this Discord channel to a Discord↔Telegram bridge."
        )
        @app_commands.describe(bridge="Bridge name (default: default)")
        async def here(interaction: discord.Interaction, bridge: str = "default") -> None:
            bridge = normalize_bridge_name(bridge)
            channel = interaction.channel
            if channel is None:
                await interaction.response.send_message(
                    "I couldn't determine the channel for this interaction.", ephemeral=True
                )
                return
            added = await self._config.add_discord_channel(bridge, channel.id)
            msg = (
                f"Added this channel to bridge `{bridge}`."
                if added
                else f"This channel is already in bridge `{bridge}`."
            )
            await interaction.response.send_message(msg, ephemeral=True)

        @self.tree.command(name="unhere", description="Remove this Discord channel from a bridge.")
        @app_commands.describe(bridge="Bridge name (default: default)")
        async def unhere(interaction: discord.Interaction, bridge: str = "default") -> None:
            bridge = normalize_bridge_name(bridge)
            channel = interaction.channel
            if channel is None:
                await interaction.response.send_message(
                    "I couldn't determine the channel for this interaction.", ephemeral=True
                )
                return
            removed = await self._config.remove_discord_channel(bridge, channel.id)
            msg = (
                f"Removed this channel from bridge `{bridge}`."
                if removed
                else f"This channel is not in bridge `{bridge}`."
            )
            await interaction.response.send_message(msg, ephemeral=True)

        @self.tree.command(name="bridges", description="Show configured bridges.")
        async def bridges(interaction: discord.Interaction) -> None:
            data = self._config.list_bridges()
            if not data:
                await interaction.response.send_message("No bridges configured.", ephemeral=True)
                return
            lines: list[str] = []
            for name, cfg in sorted(data.items()):
                lines.append(
                    f"- {name}: dc={len(cfg['discord_channels'])}, tg={len(cfg['telegram_chats'])}"
                )
            await interaction.response.send_message("\n".join(lines), ephemeral=True)

    async def on_ready(self) -> None:
        logging.info("Discord connected as %s (id=%s)", self.user, getattr(self.user, "id", None))

    async def _get_channel(self, channel_id: int):
        cached = self.get_channel(channel_id)
        if cached is not None:
            return cached
        if channel_id in self._channel_cache:
            return self._channel_cache[channel_id]
        fetched = await self.fetch_channel(channel_id)
        self._channel_cache[channel_id] = fetched
        return fetched

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or message.webhook_id is not None:
            return
        if message.guild is None:
            return
        if message.type is not discord.MessageType.default:
            return

        bridges = self._config.bridges_for_discord_channel(message.channel.id)
        if not bridges:
            return

        text = format_discord_message(message)
        if not text:
            return

        parent_discord_id: int | None = None
        if message.reference and message.reference.message_id:
            parent_discord_id = int(message.reference.message_id)

        for bridge in bridges:
            tg_chats = self._config.telegram_chats(bridge)
            if not tg_chats:
                continue
            await self._relay_discord_to_telegram(
                bridge=bridge,
                message=message,
                text=text,
                tg_chat_ids=tg_chats,
                parent_discord_id=parent_discord_id,
            )

    async def _relay_discord_to_telegram(
        self,
        *,
        bridge: str,
        message: discord.Message,
        text: str,
        tg_chat_ids: list[int],
        parent_discord_id: int | None,
    ) -> None:
        bot = self._telegram_app.bot

        async def send_one(chat_id: int):
            reply_to = None
            if parent_discord_id is not None:
                reply_to = await self._store.find_telegram_message_id(
                    discord_channel_id=message.channel.id,
                    discord_message_id=parent_discord_id,
                    telegram_chat_id=chat_id,
                )

            chunks = split_text(text, TELEGRAM_MESSAGE_LIMIT)
            if not chunks:
                return

            sent_messages = []
            sent_first = await bot.send_message(
                chat_id=chat_id,
                text=chunks[0],
                reply_to_message_id=reply_to,
                disable_web_page_preview=True,
            )
            sent_messages.append(sent_first)
            for chunk in chunks[1:]:
                sent = await bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    disable_web_page_preview=True,
                )
                sent_messages.append(sent)

            for sent in sent_messages:
                await self._store.save_map(
                    bridge=bridge,
                    discord_channel_id=message.channel.id,
                    discord_message_id=message.id,
                    telegram_chat_id=chat_id,
                    telegram_message_id=sent.message_id,
                )

        results = await asyncio.gather(
            *(send_one(chat_id) for chat_id in tg_chat_ids), return_exceptions=True
        )
        for res in results:
            if isinstance(res, Exception):
                logging.exception("Discord→Telegram relay error: %s", res)

    async def send_telegram_to_discord(
        self,
        *,
        bridge: str,
        telegram_message,
        discord_channel_ids: list[int],
        text: str,
        parent_telegram_id: int | None,
    ) -> None:
        async def send_one(channel_id: int):
            channel = await self._get_channel(channel_id)
            if not hasattr(channel, "send"):
                return

            reference = None
            if parent_telegram_id is not None:
                parent_discord_id = await self._store.find_discord_message_id(
                    telegram_chat_id=telegram_message.chat.id,
                    telegram_message_id=parent_telegram_id,
                    discord_channel_id=channel_id,
                )
                if parent_discord_id is not None:
                    try:
                        guild_id = getattr(getattr(channel, "guild", None), "id", None)
                        reference = discord.MessageReference(
                            message_id=parent_discord_id,
                            channel_id=channel_id,
                            guild_id=guild_id,
                            fail_if_not_exists=False,
                        )
                    except Exception:
                        reference = None

            chunks = split_text(text, DISCORD_MESSAGE_LIMIT)
            if not chunks:
                return

            sent_messages = []
            sent_first = await channel.send(
                chunks[0],
                reference=reference,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            sent_messages.append(sent_first)
            for chunk in chunks[1:]:
                sent = await channel.send(
                    chunk,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                sent_messages.append(sent)

            for sent in sent_messages:
                await self._store.save_map(
                    bridge=bridge,
                    discord_channel_id=channel_id,
                    discord_message_id=sent.id,
                    telegram_chat_id=telegram_message.chat.id,
                    telegram_message_id=telegram_message.message_id,
                )

        results = await asyncio.gather(
            *(send_one(cid) for cid in discord_channel_ids), return_exceptions=True
        )
        for res in results:
            if isinstance(res, Exception):
                logging.exception("Telegram→Discord relay error: %s", res)


async def build_telegram_app(
    *,
    token: str,
    config: BridgeConfig,
) -> Application:
    app = ApplicationBuilder().token(token).build()

    async def here(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None:
            return
        bridge = normalize_bridge_name(context.args[0] if context.args else "default")
        added = await config.add_telegram_chat(bridge, update.effective_chat.id)
        msg = (
            f"Added this chat to bridge '{bridge}'."
            if added
            else f"This chat is already in bridge '{bridge}'."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def unhere(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None:
            return
        bridge = normalize_bridge_name(context.args[0] if context.args else "default")
        removed = await config.remove_telegram_chat(bridge, update.effective_chat.id)
        msg = (
            f"Removed this chat from bridge '{bridge}'."
            if removed
            else f"This chat is not in bridge '{bridge}'."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

    async def bridges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None:
            return
        data = config.list_bridges()
        if not data:
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text="No bridges configured."
            )
            return
        lines: list[str] = []
        for name, cfg in sorted(data.items()):
            lines.append(
                f"- {name}: dc={len(cfg['discord_channels'])}, tg={len(cfg['telegram_chats'])}"
            )
        await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines))

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        discord_client: BridgeDiscordClient | None = context.application.bot_data.get(
            "discord_client"
        )
        if discord_client is None:
            return
        if update.effective_message is None or update.effective_chat is None:
            return
        msg = update.effective_message
        if msg.from_user is None or msg.from_user.is_bot:
            return
        if update.effective_chat.type == ChatType.CHANNEL:
            return

        bridges_for_chat = config.bridges_for_telegram_chat(update.effective_chat.id)
        if not bridges_for_chat:
            return

        text = format_telegram_message(msg)
        if not text:
            return

        parent_tid = msg.reply_to_message.message_id if msg.reply_to_message else None

        for bridge in bridges_for_chat:
            discord_channels = config.discord_channels(bridge)
            if not discord_channels:
                continue
            await discord_client.send_telegram_to_discord(
                bridge=bridge,
                telegram_message=msg,
                discord_channel_ids=discord_channels,
                text=text,
                parent_telegram_id=parent_tid,
            )

    app.add_handler(CommandHandler("here", here))
    app.add_handler(CommandHandler("unhere", unhere))
    app.add_handler(CommandHandler("bridges", bridges))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_message))
    return app


async def run() -> None:
    load_dotenv()

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    discord_token = os.environ.get("DISCORD_TOKEN")
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not discord_token or not telegram_token:
        print("Missing DISCORD_TOKEN or TELEGRAM_BOT_TOKEN in env/.env.", file=sys.stderr)
        raise SystemExit(1)

    config_path = os.environ.get("CONFIG_PATH", "data/config.json")
    db_path = os.environ.get("DB_PATH", "data/message_map.sqlite3")
    guild_id_raw = os.environ.get("DISCORD_GUILD_ID", "").strip()
    guild_id = int(guild_id_raw) if guild_id_raw else None

    config = BridgeConfig(config_path)
    await config.load()

    store = MessageStore(db_path)
    await store.open()

    telegram_app = await build_telegram_app(
        token=telegram_token,
        config=config,
    )
    discord_client = BridgeDiscordClient(
        config=config,
        store=store,
        telegram_app=telegram_app,
        guild_id=guild_id,
    )
    telegram_app.bot_data["discord_client"] = discord_client

    async with telegram_app:
        await telegram_app.start()
        if telegram_app.updater is None:
            raise RuntimeError("Telegram updater is not available")
        await telegram_app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        try:
            await discord_client.start(discord_token)
        finally:
            try:
                await discord_client.close()
            except Exception:
                logging.exception("Error while closing Discord client")
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await store.close()


if __name__ == "__main__":
    asyncio.run(run())
