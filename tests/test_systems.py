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
