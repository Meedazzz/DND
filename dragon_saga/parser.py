from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import ABILITIES, Action, Combatant, Resource, uid


@dataclass
class ParseResult:
    combatant: Combatant
    found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


ABILITY_ALIASES = {
    "str": ("str", "сил", "сила"),
    "dex": ("dex", "лов", "ловкость"),
    "con": ("con", "тел", "выносливость"),
    "int": ("int", "инт", "интеллект"),
    "wis": ("wis", "мдр", "мудрость"),
    "cha": ("cha", "хар", "харизма"),
}


def _first(patterns: list[str], text: str, flags: int = re.I | re.M) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match
    return None


def _integer(match: re.Match[str] | None, group: int = 1) -> int | None:
    if not match:
        return None
    try:
        return int(match.group(group))
    except (TypeError, ValueError):
        return None


def parse_stat_block(source: str, side: str = "enemy") -> ParseResult:
    """Parse only explicit values. The original source is preserved byte-for-byte as text."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Вставьте текст статблока")

    lines = [line for line in source.splitlines() if line.strip()]
    name = lines[0].strip()[:120]
    result = ParseResult(Combatant(name=name, side=side, source_text=source))
    combatant = result.combatant

    ac = _integer(_first([r"(?:^|\n)\s*(?:КД|Класс\s+Доспеха|Armor\s+Class|AC)\s*[:—-]?\s*(\d+)", r"\bAC\s+(\d+)"], source))
    hp = _integer(_first([r"(?:^|\n)\s*(?:ОЗ|Хиты|Hit\s+Points|HP)\s*[:—-]?\s*(\d+)", r"\bHP\s+(\d+)"], source))
    speed = _integer(_first([r"(?:Скорость|Speed)\s*[:—-]?\s*(\d+)\s*(?:фт|фут|ft)?"], source))
    level = _integer(_first([r"(?:Уровень|Level)\s*[:—-]?\s*(\d+)"], source))
    proficiency = _integer(_first([r"(?:Бонус\s+мастерства|Proficiency\s+Bonus)\s*[:—-]?\s*\+?(\d+)"], source))
    initiative = _integer(_first([r"(?:Инициатива|Initiative)\s*[:—-]?\s*([+-]?\d+)"], source))

    explicit = (("КД", ac), ("ОЗ", hp), ("скорость", speed), ("уровень", level), ("мастерство", proficiency), ("инициатива", initiative))
    for label, value in explicit:
        if value is not None:
            result.found.append(label)
    if ac is not None:
        combatant.armor_class = ac
    if hp is not None:
        combatant.hp = combatant.max_hp = max(1, hp)
    if speed is not None:
        combatant.speed = speed
    if level is not None:
        combatant.level = level
    if proficiency is not None:
        combatant.proficiency = proficiency
    if initiative is not None:
        combatant.initiative_bonus = initiative

    for ability in ABILITIES:
        aliases = "|".join(re.escape(x) for x in ABILITY_ALIASES[ability])
        match = _first([rf"\b(?:{aliases})\b\s*[:—-]?\s*(\d{{1,2}})"], source)
        score = _integer(match)
        if score is not None:
            combatant.stats[ability] = score
            result.found.append(ability.upper())

    class_match = _first([r"(?:Класс|Class)\s*[:—-]\s*([^\n]+)"], source)
    race_match = _first([r"(?:Раса|Race|Вид|Species)\s*[:—-]\s*([^\n]+)"], source)
    if class_match:
        combatant.class_name = class_match.group(1).strip()[:100]
        result.found.append("класс")
    if race_match:
        combatant.race = race_match.group(1).strip()[:100]
        result.found.append("раса/вид")

    # A resource is accepted only when the line explicitly contains current/maximum.
    resource_by_line: dict[int, Resource] = {}
    for index, line in enumerate(source.splitlines()):
        match = re.search(r"(?P<label>[^:;.]{2,80}?)\s*(?:[:—-]|\()?\s*(?P<cur>\d+)\s*/\s*(?P<max>\d+)\)?", line)
        if not match or re.search(r"(?:ОЗ|HP|Hit\s+Points|Кость|Hit\s+Dice)", line, re.I):
            continue
        current, maximum = int(match.group("cur")), int(match.group("max"))
        if maximum <= 0 or current > maximum:
            continue
        label = match.group("label").strip(" -–—:()") or "Ресурс"
        recovery = "short" if re.search(r"коротк|short", line, re.I) else "long"
        resource = Resource(name=label[:80], current=current, maximum=maximum, recovery=recovery)
        combatant.resources.append(resource)
        resource_by_line[index] = resource
        result.found.append(f"ресурс {label}")

    for index, raw_line in enumerate(source.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        attack_match = re.search(r"([+-]\d+)\s*(?:к\s+атаке|to\s+hit)", line, re.I)
        save_match = re.search(r"(?:Сл|DC)\s*(\d+)\s*(?:([СЛТВИМХ]{3}|STR|DEX|CON|INT|WIS|CHA))?", line, re.I)
        damage_match = re.search(r"(?<!\w)(\d+d\d+(?:\s*[+-]\s*\d+)?)", line, re.I)
        if not (attack_match or save_match) or not damage_match:
            continue
        prefix = re.split(r"[.:—]", line, maxsplit=1)[0].strip()
        action_name = prefix[:80] if prefix and len(prefix) >= 2 else "Действие"
        range_match = re.search(r"(?:дистанция|range|reach|досягаемость)\s*(\d+)\s*(?:фт|ft|фут)", line, re.I)
        range_ft = int(range_match.group(1)) if range_match else 5
        action = Action(name=action_name, damage=damage_match.group(1).replace(" ", ""), range_ft=range_ft, description=raw_line)
        if attack_match:
            action.kind = "attack"
            action.attack_bonus = int(attack_match.group(1))
        else:
            action.kind = "save"
            action.save_dc = int(save_match.group(1))
            alias = (save_match.group(2) or "dex").lower()
            reverse = {item: key for key, names in ABILITY_ALIASES.items() for item in names}
            action.save_ability = reverse.get(alias, alias if alias in ABILITIES else "dex")
            action.half_on_save = bool(re.search(r"половин|half(?: as much| damage)?", raw_line, re.I))
        if index in resource_by_line:
            action.resource_id = resource_by_line[index].id
        combatant.actions.append(action)
        result.found.append(f"действие {action_name}")

    if not combatant.actions:
        result.warnings.append("Действия не найдены: добавьте их вручную, исходный текст не изменён.")
    if ac is None:
        result.warnings.append("КД не указана; использовано безопасное значение схемы 10.")
    if hp is None:
        result.warnings.append("ОЗ не указаны; использовано безопасное значение схемы 10.")
    if speed is None:
        result.warnings.append("Скорость не указана; использовано безопасное значение схемы 30 фт.")
    combatant.audit = [f"Найдено: {', '.join(result.found)}" if result.found else "Явные поля не найдены.", *result.warnings]
    return result
