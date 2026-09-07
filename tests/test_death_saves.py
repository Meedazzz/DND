"""Спасброски от смерти в движке правил."""

import pytest

from dragon_saga.models import Action, Campaign, Combatant
from dragon_saga.rules import BattleEngine, RuleError


def _campaign_with_dying_hero() -> tuple[Campaign, Combatant]:
    campaign = Campaign()
    hero = Combatant(
        name="Умирающий герой", side="hero", rank="hero",
        hp=0, max_hp=30, armor_class=15,
        conditions=["Без сознания"],
        actions=[Action(name="Удар", attack_bonus=5, damage="1d8+3")],
    )
    campaign.characters.append(hero)
    campaign.battle.positions[hero.id] = "A1"
    return campaign, hero


def _engine(campaign: Campaign, roll: int) -> BattleEngine:
    return BattleEngine(campaign, randint=lambda _low, _high: roll)


def test_successes_accumulate_and_stabilize():
    campaign, hero = _campaign_with_dying_hero()
    engine = _engine(campaign, 12)
    for expected in (1, 2, 0):  # третий спасбросок стабилизирует и сбрасывает счётчик
        result = engine.death_save(hero.id)
        assert "Спасбросок от смерти" in result.detail
        assert engine.death_status(hero.id)[0] == expected
    assert "Стабилизирован" in hero.conditions
    assert hero.hp == 0
    with pytest.raises(RuleError):
        engine.death_save(hero.id)  # исход решён


def test_natural_twenty_revives_with_one_hp():
    campaign, hero = _campaign_with_dying_hero()
    engine = _engine(campaign, 20)
    result = engine.death_save(hero.id)
    assert hero.hp == 1
    assert "Без сознания" not in hero.conditions
    assert engine.death_status(hero.id) == (0, 0)
    assert result.hit is True
    with pytest.raises(RuleError):
        engine.death_save(hero.id)  # героя уже подняли


def test_natural_one_counts_double_and_three_failures_kill():
    campaign, hero = _campaign_with_dying_hero()
    engine = _engine(campaign, 1)
    engine.death_save(hero.id)  # нат. 1 → два провала
    assert engine.death_status(hero.id) == (0, 2)
    engine2 = _engine(campaign, 5)
    engine2.death_save(hero.id)  # третий провал
    assert "Мёртв" in hero.conditions
    assert "Без сознания" not in hero.conditions
    with pytest.raises(RuleError):
        engine2.death_save(hero.id)


def test_death_save_requires_zero_hp():
    campaign, hero = _campaign_with_dying_hero()
    hero.hp = 5
    with pytest.raises(RuleError):
        _engine(campaign, 12).death_save(hero.id)


def test_healing_from_zero_clears_death_marks():
    campaign, hero = _campaign_with_dying_hero()
    cleric = Combatant(
        name="Жрица", side="hero", rank="hero",
        actions=[Action(name="Исцеление", kind="heal", damage="2d8")],
    )
    campaign.characters.append(cleric)
    campaign.battle.positions[cleric.id] = "T1"
    engine = _engine(campaign, 4)  # 2d8 → 8 лечения, но спасброски тоже пойдут 4
    engine.death_save(hero.id)
    assert engine.death_status(hero.id) == (0, 1)  # 4 < 10 — провал
    heal = cleric.actions[0]
    engine.resolve_action(cleric.id, hero.id, heal.id)
    assert hero.hp == 8
    assert "Без сознания" not in hero.conditions
    assert engine.death_status(hero.id) == (0, 0)


def test_death_saves_do_not_touch_other_combatants():
    campaign, hero = _campaign_with_dying_hero()
    bystander = Combatant(name="Свидетель", side="enemy", rank="mob", hp=9, max_hp=9)
    campaign.characters.append(bystander)
    campaign.battle.positions[bystander.id] = "A2"
    _engine(campaign, 12).death_save(hero.id)
    assert bystander.hp == 9
