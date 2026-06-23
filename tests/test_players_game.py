from __future__ import annotations

import random

import pytest

from bot.game import DiceError, roll_dice
from bot.players import PlayerStore


def test_player_store_registers_and_lists_players(tmp_path) -> None:
    store = PlayerStore(tmp_path / "players.json")

    profile = store.register(123, "Arvand", "Aephirum")
    players = store.list_all()

    assert profile.display_name == "Arvand"
    assert profile.preferred_system == "Aephirum"
    assert profile.registered_at is not None
    assert len(players) == 1
    assert store.count() == 1


def test_player_store_updates_existing_registration(tmp_path) -> None:
    store = PlayerStore(tmp_path / "players.json")

    store.register(123, "Arvand", "Aephirum")
    updated = store.register(123, "Arvand Atualizado", "Segundo Sistema")

    assert updated.display_name == "Arvand Atualizado"
    assert updated.preferred_system == "Segundo Sistema"
    assert store.count() == 1


def test_roll_dice_returns_expected_total() -> None:
    rng = random.Random(0)
    result = roll_dice("2d6", rng=rng)

    assert result.expression == "2d6"
    assert len(result.rolls) == 2
    assert result.total == sum(result.rolls)


def test_roll_dice_rejects_invalid_expression() -> None:
    with pytest.raises(DiceError, match="Formato invalido"):
        roll_dice("d20")
