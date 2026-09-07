"""Портретные заглушки и реестр ресурсов."""

from dragon_saga import assets
from dragon_saga.models import Combatant


def test_placeholder_key_prefers_boss_then_rank():
    assert assets.placeholder_key("enemy", "mob") == "enemy_mob"
    assert assets.placeholder_key("enemy", "elite") == "enemy_elite"
    assert assets.placeholder_key("enemy", "boss") == "enemy_boss"
    assert assets.placeholder_key("enemy", "mob", is_boss=True) == "enemy_boss"
    assert assets.placeholder_key("hero", "") == "hero_generic"


def test_all_portrait_art_files_exist():
    for key in ("hero_warrior", "hero_ranger", "hero_mage", "hero_bard", "hero_rogue",
                "hero_generic", "enemy_mob", "enemy_elite", "enemy_boss"):
        assert assets.art_available(key), f"нет файла для {key}"
    assert assets.art_available("backdrop_battle")


def test_portrait_archetype_aliases():
    guardian = Combatant(name="Северный страж", side="hero", rank="hero")
    assert assets.portrait_path_for(guardian) == assets.art_path("hero_warrior")
    ranger = Combatant(name="Безымянный", side="hero", class_name="Следопыт", rank="hero")
    assert assets.portrait_path_for(ranger) == assets.art_path("hero_ranger")


def test_portrait_falls_back_to_rank_placeholder():
    mob = Combatant(name="Тварь без имени", side="enemy", rank="mob")
    assert assets.portrait_path_for(mob) == assets.art_path("enemy_mob")
    elite = Combatant(name="Тварь без имени", side="enemy", rank="elite")
    assert assets.portrait_path_for(elite) == assets.art_path("enemy_elite")
    boss = Combatant(name="Тварь без имени", side="enemy", is_boss=True)
    assert assets.portrait_path_for(boss) == assets.art_path("enemy_boss")
    hero = Combatant(name="Неизвестный союзник", side="hero")
    assert assets.portrait_path_for(hero) == assets.art_path("hero_generic")


def test_manifest_has_no_missing_portraits():
    missing = assets.manifest()
    assert not any(key.startswith("hero_") or key.startswith("enemy_") for key in missing)
