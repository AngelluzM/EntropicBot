from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bot.systems import ActionResult, ConfigError, ExternalSystem, SystemClient, SystemRegistry


MAX_SHEET_SUMMARY_LENGTH = 1200


@dataclass(frozen=True)
class CharacterSheetBinding:
    discord_user_id: int
    system_name: str
    character_id: str
    alias: str | None = None
    last_synced_at: str | None = None
    last_status: int | None = None
    last_error: str | None = None
    snapshot: str | None = None

    @property
    def label(self) -> str:
        return self.alias or self.character_id


class CharacterSheetStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def upsert_binding(
        self,
        discord_user_id: int,
        system_name: str,
        character_id: str,
        alias: str | None = None,
    ) -> CharacterSheetBinding:
        data = self._read()
        bindings = data["bindings"]
        existing = _find_binding(bindings, discord_user_id, system_name, character_id)

        if existing is None:
            binding = CharacterSheetBinding(
                discord_user_id=discord_user_id,
                system_name=system_name,
                character_id=character_id,
                alias=alias,
            )
            bindings.append(_binding_to_dict(binding))
        else:
            existing["alias"] = alias or existing.get("alias")
            binding = _binding_from_dict(existing)

        self._write(data)
        return binding

    def list_for_user(self, discord_user_id: int) -> list[CharacterSheetBinding]:
        data = self._read()
        return [
            _binding_from_dict(binding)
            for binding in data["bindings"]
            if int(binding.get("discord_user_id", 0)) == discord_user_id
        ]

    def list_all(self) -> list[CharacterSheetBinding]:
        data = self._read()
        return [_binding_from_dict(binding) for binding in data["bindings"]]

    def update_sync_result(
        self,
        binding: CharacterSheetBinding,
        *,
        status: int | None,
        snapshot: str | None,
        error: str | None,
    ) -> CharacterSheetBinding:
        data = self._read()
        bindings = data["bindings"]
        existing = _find_binding(
            bindings,
            binding.discord_user_id,
            binding.system_name,
            binding.character_id,
        )

        if existing is None:
            existing = _binding_to_dict(binding)
            bindings.append(existing)

        existing["last_synced_at"] = datetime.now(UTC).isoformat()
        existing["last_status"] = status
        existing["last_error"] = error
        existing["snapshot"] = snapshot

        self._write(data)
        return _binding_from_dict(existing)

    def _read(self) -> dict[str, list[dict[str, Any]]]:
        if not self._path.exists():
            return {"bindings": []}

        data = json.loads(self._path.read_text(encoding="utf-8"))
        bindings = data.get("bindings", [])
        if not isinstance(bindings, list):
            raise ConfigError(f"{self._path} must contain a bindings list")

        return {"bindings": [binding for binding in bindings if isinstance(binding, dict)]}

    def _write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(self._path)


class CharacterSheetSyncer:
    def __init__(
        self,
        registry: SystemRegistry,
        client: SystemClient,
        store: CharacterSheetStore,
    ) -> None:
        self._registry = registry
        self._client = client
        self._store = store

    async def sync_binding(self, binding: CharacterSheetBinding) -> CharacterSheetBinding:
        try:
            system = self._registry.get_system(binding.system_name)
            payload = _sheet_payload(system, binding.character_id)
            result = await self._client.execute(
                binding.system_name,
                system.sheet.action if system.sheet else "",
                payload,
            )
            snapshot = summarize_sheet_result(result)
            error = None if result.ok else f"HTTP {result.status}"
            return self._store.update_sync_result(
                binding,
                status=result.status,
                snapshot=snapshot,
                error=error,
            )
        except Exception as exc:
            return self._store.update_sync_result(
                binding,
                status=None,
                snapshot=binding.snapshot,
                error=str(exc),
            )

    async def sync_user(self, discord_user_id: int) -> list[CharacterSheetBinding]:
        synced: list[CharacterSheetBinding] = []
        for binding in self._store.list_for_user(discord_user_id):
            synced.append(await self.sync_binding(binding))
        return synced

    async def sync_all(self) -> list[CharacterSheetBinding]:
        synced: list[CharacterSheetBinding] = []
        for binding in self._store.list_all():
            synced.append(await self.sync_binding(binding))
        return synced


