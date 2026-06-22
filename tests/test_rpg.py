from __future__ import annotations

from bot.rpg import CharacterSheetStore, summarize_sheet_result
from bot.systems import ActionResult


def test_character_sheet_store_upserts_and_updates_sync_result(tmp_path) -> None:
    store = CharacterSheetStore(tmp_path / "character_sheets.json")

    binding = store.upsert_binding(
        discord_user_id=123,
        system_name="aephirum",
        character_id="abc",
        alias="Arvand",
    )
    updated = store.update_sync_result(
        binding,
        status=200,
        snapshot="Nome: Arvand\nNivel: 5",
        error=None,
    )

    bindings = store.list_for_user(123)

    assert len(bindings) == 1
    assert bindings[0].alias == "Arvand"
    assert bindings[0].last_status == 200
    assert bindings[0].snapshot == "Nome: Arvand\nNivel: 5"
    assert updated.last_synced_at is not None


def test_character_sheet_store_updates_existing_alias(tmp_path) -> None:
    store = CharacterSheetStore(tmp_path / "character_sheets.json")

    store.upsert_binding(123, "aephirum", "abc", "Arvand")
    store.upsert_binding(123, "aephirum", "abc", "Novo Nome")

    bindings = store.list_for_user(123)

    assert len(bindings) == 1
    assert bindings[0].alias == "Novo Nome"


def test_summarize_sheet_result_prefers_known_character_fields() -> None:
    result = ActionResult(
        status=200,
        ok=True,
        content_type="application/json",
        body='{"name":"Arvand","level":5,"class":"Guardiao","updated_at":"2026-06-22"}',
    )

    summary = summarize_sheet_result(result)

    assert "Nome: Arvand" in summary
    assert "Nivel: 5" in summary
    assert "Classe: Guardiao" in summary
    assert "Atualizada no sistema: 2026-06-22" in summary
