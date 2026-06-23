from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    discord_token: str
    systems_config_path: Path
    sheets_store_path: Path
    players_store_path: Path
    discord_guild_id: int | None = None
    command_prefix: str = "!"
    sheet_sync_interval_hours: float = 24
    staff_role_ids: frozenset[int] = frozenset()


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is required")

    guild_id_value = os.getenv("DISCORD_GUILD_ID")
    guild_id = int(guild_id_value) if guild_id_value else None

    return Settings(
        discord_token=token,
        discord_guild_id=guild_id,
        systems_config_path=Path(os.getenv("SYSTEMS_CONFIG_PATH", "systems.json")),
        sheets_store_path=Path(os.getenv("SHEETS_STORE_PATH", "data/character_sheets.json")),
        players_store_path=Path(os.getenv("PLAYERS_STORE_PATH", "data/players.json")),
        command_prefix=os.getenv("DISCORD_COMMAND_PREFIX", "!"),
        sheet_sync_interval_hours=float(os.getenv("SHEET_SYNC_INTERVAL_HOURS", "24")),
        staff_role_ids=_parse_role_ids(os.getenv("DISCORD_STAFF_ROLE_IDS", "")),
    )


def _parse_role_ids(raw: str) -> frozenset[int]:
    if not raw.strip():
        return frozenset()

    return frozenset(int(value.strip()) for value in raw.split(",") if value.strip())