def summarize_sheet_result(result: ActionResult) -> str:
    body = result.body.strip()
    if not body:
        return "(resposta sem conteudo)"

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return _truncate(body)

    if isinstance(parsed, dict):
        lines = _known_character_fields(parsed)
        if lines:
            return _truncate("\n".join(lines))

    return _truncate(json.dumps(parsed, ensure_ascii=False, indent=2))


def format_binding(binding: CharacterSheetBinding, system: ExternalSystem | None = None) -> str:
    system_name = system.display_name if system else binding.system_name
    lines = [
        f"**{binding.label}**",
        f"Sistema: {system_name}",
        f"ID: `{binding.character_id}`",
    ]

    if binding.last_synced_at:
        lines.append(f"Ultima sync: {binding.last_synced_at}")

    if binding.last_error:
        lines.append(f"Erro na ultima sync: {binding.last_error}")

    if binding.snapshot:
        lines.append(f"```text\n{binding.snapshot}\n```")
    else:
        lines.append("Ficha ainda nao sincronizada.")

    return "\n".join(lines)


def _sheet_payload(system: ExternalSystem, character_id: str) -> dict[str, str]:
    if not system.sheet:
        raise ConfigError(f"System '{system.name}' does not have sheet sync configured")

    return {system.sheet.id_payload_key: character_id}


def _known_character_fields(parsed: dict[str, Any]) -> list[str]:
    field_labels = [
        ("Nome", ("name", "nome", "character_name", "personagem")),
        ("Nivel", ("level", "nivel")),
        ("Classe", ("class", "classe", "archetype", "arquetipo")),
        ("Raca", ("race", "raca", "ancestry")),
        ("Status", ("status", "state", "estado")),
    ]

    lines: list[str] = []
    for label, keys in field_labels:
        value = _first_present(parsed, keys)
        if value is not None:
            lines.append(f"{label}: {value}")

    if not lines:
        return []

    updated_at = _first_present(parsed, ("updated_at", "updatedAt", "ultima_atualizacao"))
    if updated_at is not None:
        lines.append(f"Atualizada no sistema: {updated_at}")

    return lines


def _first_present(parsed: dict[str, Any], keys: tuple[str, ...]) -> Any | None:
    for key in keys:
        if key in parsed:
            return parsed[key]
    return None


def _truncate(value: str) -> str:
    if len(value) <= MAX_SHEET_SUMMARY_LENGTH:
        return value

    return f"{value[:MAX_SHEET_SUMMARY_LENGTH]}\n... (resumo truncado)"


def _find_binding(
    bindings: list[dict[str, Any]],
    discord_user_id: int,
    system_name: str,
    character_id: str,
) -> dict[str, Any] | None:
    for binding in bindings:
        if (
            int(binding.get("discord_user_id", 0)) == discord_user_id
            and binding.get("system_name") == system_name
            and binding.get("character_id") == character_id
        ):
            return binding

    return None


def _binding_from_dict(raw: dict[str, Any]) -> CharacterSheetBinding:
    return CharacterSheetBinding(
        discord_user_id=int(raw["discord_user_id"]),
        system_name=str(raw["system_name"]),
        character_id=str(raw["character_id"]),
        alias=raw.get("alias"),
        last_synced_at=raw.get("last_synced_at"),
        last_status=raw.get("last_status"),
        last_error=raw.get("last_error"),
        snapshot=raw.get("snapshot"),
    )


def _binding_to_dict(binding: CharacterSheetBinding) -> dict[str, Any]:
    return {
        "discord_user_id": binding.discord_user_id,
        "system_name": binding.system_name,
        "character_id": binding.character_id,
        "alias": binding.alias,
        "last_synced_at": binding.last_synced_at,
        "last_status": binding.last_status,
        "last_error": binding.last_error,
        "snapshot": binding.snapshot,
    }
