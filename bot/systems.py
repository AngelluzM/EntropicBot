from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from string import Formatter
from typing import Any

import aiohttp


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


class ConfigError(ValueError):
    """Raised when the systems configuration cannot be loaded safely."""


@dataclass(frozen=True)
class SystemAction:
    name: str
    method: str
    path: str
    description: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 20


@dataclass(frozen=True)
class CharacterSheetConfig:
    action: str
    id_payload_key: str = "character_id"


@dataclass(frozen=True)
class ExternalSystem:
    name: str
    base_url: str
    display_name: str
    description: str = ""
    link: str | None = None
    sheet: CharacterSheetConfig | None = None
    headers: dict[str, str] = field(default_factory=dict)
    actions: dict[str, SystemAction] = field(default_factory=dict)


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    url: str
    headers: dict[str, str]
    params: dict[str, Any] | None
    json_body: dict[str, Any] | None
    timeout_seconds: float


@dataclass(frozen=True)
class ActionResult:
    status: int
    ok: bool
    content_type: str
    body: str


class SystemRegistry:
    def __init__(self, systems: dict[str, ExternalSystem]) -> None:
        self._systems = systems

    @property
    def systems(self) -> dict[str, ExternalSystem]:
        return self._systems

    @classmethod
    def from_file(cls, path: Path) -> SystemRegistry:
        if not path.exists():
            return cls({})

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SystemRegistry:
        raw_systems = data.get("systems", {})
        if not isinstance(raw_systems, dict):
            raise ConfigError("'systems' must be an object")

        systems: dict[str, ExternalSystem] = {}
        for system_name, raw_system in raw_systems.items():
            systems[system_name] = _parse_system(system_name, raw_system)

        return cls(systems)

    def get_system(self, name: str) -> ExternalSystem:
        try:
            return self._systems[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown system: {name}") from exc

    def get_action(self, system_name: str, action_name: str) -> tuple[ExternalSystem, SystemAction]:
        system = self.get_system(system_name)
        try:
            return system, system.actions[action_name]
        except KeyError as exc:
            raise ConfigError(f"Unknown action '{action_name}' for system '{system_name}'") from exc

    def list_actions(self) -> list[tuple[ExternalSystem, SystemAction]]:
        actions: list[tuple[ExternalSystem, SystemAction]] = []
        for system in self._systems.values():
            actions.extend((system, action) for action in system.actions.values())
        return actions


class SystemClient:
    def __init__(self, registry: SystemRegistry) -> None:
        self._registry = registry

    def prepare_request(
        self,
        system_name: str,
        action_name: str,
        payload: dict[str, Any] | None = None,
    ) -> PreparedRequest:
        payload = payload or {}
        system, action = self._registry.get_action(system_name, action_name)
        path_fields = _path_fields(action.path)
        url = _join_url(system.base_url, _format_path(action.path, payload, path_fields))
        headers = {**system.headers, **action.headers}
        request_payload = {
            key: value
            for key, value in payload.items()
            if key not in path_fields
        }

        method = action.method.upper()
        if method in {"GET", "DELETE"}:
            params = request_payload or None
            json_body = None
        else:
            params = None
            json_body = {**action.body, **request_payload} if action.body or request_payload else None

        return PreparedRequest(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json_body=json_body,
            timeout_seconds=action.timeout_seconds,
        )

    async def execute(
        self,
        system_name: str,
        action_name: str,
        payload: dict[str, Any] | None = None,
    ) -> ActionResult:
        request = self.prepare_request(system_name, action_name, payload)
        timeout = aiohttp.ClientTimeout(total=request.timeout_seconds)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                request.method,
                request.url,
                headers=request.headers,
                params=request.params,
                json=request.json_body,
            ) as response:
                body = await response.text()
                return ActionResult(
                    status=response.status,
                    ok=200 <= response.status < 300,
                    content_type=response.headers.get("content-type", ""),
                    body=body,
                )


