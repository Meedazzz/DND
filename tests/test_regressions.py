import pytest

from dragon_saga.models import Action, Campaign, Combatant, Resource
from dragon_saga.rules import BattleEngine, RuleError


class FixedDice:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self, low, high):
        return max(low, min(high, next(self.values)))


def active_duel():
    hero = Combatant(
        name="Герой", side="hero", armor_class=15, hp=24, max_hp=24,
        actions=[Action(name="Меч", attack_bonus=6, damage="1d8+3")],
    )
    enemy = Combatant(
        name="Враг", side="enemy", armor_class=13, hp=20, max_hp=20,
        actions=[Action(name="Когти", attack_bonus=5, damage="1d6+2")],
    )
    campaign = Campaign(characters=[hero, enemy])
    campaign.battle.positions = {hero.id: "A1", enemy.id: "A2"}
    campaign.battle.active = True
    campaign.battle.round_number = 1
    campaign.battle.initiative = [{"id": hero.id, "value": 20}, {"id": enemy.id, "value": 10}]
    campaign.battle.movement_left[hero.id] = 30
    campaign.battle.turn_start_zone[hero.id] = "A1"
    campaign.battle.flags[hero.id] = {"action": True, "bonus": True, "reaction": True}
    campaign.battle.flags[enemy.id] = {"reaction": True}
    return campaign, hero, enemy


def test_disengage_spends_action_and_prevents_opportunity_attack():
    campaign, hero, enemy = active_duel()
    engine = BattleEngine(campaign, FixedDice([20, 6]))
    engine.move(hero.id, "T1", "disengage")
    assert campaign.battle.positions[hero.id] == "T1"
    assert hero.hp == hero.max_hp
    assert campaign.battle.flags[hero.id]["action"] is False
    assert campaign.battle.flags[enemy.id]["reaction"] is True
    with pytest.raises(RuleError, match="потрачено"):
        engine.resolve_action(hero.id, enemy.id, hero.actions[0].id)


def test_boss_telegraph_spends_action_and_investigation_reveals_counter():
    campaign, hero, boss = active_duel()
    boss.is_boss = True
    campaign.battle.turn_index = 1
    campaign.battle.flags[boss.id]["action"] = True
    engine = BattleEngine(campaign, FixedDice([19]))
    engine.telegraph(boss.id, "Обвал", 14, "Уйти в тыл")
    assert campaign.battle.flags[boss.id]["action"] is False
    with pytest.raises(RuleError, match="потрачено"):
        engine.telegraph(boss.id, "Ещё удар", 10, "Отойти")
    campaign.battle.turn_index = 0
    result = engine.investigate_telegraph(hero.id, boss.id, "wis")
    assert result.hit is True
    assert "Уйти в тыл" in result.detail


def test_rear_cover_adds_ac_and_disadvantage_to_ranged_attack():
    protected = Combatant(name="Стрелок", side="hero", armor_class=10, hp=20, max_hp=20)
    guard = Combatant(name="Страж", side="hero", hp=20, max_hp=20)
    enemy = Combatant(name="Колдун", side="enemy", actions=[Action(name="Луч", attack_bonus=5, damage="1d6", range_ft=60)])
    campaign = Campaign(characters=[protected, guard, enemy])
    campaign.battle.positions = {protected.id: "T1", guard.id: "A1", enemy.id: "T2"}
    result = BattleEngine(campaign, FixedDice([18, 5])).resolve_action(enemy.id, protected.id, enemy.actions[0].id)
    assert result.hit is False
    assert "18/5" in result.detail
    assert "КД 12" in result.detail


def test_save_action_can_deal_half_damage_on_success():
    caster = Combatant(name="Маг", side="hero", actions=[Action(name="Пламя", kind="save", damage="2d6", save_ability="dex", save_dc=14, half_on_save=True, range_ft=60)])
    target = Combatant(name="Цель", side="enemy", hp=30, max_hp=30, stats={"str": 10, "dex": 20, "con": 10, "int": 10, "wis": 10, "cha": 10})
    campaign = Campaign(characters=[caster, target]); campaign.battle.positions = {caster.id: "T1", target.id: "T2"}
    result = BattleEngine(campaign, FixedDice([20, 6, 4])).resolve_action(caster.id, target.id, caster.actions[0].id)
    assert result.hit is False
    assert result.damage == 5
    assert target.hp == 25


def test_end_combat_clears_turn_state_for_rest():
    campaign, hero, _ = active_duel()
    engine = BattleEngine(campaign); engine.end_combat()
    assert campaign.battle.active is False and campaign.battle.initiative == []
    assert campaign.battle.movement_left == {} and campaign.battle.turn_start_zone == {}
    assert engine.rest(hero.id, "short") == 0


def test_rest_restores_resources_hp_and_hit_dice_outside_combat():
    resource = Resource(name="Вдохновение", current=0, maximum=2, recovery="short")
    hero = Combatant(name="Герой", hp=5, max_hp=20, hit_die=8, hit_dice_current=1, hit_dice_max=3, resources=[resource])
    campaign = Campaign(characters=[hero]); campaign.battle.positions = {hero.id: "T1"}
    healed = BattleEngine(campaign, FixedDice([6])).rest(hero.id, "short", 1)
    assert healed == 6 and hero.hp == 11 and hero.hit_dice_current == 0
    assert resource.current == 2
    BattleEngine(campaign).rest(hero.id, "long")
    assert hero.hp == hero.max_hp
    assert hero.hit_dice_current == 1
