from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any


def normalize_bridge_name(name: str | None) -> str:
    if not name:
        return "default"
    name = name.strip()
    if not name:
        return "default"
    return name[:64]


class BridgeConfig:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self._data: dict[str, Any] = {"bridges": {}}

    async def load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = await asyncio.to_thread(self.path.read_text, encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            return
        if isinstance(data, dict) and isinstance(data.get("bridges"), dict):
            self._data = data

    async def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(self._data, ensure_ascii=False, indent=2, sort_keys=True)
        await asyncio.to_thread(self.path.write_text, raw + "\n", encoding="utf-8")

    def bridges_for_discord_channel(self, channel_id: int) -> list[str]:
        bridges: dict[str, Any] = self._data.get("bridges", {})
        out: list[str] = []
        for name, cfg in bridges.items():
            if not isinstance(cfg, dict):
                continue
            channels = cfg.get("discord_channels", [])
            if isinstance(channels, list) and channel_id in channels:
                out.append(str(name))
        return out

    def bridges_for_telegram_chat(self, chat_id: int) -> list[str]:
        bridges: dict[str, Any] = self._data.get("bridges", {})
        out: list[str] = []
        for name, cfg in bridges.items():
            if not isinstance(cfg, dict):
                continue
            chats = cfg.get("telegram_chats", [])
            if isinstance(chats, list) and chat_id in chats:
                out.append(str(name))
        return out

    def discord_channels(self, bridge_name: str) -> list[int]:
        bridges: dict[str, Any] = self._data.get("bridges", {})
        cfg = bridges.get(bridge_name)
        if not isinstance(cfg, dict):
            return []
        channels = cfg.get("discord_channels", [])
        return [int(x) for x in channels] if isinstance(channels, list) else []

    def telegram_chats(self, bridge_name: str) -> list[int]:
        bridges: dict[str, Any] = self._data.get("bridges", {})
        cfg = bridges.get(bridge_name)
        if not isinstance(cfg, dict):
            return []
        chats = cfg.get("telegram_chats", [])
        return [int(x) for x in chats] if isinstance(chats, list) else []

    def list_bridges(self) -> dict[str, dict[str, list[int]]]:
        bridges: dict[str, Any] = self._data.get("bridges", {})
        out: dict[str, dict[str, list[int]]] = {}
        for name, cfg in bridges.items():
            if not isinstance(cfg, dict):
                continue
            out[str(name)] = {
                "discord_channels": [int(x) for x in cfg.get("discord_channels", [])]
                if isinstance(cfg.get("discord_channels", []), list)
                else [],
                "telegram_chats": [int(x) for x in cfg.get("telegram_chats", [])]
                if isinstance(cfg.get("telegram_chats", []), list)
                else [],
            }
        return out

    async def add_discord_channel(self, bridge_name: str, channel_id: int) -> bool:
        bridge_name = normalize_bridge_name(bridge_name)
        async with self._lock:
            bridges: dict[str, Any] = self._data.setdefault("bridges", {})
            cfg = bridges.setdefault(
                bridge_name, {"discord_channels": [], "telegram_chats": []}
            )
            if not isinstance(cfg, dict):
                bridges[bridge_name] = {"discord_channels": [], "telegram_chats": []}
                cfg = bridges[bridge_name]

            channels = cfg.get("discord_channels")
            if not isinstance(channels, list):
                channels = []
            if channel_id in channels:
                return False
            channels.append(channel_id)
            cfg["discord_channels"] = sorted(set(int(x) for x in channels))
            await self.save()
            return True

    async def add_telegram_chat(self, bridge_name: str, chat_id: int) -> bool:
        bridge_name = normalize_bridge_name(bridge_name)
        async with self._lock:
            bridges: dict[str, Any] = self._data.setdefault("bridges", {})
            cfg = bridges.setdefault(
                bridge_name, {"discord_channels": [], "telegram_chats": []}
            )
            if not isinstance(cfg, dict):
                bridges[bridge_name] = {"discord_channels": [], "telegram_chats": []}
                cfg = bridges[bridge_name]

            chats = cfg.get("telegram_chats")
            if not isinstance(chats, list):
                chats = []
            if chat_id in chats:
                return False
            chats.append(chat_id)
            cfg["telegram_chats"] = sorted(set(int(x) for x in chats))
            await self.save()
            return True

    async def remove_discord_channel(self, bridge_name: str, channel_id: int) -> bool:
        bridge_name = normalize_bridge_name(bridge_name)
        async with self._lock:
            bridges: dict[str, Any] = self._data.get("bridges", {})
            cfg = bridges.get(bridge_name)
            if not isinstance(cfg, dict):
                return False
            channels = cfg.get("discord_channels")
            if not isinstance(channels, list) or channel_id not in channels:
                return False
            cfg["discord_channels"] = sorted(int(x) for x in channels if int(x) != int(channel_id))
            if not cfg.get("discord_channels") and not cfg.get("telegram_chats"):
                bridges.pop(bridge_name, None)
            await self.save()
            return True

    async def remove_telegram_chat(self, bridge_name: str, chat_id: int) -> bool:
        bridge_name = normalize_bridge_name(bridge_name)
        async with self._lock:
            bridges: dict[str, Any] = self._data.get("bridges", {})
            cfg = bridges.get(bridge_name)
            if not isinstance(cfg, dict):
                return False
            chats = cfg.get("telegram_chats")
            if not isinstance(chats, list) or chat_id not in chats:
                return False
            cfg["telegram_chats"] = sorted(int(x) for x in chats if int(x) != int(chat_id))
            if not cfg.get("discord_channels") and not cfg.get("telegram_chats"):
                bridges.pop(bridge_name, None)
            await self.save()
            return True
