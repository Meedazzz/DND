from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Callable

from .models import Action, Campaign, Combatant, ZONES


class RuleError(ValueError):
    pass


@dataclass
class Roll:
    formula: str
    total: int
    parts: list[int]

    def __str__(self) -> str:
        return f"{self.formula} = {self.total} [{', '.join(map(str, self.parts))}]"


@dataclass
class ActionResult:
    title: str
    detail: str
    hit: bool | None = None
    damage: int = 0


class BattleEngine:
    def __init__(self, campaign: Campaign, randint: Callable[[int, int], int] | None = None):
        self.campaign = campaign
        self.randint = randint or random.randint

    def roll(self, formula: str) -> Roll:
        clean = formula.lower().replace(" ", "")
        match = re.fullmatch(r"(?:(\d*)d(\d+))?([+-]\d+)?", clean)
        if not match or not match.group(1) and "d" not in clean:
            if re.fullmatch(r"[+-]?\d+", clean):
                return Roll(formula, int(clean), [int(clean)])
            raise RuleError(f"Неверная формула: {formula}")
        count = int(match.group(1) or 1)
        die = int(match.group(2))
        modifier = int(match.group(3) or 0)
        if not 1 <= count <= 100 or not 2 <= die <= 1000:
            raise RuleError("Формула выходит за безопасные пределы")
        parts = [self.randint(1, die) for _ in range(count)]
        return Roll(formula, sum(parts) + modifier, parts)

    def d20(self, modifier: int = 0, advantage: int = 0) -> tuple[int, list[int], int]:
        dice = [self.randint(1, 20)] if advantage == 0 else [self.randint(1, 20), self.randint(1, 20)]
        natural = max(dice) if advantage > 0 else min(dice) if advantage < 0 else dice[0]
        return natural + modifier, dice, natural

    def log(self, text: str) -> None:
        self.campaign.battle.log.append(text)
        self.campaign.battle.log = self.campaign.battle.log[-200:]
        self.campaign.recent_rolls.insert(0, text)
        self.campaign.recent_rolls = self.campaign.recent_rolls[:30]

    def zone(self, actor_id: str) -> str:
        return self.campaign.battle.positions.get(actor_id, "reserve")

    def occupants(self, zone: str) -> list[Combatant]:
        return [x for x in self.campaign.characters if self.zone(x.id) == zone and x.alive]

    def place(self, actor_id: str, zone: str) -> None:
        actor = self._actor(actor_id)
        if zone not in (*ZONES, "reserve"):
            raise RuleError("Неизвестная зона")
        if zone != "reserve":
            expected = {"hero": {"T1", "A1"}, "enemy": {"A2", "T2"}}[actor.side]
            # An enemy may be in a foreign rear only after a validated flank move.
            if zone not in expected and not self.campaign.battle.active:
                raise RuleError("До боя участник ставится только на своей стороне")
            if len(self.campaign.positioned(zone)) >= 2 and self.zone(actor_id) != zone:
                raise RuleError("В ряду уже два участника")
        self.campaign.battle.positions[actor_id] = zone

    def roll_initiative(self) -> None:
        entries = []
        for actor in self.campaign.characters:
            if self.zone(actor.id) == "reserve" or not actor.alive:
                continue
            total, dice, _ = self.d20(actor.initiative_bonus)
            entries.append({"id": actor.id, "value": total, "tie": actor.stats.get("dex", 10)})
            self.log(f"Инициатива · {actor.name}: {dice[0]} {actor.initiative_bonus:+d} = {total}")
        entries.sort(key=lambda x: (x["value"], x["tie"]), reverse=True)
        self.campaign.battle.initiative = entries
        self.campaign.battle.turn_index = 0
        self.campaign.battle.round_number = 1 if entries else 0
        self.campaign.battle.active = bool(entries)
        self._start_turn()

    def end_combat(self) -> None:
        battle = self.campaign.battle
        battle.active = False
        battle.initiative = []
        battle.turn_index = 0
        battle.round_number = 0
        battle.target_id = ""
        battle.flags = {}
        battle.movement_left = {}
        battle.turn_start_zone = {}
        self.log("Бой завершён мастером")

    def active_actor(self) -> Combatant | None:
        battle = self.campaign.battle
        if not battle.active or not battle.initiative:
            return None
        battle.turn_index %= len(battle.initiative)
        return self.campaign.character(battle.initiative[battle.turn_index]["id"])

    def next_turn(self) -> None:
        battle = self.campaign.battle
        if not battle.active or not battle.initiative:
            raise RuleError("Сначала бросьте инициативу")
        previous = self.active_actor()
        if previous:
            self._flag(previous.id)["reaction"] = True
            self._flag(previous.id).pop("charge_vulnerable", None)
        battle.turn_index += 1
        if battle.turn_index >= len(battle.initiative):
            battle.turn_index = 0
            battle.round_number += 1
        self._start_turn()

    def _start_turn(self) -> None:
        actor = self.active_actor()
        if not actor:
            return
        battle = self.campaign.battle
        battle.movement_left[actor.id] = actor.speed
        battle.turn_start_zone[actor.id] = self.zone(actor.id)
        flags = self._flag(actor.id)
        flags["action"] = True
        flags["bonus"] = True
        flags["reaction"] = True
        flags.pop("charge_advantage", None)
        for action in actor.actions:
            key = f"recharge:{action.id}"
            if action.recharge and flags.get(key) is False:
                match = re.search(r"(\d)", action.recharge)
                threshold = int(match.group(1)) if match else 6
                rolled = self.randint(1, 6)
                if rolled >= threshold:
                    flags[key] = True; self.log(f"Перезарядка · {actor.name}: {action.name} ({rolled}) готово")
                else:
                    self.log(f"Перезарядка · {actor.name}: {action.name} ({rolled}) не готово")
        self.log(f"Ход: {actor.name} · раунд {battle.round_number}")

    def move(self, actor_id: str, destination: str, mode: str = "normal") -> None:
        actor = self._actor(actor_id)
        self._require_turn(actor)
        origin = self.zone(actor.id)
        if origin not in ZONES or destination not in ZONES:
            raise RuleError("Перемещение возможно только между рядами поля")
        start = self.campaign.battle.turn_start_zone.get(actor.id, origin)
        movement = self.campaign.battle.movement_left.get(actor.id, actor.speed)

        if mode == "flank":
            own_rear, enemy_rear = ("T1", "T2") if actor.side == "hero" else ("T2", "T1")
            if start != own_rear or origin != own_rear or destination != enemy_rear or actor.speed < 40:
                raise RuleError("Фланг требует начала в своём тылу и скорости 40+ футов")
            if len(self.campaign.positioned(destination)) >= 2:
                raise RuleError("Во вражеском тылу нет места")
            self.campaign.battle.movement_left[actor.id] = 0
            self.campaign.battle.positions[actor.id] = destination
            self.log(f"Фланг · {actor.name}: {origin} → {destination}")
            return

        if abs(ZONES.index(destination) - ZONES.index(origin)) != 1:
            raise RuleError("Обычный шаг возможен только в соседний ряд")
        if movement < 10:
            raise RuleError("Не осталось 10 футов движения")
        if len(self.campaign.positioned(destination)) >= 2:
            raise RuleError("В ряду уже два участника")
        if mode == "charge":
            own_rear, own_front = ("T1", "A1") if actor.side == "hero" else ("T2", "A2")
            if start != own_rear or origin != own_rear or destination != own_front:
                raise RuleError("Натиск начинается в своём тылу и заканчивается в авангарде")
            self._flag(actor.id)["charge_advantage"] = True
            self._flag(actor.id)["charge_vulnerable"] = True
        if mode == "disengage":
            if not self._flag(actor.id).get("action", True):
                raise RuleError("Для Отхода нужно доступное действие")
            self._flag(actor.id)["action"] = False

        if origin in ("A1", "A2") and mode != "disengage":
            self._opportunity_attacks(actor, origin)
            if not actor.alive:
                return
        self.campaign.battle.positions[actor.id] = destination
        self.campaign.battle.movement_left[actor.id] = movement - 10
        self.log(f"Движение · {actor.name}: {origin} → {destination}{' · Натиск' if mode == 'charge' else ''}")

    def _opportunity_attacks(self, mover: Combatant, origin: str) -> None:
        enemy_front = "A2" if origin == "A1" else "A1"
        for enemy in self.occupants(enemy_front):
            if enemy.side == mover.side or not self._flag(enemy.id).get("reaction", True):
                continue
            action = next((x for x in enemy.actions if x.kind == "attack" and x.range_ft <= 10), None)
            if not action:
                continue
            self._flag(enemy.id)["reaction"] = False
            self.resolve_action(enemy.id, mover.id, action.id, consume_action=False, label="Провоцированная атака")

    def resolve_action(self, actor_id: str, target_id: str, action_id: str, consume_action: bool = True, label: str = "Атака") -> ActionResult:
        actor, target = self._actor(actor_id), self._actor(target_id)
        self._require_turn(actor, reactions_allowed=not consume_action)
        action = next((x for x in actor.actions if x.id == action_id), None)
        if not action:
            raise RuleError("Действие не найдено")
        if action.kind in {"attack", "save", "damage"} and actor.side == target.side:
            raise RuleError("Для этого действия выберите противника")
        if action.kind == "heal" and actor.side != target.side:
            raise RuleError("Лечение требует союзную цель")
        economy = "bonus" if action.section == "bonus" else "reaction" if action.section == "reactions" else "action"
        if consume_action and self.campaign.battle.active and not self._flag(actor.id).get(economy, True):
            raise RuleError({"bonus": "Бонусное действие уже потрачено", "reaction": "Реакция уже потрачена"}.get(economy, "Действие уже потрачено"))
        if action.recharge and self._flag(actor.id).get(f"recharge:{action.id}", True) is False:
            raise RuleError(f"«{action.name}» ещё не перезарядилось")
        actor_zone, target_zone = self.zone(actor.id), self.zone(target.id)
        if actor_zone not in ZONES or target_zone not in ZONES:
            raise RuleError("Действие требует цель на сцене")
        zone_gap = abs(ZONES.index(actor_zone) - ZONES.index(target_zone))
        distance = zone_gap * 10
        if (action.range_ft <= 10 and zone_gap > 1) or (action.range_ft > 10 and action.range_ft < distance):
            raise RuleError("Цель вне дистанции")
        resource = next((x for x in actor.resources if x.id == action.resource_id), None)
        if action.resource_id and (not resource or resource.current <= 0):
            raise RuleError("Ресурс исчерпан")

        damage = 0
        hit: bool | None = None
        if action.kind == "attack":
            advantage = 1 if self._flag(actor.id).pop("charge_advantage", False) else 0
            if self._flag(target.id).get("charge_vulnerable"):
                advantage = max(1, advantage)
            target_ac = target.armor_class
            target_rear, target_front = (("T1", "A1") if target.side == "hero" else ("T2", "A2"))
            if self.zone(target.id) == target_rear and any(x.side == target.side for x in self.occupants(target_front)):
                target_ac += 2
                if action.range_ft > 10:
                    advantage -= 1
            total, dice, natural = self.d20(action.attack_bonus or 0, max(-1, min(1, advantage)))
            hit = natural == 20 or (natural != 1 and total >= target_ac)
            roll_text = "/".join(map(str, dice))
            if hit:
                roll = self.roll(action.damage)
                damage = roll.total
                if natural == 20:
                    extra = self.roll(re.sub(r"([+-]\d+)$", "", action.damage)).total
                    damage += extra
                damage = self._apply_damage(target, damage, action.damage_type)
                detail = f"{label} · {actor.name} → {target.name}: {roll_text} {action.attack_bonus or 0:+d} = {total} против КД {target_ac}; урон {damage}"
            else:
                detail = f"{label} · {actor.name} → {target.name}: {roll_text} {action.attack_bonus or 0:+d} = {total} против КД {target_ac}; промах"
        elif action.kind == "save":
            total, dice, _ = self.d20(target.ability_mod(action.save_ability or "dex"))
            hit = total < (action.save_dc or 10)
            rolled_damage = self.roll(action.damage).total
            damage = rolled_damage if hit else rolled_damage // 2 if action.half_on_save else 0
            if damage:
                damage = self._apply_damage(target, damage, action.damage_type)
            detail = f"Спасбросок · {target.name}: {dice[0]} = {total} против Сл {action.save_dc}; {'неудача' if hit else 'успех'}; урон {damage}"
        elif action.kind == "damage":
            rolled_damage = self.roll(action.damage).total
            damage = self._apply_damage(target, rolled_damage, action.damage_type)
            detail = f"Урон · {actor.name} → {target.name}: {action.damage} = {damage}"
        elif action.kind == "heal":
            amount = self.roll(action.damage).total
            before = target.hp
            target.hp = min(target.max_hp, target.hp + amount)
            damage = -(target.hp - before)
            detail = f"Лечение · {actor.name} → {target.name}: +{target.hp - before} ОЗ"
        else:
            detail = f"{actor.name}: {action.name}"

        if consume_action and self.campaign.battle.active:
            self._flag(actor.id)[economy] = False
        if action.recharge:
            self._flag(actor.id)[f"recharge:{action.id}"] = False
        if resource:
            resource.current -= 1
        self.log(detail)
        return ActionResult(action.name, detail, hit, damage)

    def rest(self, actor_id: str, kind: str = "short", spend_hit_dice: int = 0) -> int:
        actor = self._actor(actor_id)
        if self.campaign.battle.active:
            raise RuleError("Отдых доступен после завершения боя")
        if kind not in {"short", "long"}:
            raise RuleError("Неизвестный тип отдыха")
        healed = 0
        if kind == "long":
            healed = actor.max_hp - actor.hp
            actor.hp = actor.max_hp
            spent = max(0, actor.hit_dice_max - actor.hit_dice_current)
            actor.hit_dice_current = min(actor.hit_dice_max, actor.hit_dice_current + max(1, actor.hit_dice_max // 2) if spent else actor.hit_dice_current)
            for resource in actor.resources:
                resource.current = resource.maximum
        else:
            dice_to_spend = min(max(0, spend_hit_dice), actor.hit_dice_current)
            for _ in range(dice_to_spend):
                if actor.hp >= actor.max_hp: break
                amount = max(0, self.roll(f"1d{actor.hit_die}+{actor.ability_mod('con')}").total)
                actual = min(amount, actor.max_hp - actor.hp)
                actor.hp += actual; healed += actual; actor.hit_dice_current -= 1
            for resource in actor.resources:
                if resource.recovery == "short": resource.current = resource.maximum
        self.log(f"{'Долгий' if kind == 'long' else 'Короткий'} отдых · {actor.name}: +{healed} ОЗ")
        return healed

    def tactical_breather(self, actor_id: str) -> int:
        actor = self._actor(actor_id)
        self._require_turn(actor)
        own_rear = "T1" if actor.side == "hero" else "T2"
        if self.zone(actor.id) != own_rear or any(x.side != actor.side for x in self.occupants(own_rear)):
            raise RuleError("Передышка доступна только в безопасном дружественном тылу")
        flags = self._flag(actor.id)
        if not flags.get("bonus", True) or actor.hit_dice_current <= 0:
            raise RuleError("Нет бонусного действия или Костей Хитов")
        heal = max(0, self.roll(f"1d{actor.hit_die}+{actor.ability_mod('con')}").total)
        actual = min(heal, actor.max_hp - actor.hp)
        actor.hp += actual
        actor.hit_dice_current -= 1
        flags["bonus"] = False
        self.log(f"Тактическая передышка · {actor.name}: +{actual} ОЗ")
        return actual

    def telegraph(self, boss_id: str, action_name: str, dc: int, counter: str) -> None:
        boss = self._actor(boss_id)
        if not boss.is_boss:
            raise RuleError("Подготовку показывает только босс")
        self._require_turn(boss)
        if not self._flag(boss.id).get("action", True):
            raise RuleError("Действие босса уже потрачено")
        self._flag(boss.id)["action"] = False
        boss.telegraph, boss.telegraph_dc, boss.telegraph_counter = action_name, max(5, dc), counter
        self.log(f"Подготовка босса · {boss.name}: {action_name} · Сл {boss.telegraph_dc}")

    def investigate_telegraph(self, actor_id: str, boss_id: str, ability: str = "wis") -> ActionResult:
        actor, boss = self._actor(actor_id), self._actor(boss_id)
        if not boss.telegraph:
            raise RuleError("Босс не готовит открытое действие")
        total, dice, _ = self.d20(actor.ability_mod(ability))
        success = total >= boss.telegraph_dc
        detail = f"Анализ · {actor.name}: {dice[0]} = {total} против Сл {boss.telegraph_dc}. " + (f"Контрмера: {boss.telegraph_counter or 'не раскрыта'}" if success else "Контрмера не раскрыта")
        self.log(detail)
        return ActionResult("Анализ подготовки", detail, success)

    def _apply_damage(self, target: Combatant, damage: int, damage_type: str = "") -> int:
        final = max(0, damage)
        kind = damage_type.strip().lower()
        if kind:
            immune = any(kind in entry.lower() for entry in target.immunities)
            resistant = any(kind in entry.lower() for entry in target.resistances)
            vulnerable = any(kind in entry.lower() for entry in target.vulnerabilities)
            if immune:
                final = 0
            elif resistant and not vulnerable:
                final //= 2
            elif vulnerable and not resistant:
                final *= 2
        absorbed = min(target.temp_hp, final)
        target.temp_hp -= absorbed
        target.hp = max(0, target.hp - max(0, final - absorbed))
        if target.hp == 0 and "Без сознания" not in target.conditions:
            target.conditions.append("Без сознания")
        return final

    def _flag(self, actor_id: str) -> dict:
        return self.campaign.battle.flags.setdefault(actor_id, {})

    def _actor(self, actor_id: str) -> Combatant:
        actor = self.campaign.character(actor_id)
        if not actor:
            raise RuleError("Участник не найден")
        return actor

    def _require_turn(self, actor: Combatant, reactions_allowed: bool = False) -> None:
        if not self.campaign.battle.active:
            return
        active = self.active_actor()
        if not reactions_allowed and (not active or active.id != actor.id):
            raise RuleError("Сейчас ход другого участника")
