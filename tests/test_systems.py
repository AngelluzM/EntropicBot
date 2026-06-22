from __future__ import annotations

import pytest

from bot.systems import ConfigError, SystemClient, SystemRegistry


def test_prepare_get_request_with_path_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_TOKEN", "secret-token")
    registry = SystemRegistry.from_dict(
        {
            "systems": {
                "orders": {
                    "base_url": "https://orders.example.com/",
                    "headers": {"Authorization": "Bearer ${API_TOKEN}"},
                    "actions": {
                        "find": {
                            "method": "GET",
                            "path": "/orders/{order_id}",
                        }
                    },
                }
            }
        }
    )

    request = SystemClient(registry).prepare_request(
        "orders",
        "find",
        {"order_id": "123", "include": "items"},
    )

    assert request.method == "GET"
    assert request.url == "https://orders.example.com/orders/123"
    assert request.headers == {"Authorization": "Bearer secret-token"}
    assert request.params == {"include": "items"}
    assert request.json_body is None


def test_prepare_post_request_merges_configured_body_and_payload() -> None:
    registry = SystemRegistry.from_dict(
        {
            "systems": {
                "workers": {
                    "base_url": "https://workers.example.com",
                    "actions": {
                        "restart": {
                            "method": "POST",
                            "path": "/restart",
                            "body": {"worker": "default"},
                        }
                    },
                }
            }
        }
    )

    request = SystemClient(registry).prepare_request(
        "workers",
        "restart",
        {"worker": "orders", "reason": "manual"},
    )

    assert request.method == "POST"
    assert request.url == "https://workers.example.com/restart"
    assert request.params is None
    assert request.json_body == {"worker": "orders", "reason": "manual"}


def test_rpg_system_config_parses_link_and_sheet_action() -> None:
    registry = SystemRegistry.from_dict(
        {
            "systems": {
                "aephirum": {
                    "display_name": "Aephirum",
                    "description": "Sistema principal",
                    "link": "https://aephirum.example.com",
                    "base_url": "https://api.aephirum.example.com",
                    "sheet": {
                        "action": "character-sheet",
                        "id_payload_key": "character_id",
                    },
                    "actions": {
                        "character-sheet": {
                            "method": "GET",
                            "path": "/characters/{character_id}",
                        }
                    },
                }
            }
        }
    )

    system = registry.get_system("aephirum")

    assert system.display_name == "Aephirum"
    assert system.link == "https://aephirum.example.com"
    assert system.sheet is not None
    assert system.sheet.action == "character-sheet"
    assert system.sheet.id_payload_key == "character_id"


def test_sheet_action_must_exist() -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        SystemRegistry.from_dict(
            {
                "systems": {
                    "aephirum": {
                        "base_url": "https://api.aephirum.example.com",
                        "sheet": {"action": "missing"},
                        "actions": {},
                    }
                }
            }
        )


def test_missing_path_payload_raises_config_error() -> None:
    registry = SystemRegistry.from_dict(
        {
            "systems": {
                "orders": {
                    "base_url": "https://orders.example.com",
                    "actions": {
                        "find": {
                            "method": "GET",
                            "path": "/orders/{order_id}",
                        }
                    },
                }
            }
        }
    )

    with pytest.raises(ConfigError, match="order_id"):
        SystemClient(registry).prepare_request("orders", "find")


def test_missing_environment_variable_raises_config_error() -> None:
    with pytest.raises(ConfigError, match="MISSING_TOKEN"):
        SystemRegistry.from_dict(
            {
                "systems": {
                    "orders": {
                        "base_url": "https://orders.example.com",
                        "headers": {"Authorization": "Bearer ${MISSING_TOKEN}"},
                        "actions": {},
                    }
                }
            }
        )
