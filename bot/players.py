from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.systems import ConfigError


@dataclass(frozen=True)
class PlayerProfile:
    discord_user_id: int
    display_name: str
    preferred_system: str | None = None
    registered_at: str | None = None
    notes: str | None = None

    @property
    def is_registered(self) -> bool:
        return self.registered_at is not None


class PlayerStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def register(
        self,
        discord_user_id: int,
        display_name: str,
        preferred_system: str | None = None,
    ) -> PlayerProfile:
        data = self._read()
        players = data["players"]
        existing = _find_player(players, discord_user_id)

        if existing is None:
            profile = PlayerProfile(
                discord_user_id=discord_user_id,
                display_name=display_name,
                preferred_system=preferred_system,
                registered_at=datetime.now(UTC).isoformat(),
            )
            players.append(_profile_to_dict(profile))
        else:
            existing["display_name"] = display_name
            existing["preferred_system"] = preferred_system or existing.get("preferred_system")
            existing.setdefault("registered_at", datetime.now(UTC).isoformat())
            profile = _profile_from_dict(existing)

        self._write(data)
        return profile

    def get(self, discord_user_id: int) -> PlayerProfile | None:
        data = self._read()
        existing = _find_player(data["players"], discord_user_id)
        if existing is None:
            return None
        return _profile_from_dict(existing)

    def get_or_none(self, discord_user_id: int, display_name: str) -> PlayerProfile:
        profile = self.get(discord_user_id)
        if profile is not None:
            return profile

        return PlayerProfile(
            discord_user_id=discord_user_id,
            display_name=display_name,
        )

    def list_all(self) -> list[PlayerProfile]:
        data = self._read()
        return [_profile_from_dict(player) for player in data["players"]]

    def count(self) -> int:
        return len(self.list_all())

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        if not self._path.exists():
            return {"players": []}

        data = json.loads(self._path.read_text(encoding="utf-8"))
        players = data.get("players", [])
        if not isinstance(players, list):
            raise ConfigError(f"{self._path} must contain a players list")

        return {"players": [player for player in players if isinstance(player, dict)]}

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self._path)


def format_profile(profile: PlayerProfile, sheet_count: int = 0) -> str:
    lines = [
        f"**{profile.display_name}**",
        f"Discord ID: `{profile.discord_user_id}`",
    ]

    if profile.registered_at:
        lines.append(f"Registrado em: {profile.registered_at}")
    else:
        lines.append("Status: ainda nao registrado")

    if profile.preferred_system:
        lines.append(f"Sistema preferido: {profile.preferred_system}")

    lines.append(f"Fichas vinculadas: {sheet_count}")

    if profile.notes:
        lines.append(f"Observacoes: {profile.notes}")

    return "\n".join(lines)


def _find_player(players: list[dict[str, Any]], discord_user_id: int) -> dict[str, Any] | None:
    for player in players:
        if int(player.get("discord_user_id", 0)) == discord_user_id:
            return player
    return None


def _profile_from_dict(raw: dict[str, Any]) -> PlayerProfile:
    return PlayerProfile(
        discord_user_id=int(raw["discord_user_id"]),
        display_name=str(raw.get("display_name", "Jogador")),
        preferred_system=raw.get("preferred_system"),
        registered_at=raw.get("registered_at"),
        notes=raw.get("notes"),
    )


def _profile_to_dict(profile: PlayerProfile) -> dict[str, Any]:
    return {
        "discord_user_id": profile.discord_user_id,
        "display_name": profile.display_name,
        "preferred_system": profile.preferred_system,
        "registered_at": profile.registered_at,
        "notes": profile.notes,
    }
