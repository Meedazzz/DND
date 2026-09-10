"""Встроенный бестиарий: целостность записей и создание экземпляров."""

import pytest

from dragon_saga import bestiary


def test_catalog_is_complete_and_unique():
    entries = bestiary.entries()
    assert len(entries) == 16
    ids = [entry.id for entry in entries]
    assert len(set(ids)) == len(ids)
    ranks = {entry.rank for entry in entries}
    assert ranks == {"mob", "elite", "boss"}
    for entry in entries:
        assert bestiary.entry(entry.id) is entry


def test_every_entry_builds_playable_combatant():
    for entry in bestiary.entries():
        creature = bestiary.create(entry.id)
        other = bestiary.create(entry.id)
        assert creature.id != other.id, "экземпляры должны быть независимыми"
        assert creature.side == "enemy"
        assert creature.max_hp > 0 and creature.hp == creature.max_hp
        assert creature.armor_class > 0
        assert creature.actions, f"у {entry.id} нет действий"
        assert {a.section for a in creature.actions} <= {"actions", "bonus", "reactions", "legendary"}
        assert creature.challenge_rating == entry.cr
        assert creature.source_text, "исходный текст обязателен"
        assert creature.audit, "аудит бестиария обязателен"
        assert creature.rank == entry.rank


def test_bosses_carry_boss_flags_and_resources():
    for entry in bestiary.entries():
        creature = bestiary.create(entry.id)
        if entry.rank == "boss":
            assert creature.is_boss
            assert creature.legendary_actions, "у босса должны быть легендарные действия"
            assert any(r.name == "Легендарное сопротивление" for r in creature.resources)
        else:
            assert not creature.is_boss


def test_numbering_for_groups():
    first = bestiary.create("goblin", number=1)
    second = bestiary.create("goblin", number=2)
    third = bestiary.create("goblin", number=3)
    assert first.name == "Гоблин-застрельщик"
    assert second.name == "Гоблин-застрельщик II"
    assert third.name == "Гоблин-застрельщик III"


def test_action_resources_are_linked():
    cultist = bestiary.create("cultist")
    burst = next(a for a in cultist.actions if a.name == "Огненная вспышка")
    assert burst.resource_id
    assert any(r.id == burst.resource_id for r in cultist.resources)


def test_preview_html_mentions_identity():
    html = bestiary.preview_html("ash_wyrm")
    assert "Древний змей Золы" in html
    assert "CR 8" in html
    assert "БОСС" in html


def test_unknown_entry_raises():
    with pytest.raises(KeyError):
        bestiary.create("tarrasque_de_luxe")
    with pytest.raises(KeyError):
        bestiary.entry("tarrasque_de_luxe")
