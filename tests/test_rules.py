import pytest

from dragon_saga.models import Action, Campaign, Combatant, starter_campaign
from dragon_saga.rules import BattleEngine, RuleError


class FixedDice:
    def __init__(self, values): self.values = iter(values)
    def __call__(self, low, high): return max(low, min(high, next(self.values)))


def duel():
    hero = Combatant(name="Герой", side="hero", armor_class=16, hp=30, max_hp=30, speed=40, actions=[Action(name="Меч", attack_bonus=7, damage="1d8+4", range_ft=5)])
    enemy = Combatant(name="Враг", side="enemy", armor_class=14, hp=30, max_hp=30, actions=[Action(name="Коготь", attack_bonus=5, damage="1d6+3", range_ft=5)])
    campaign = Campaign(characters=[hero, enemy])
    campaign.battle.positions = {hero.id: "A1", enemy.id: "A2"}
    return campaign, hero, enemy


def test_starter_scene_has_five_heroes_four_staged_and_capacity_two():
    campaign = starter_campaign()
    assert len(campaign.characters) == 5
    assert len(campaign.positioned("T1")) == 2
    assert len(campaign.positioned("A1")) == 2
    assert sum(1 for zone in campaign.battle.positions.values() if zone == "reserve") == 1
    extra = Combatant(name="Лишний")
    campaign.characters.append(extra)
    with pytest.raises(RuleError):
        BattleEngine(campaign).place(extra.id, "T1")


def test_adjacent_melee_hit_and_damage_are_one_click():
    campaign, hero, enemy = duel()
    engine = BattleEngine(campaign, FixedDice([16, 5]))
    result = engine.resolve_action(hero.id, enemy.id, hero.actions[0].id)
    assert result.hit is True
    assert result.damage == 9
    assert enemy.hp == 21
    assert "ПОПАДАНИЕ" not in result.detail  # UI owns the banner; engine owns exact mechanics.


def test_imported_direct_damage_applies_damage_defenses_and_recharge_state():
    action = Action(name="Пламя", kind="damage", damage="2d6", damage_type="fire", recharge="5-6", range_ft=30)
    caster = Combatant(name="Маг", side="hero", actions=[action])
    target = Combatant(name="Саламандра", side="enemy", hp=30, max_hp=30, resistances=["fire"])
    campaign = Campaign(characters=[caster, target]); campaign.battle.positions = {caster.id: "A1", target.id: "A2"}
    engine = BattleEngine(campaign, FixedDice([5, 4]))
    result = engine.resolve_action(caster.id, target.id, action.id)
    assert result.damage == 4 and target.hp == 26
    assert campaign.battle.flags[caster.id][f"recharge:{action.id}"] is False
    with pytest.raises(RuleError, match="перезаряд"):
        engine.resolve_action(caster.id, target.id, action.id)

    campaign.battle.active = True; campaign.battle.initiative = [{"id": caster.id, "value": 20}]
    engine = BattleEngine(campaign, FixedDice([5])); engine._start_turn()
    assert campaign.battle.flags[caster.id][f"recharge:{action.id}"] is True


def test_opportunity_attack_on_leaving_vanguard():
    campaign, hero, enemy = duel()
    campaign.battle.active = True
    campaign.battle.round_number = 1
    campaign.battle.initiative = [{"id": hero.id, "value": 20}, {"id": enemy.id, "value": 10}]
    campaign.battle.movement_left[hero.id] = 30
    campaign.battle.turn_start_zone[hero.id] = "A1"
    engine = BattleEngine(campaign, FixedDice([18, 4]))
    engine.move(hero.id, "T1")
    assert campaign.battle.positions[hero.id] == "T1"
    assert hero.hp == 23
    assert any("Провоцированная атака" in line for line in campaign.battle.log)


def test_charge_flank_breather_and_rear_cover():
    campaign, hero, enemy = duel()
    campaign.battle.positions[hero.id] = "T1"
    campaign.battle.active = True
    campaign.battle.round_number = 1
    campaign.battle.initiative = [{"id": hero.id, "value": 20}, {"id": enemy.id, "value": 10}]
    campaign.battle.movement_left[hero.id] = 40
    campaign.battle.turn_start_zone[hero.id] = "T1"
    engine = BattleEngine(campaign, FixedDice([15, 4]))
    engine.move(hero.id, "A1", "charge")
    assert campaign.battle.flags[hero.id]["charge_advantage"] is True

    campaign2, hero2, enemy2 = duel()
    campaign2.battle.positions[hero2.id] = "T1"
    campaign2.battle.active = True
    campaign2.battle.initiative = [{"id": hero2.id, "value": 20}]
    campaign2.battle.movement_left[hero2.id] = 40
    campaign2.battle.turn_start_zone[hero2.id] = "T1"
    BattleEngine(campaign2).move(hero2.id, "T2", "flank")
    assert campaign2.battle.positions[hero2.id] == "T2"

    campaign3 = Campaign(characters=[Combatant(name="Раненый", hp=4, max_hp=20, hit_dice_current=1)])
    wounded = campaign3.characters[0]
    campaign3.battle.positions[wounded.id] = "T1"
    healed = BattleEngine(campaign3, FixedDice([5])).tactical_breather(wounded.id)
    assert healed > 0 and wounded.hit_dice_current == 0