def _parse_system(name: str, raw: Any) -> ExternalSystem:
    if not isinstance(raw, dict):
        raise ConfigError(f"System '{name}' must be an object")

    base_url = raw.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        raise ConfigError(f"System '{name}' requires base_url")

    raw_actions = raw.get("actions", {})
    if not isinstance(raw_actions, dict):
        raise ConfigError(f"System '{name}' actions must be an object")

    actions: dict[str, SystemAction] = {}
    for action_name, raw_action in raw_actions.items():
        actions[action_name] = _parse_action(action_name, raw_action)

    return ExternalSystem(
        name=name,
        base_url=_expand_env(base_url),
        display_name=str(raw.get("display_name", name)),
        description=str(raw.get("description", "")),
        link=_optional_expanded_string(raw.get("link"), f"system '{name}' link"),
        sheet=_parse_sheet_config(raw.get("sheet"), raw_actions, name),
        headers=_parse_headers(raw.get("headers", {}), f"system '{name}'"),
        actions=actions,
    )


def _parse_action(name: str, raw: Any) -> SystemAction:
    if not isinstance(raw, dict):
        raise ConfigError(f"Action '{name}' must be an object")

    method = str(raw.get("method", "GET")).upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ConfigError(f"Action '{name}' has unsupported method: {method}")

    path = raw.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ConfigError(f"Action '{name}' requires a path starting with '/'")

    body = raw.get("body", {})
    if not isinstance(body, dict):
        raise ConfigError(f"Action '{name}' body must be an object")

    return SystemAction(
        name=name,
        method=method,
        path=path,
        description=str(raw.get("description", "")),
        headers=_parse_headers(raw.get("headers", {}), f"action '{name}'"),
        body=_expand_env(body),
        timeout_seconds=float(raw.get("timeout_seconds", 20)),
    )


def _parse_headers(raw: Any, context: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ConfigError(f"Headers for {context} must be an object")

    return {str(key): str(_expand_env(value)) for key, value in raw.items()}


def _parse_sheet_config(raw: Any, raw_actions: dict[str, Any], system_name: str) -> CharacterSheetConfig | None:
    if raw is None:
        return None

    if not isinstance(raw, dict):
        raise ConfigError(f"Sheet config for system '{system_name}' must be an object")

    action = raw.get("action")
    if not isinstance(action, str) or not action:
        raise ConfigError(f"Sheet config for system '{system_name}' requires action")

    if action not in raw_actions:
        raise ConfigError(f"Sheet action '{action}' does not exist in system '{system_name}'")

    id_payload_key = raw.get("id_payload_key", "character_id")
    if not isinstance(id_payload_key, str) or not id_payload_key:
        raise ConfigError(f"Sheet id_payload_key for system '{system_name}' must be a string")

    return CharacterSheetConfig(action=action, id_payload_key=id_payload_key)


def _optional_expanded_string(raw: Any, context: str) -> str | None:
    if raw is None:
        return None

    if not isinstance(raw, str):
        raise ConfigError(f"{context} must be a string")

    return _expand_env(raw)


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            variable_name = match.group(1)
            try:
                return os.environ[variable_name]
            except KeyError as exc:
                raise ConfigError(f"Environment variable {variable_name} is required") from exc

        return _ENV_PATTERN.sub(replace, value)

    if isinstance(value, dict):
        return {key: _expand_env(inner_value) for key, inner_value in value.items()}

    if isinstance(value, list):
        return [_expand_env(inner_value) for inner_value in value]

    return value


def _path_fields(path: str) -> set[str]:
    formatter = Formatter()
    return {
        field_name
        for _, field_name, _, _ in formatter.parse(path)
        if field_name is not None
    }


def _format_path(path: str, payload: dict[str, Any], required_fields: set[str]) -> str:
    missing = required_fields - payload.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise ConfigError(f"Missing payload values for path: {names}")

    return path.format(**payload)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"
