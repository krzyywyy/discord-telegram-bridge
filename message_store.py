from __future__ import annotations

import asyncio
import sqlite3
import time
from pathlib import Path


class MessageStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._conn: sqlite3.Connection | None = None

    async def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_map (
              bridge TEXT NOT NULL,
              discord_channel_id INTEGER NOT NULL,
              discord_message_id INTEGER NOT NULL,
              telegram_chat_id INTEGER NOT NULL,
              telegram_message_id INTEGER NOT NULL,
              created_at INTEGER NOT NULL,
              PRIMARY KEY (
                discord_channel_id,
                discord_message_id,
                telegram_chat_id,
                telegram_message_id
              )
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_discord_to_tg
            ON message_map(discord_channel_id, discord_message_id, telegram_chat_id)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tg_to_discord
            ON message_map(telegram_chat_id, telegram_message_id, discord_channel_id)
            """
        )
        self._conn.commit()

    async def close(self) -> None:
        async with self._lock:
            if self._conn is None:
                return
            self._conn.close()
            self._conn = None

    async def save_map(
        self,
        *,
        bridge: str,
        discord_channel_id: int,
        discord_message_id: int,
        telegram_chat_id: int,
        telegram_message_id: int,
    ) -> None:
        if self._conn is None:
            raise RuntimeError("MessageStore is not open")
        async with self._lock:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO message_map(
                  bridge,
                  discord_channel_id,
                  discord_message_id,
                  telegram_chat_id,
                  telegram_message_id,
                  created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    bridge,
                    int(discord_channel_id),
                    int(discord_message_id),
                    int(telegram_chat_id),
                    int(telegram_message_id),
                    int(time.time()),
                ),
            )
            self._conn.commit()

    async def find_telegram_message_id(
        self,
        *,
        discord_channel_id: int,
        discord_message_id: int,
        telegram_chat_id: int,
    ) -> int | None:
        if self._conn is None:
            raise RuntimeError("MessageStore is not open")
        async with self._lock:
            row = self._conn.execute(
                """
                SELECT MIN(telegram_message_id)
                FROM message_map
                WHERE discord_channel_id = ?
                  AND discord_message_id = ?
                  AND telegram_chat_id = ?
                """,
                (int(discord_channel_id), int(discord_message_id), int(telegram_chat_id)),
            ).fetchone()
        return int(row[0]) if row else None

    async def find_discord_message_id(
        self,
        *,
        telegram_chat_id: int,
        telegram_message_id: int,
        discord_channel_id: int,
    ) -> int | None:
        if self._conn is None:
            raise RuntimeError("MessageStore is not open")
        async with self._lock:
            row = self._conn.execute(
                """
                SELECT MIN(discord_message_id)
                FROM message_map
                WHERE telegram_chat_id = ?
                  AND telegram_message_id = ?
                  AND discord_channel_id = ?
                """,
                (int(telegram_chat_id), int(telegram_message_id), int(discord_channel_id)),
            ).fetchone()
        return int(row[0]) if row else None
