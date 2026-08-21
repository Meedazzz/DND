from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import ABILITIES, Action, Combatant, Resource


@dataclass
class ParseResult:
    combatant: Combatant
    found: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


ABILITY_ALIASES = {
    "str": ("STR", "СИЛ", "сила", "strength"),
    "dex": ("DEX", "ЛОВ", "ловкость", "dexterity"),
    "con": ("CON", "ТЕЛ", "телосложение", "выносливость", "constitution"),
    "int": ("INT", "ИНТ", "интеллект", "intelligence"),
    "wis": ("WIS", "МДР", "мудрость", "wisdom"),
    "cha": ("CHA", "ХАР", "харизма", "charisma"),
}

ABILITY_LOOKUP = {
    alias.casefold(): ability
    for ability, aliases in ABILITY_ALIASES.items()
    for alias in aliases
}

SECTION_NAMES = {
    "actions": ("actions", "действия"),
    "bonus": ("bonus actions", "бонусные действия"),
    "reactions": ("reactions", "реакции"),
    "legendary": ("legendary actions", "легендарные действия", "действия логова", "lair actions", "действия босса"),
    "traits": ("traits", "особенности", "черты"),
}

FIELD_LABELS = (
    r"Имя|Name|Класс|Class|Раса|Race|Вид|Species|Тип\s+существа|Creature\s+Type|"
    r"КД|Класс\s+Доспеха|Armor\s+Class|AC|ОЗ|Хиты|Hit\s+Points|HP|Скорость|Speed|"
    r"Инициатива|Initiative|Уровень|Level|Бонус\s+мастерства|Proficiency(?:\s+Bonus)?|"
    r"Спасброски|Saving\s+Throws|Saves|Навыки|Skills|Сопротивления(?:\s+урону)?|Damage\s+Resistances|"
    r"Уязвимости(?:\s+к\s+урону)?|Damage\s+Vulnerabilities|Иммунитеты(?:\s+к\s+урону)?|Damage\s+Immunities|"
    r"Иммунитеты\s+к\s+состояниям|Condition\s+Immunities|Чувства|Senses|Языки|Languages|"
    r"Опасность|ПО|Challenge|CR|Ресурсы|Resources|Использования|Uses"
)

DAMAGE_WORDS = (
    "рубящ", "колющ", "дробящ", "огонь", "огнен", "холод", "кислот", "электр", "молни", "гром",
    "яд", "психичес", "силов", "излучен", "некрот", "slashing", "piercing", "bludgeoning", "fire",
    "cold", "acid", "lightning", "thunder", "poison", "psychic", "force", "radiant", "necrotic",
)


def _first(patterns: list[str], text: str, flags: int = re.I | re.M | re.S) -> re.Match[str] | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match
    return None


def _integer(match: re.Match[str] | None, group: int = 1) -> int | None:
    if not match:
        return None
    try:
        return int(match.group(group).replace("−", "-"))
    except (AttributeError, TypeError, ValueError):
        return None


def _label_value(source: str, labels: str) -> str:
    """Return an explicit text field, including from a single uninterrupted paragraph."""
    pattern = rf"(?:^|\n|(?<=\s))(?:{labels})(?!\w)\s*[:—-]?\s*(.+?)(?=(?:\n|\s+(?:{FIELD_LABELS})(?!\w)\s*[:—-]?)|$)"
    match = re.search(pattern, source, re.I | re.M | re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _split_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;]", value) if item.strip()]


def _ability_from_text(value: str) -> str:
    folded = value.casefold()
    for alias, key in sorted(ABILITY_LOOKUP.items(), key=lambda pair: len(pair[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", folded, re.I):
            return key
    return ""


def _signed_pairs(value: str) -> dict[str, int]:
    pairs: dict[str, int] = {}
    aliases = "|".join(re.escape(alias) for names in ABILITY_ALIASES.values() for alias in names)
    for match in re.finditer(rf"(?P<name>{aliases})\s*(?P<bonus>[+−-]\s*\d+)", value, re.I):
        ability = ABILITY_LOOKUP.get(match.group("name").casefold())
        if ability:
            pairs[ability] = int(match.group("bonus").replace(" ", "").replace("−", "-"))
    return pairs


def _skill_pairs(value: str) -> dict[str, int]:
    pairs: dict[str, int] = {}
    for match in re.finditer(r"([A-Za-zА-Яа-яЁё ()'’.-]{2,40}?)\s*([+−-]\s*\d+)(?=\s*[,;]|$)", value):
        name = match.group(1).strip(" ,;()")
        if name:
            pairs[name] = int(match.group(2).replace(" ", "").replace("−", "-"))
    return pairs


def _standard_identity(lines: list[str], combatant: Combatant, found: list[str]) -> None:
    if len(lines) < 2:
        return
    sizes = "Tiny|Small|Medium|Large|Huge|Gargantuan|Крошечн(?:ый|ая|ое)|Маленьк(?:ий|ая|ое)|Средн(?:ий|яя|ее)|Больш(?:ой|ая|ое)|Огромн(?:ый|ая|ое)|Громадн(?:ый|ая|ое)"
    match = re.match(rf"^({sizes})\s+([^,]+?)(?:,\s*(.+))?$", lines[1].strip(), re.I)
    if not match:
        return
    combatant.creature_size = match.group(1).strip()
    combatant.creature_type = match.group(2).strip()
    combatant.alignment = (match.group(3) or "").strip()
    combatant.race = " ".join(x for x in (combatant.creature_size, combatant.creature_type) if x)
    found.extend(["размер", "тип существа"])
    if combatant.alignment:
        found.append("мировоззрение")


def _find_section_markers(source: str) -> list[tuple[int, int, str]]:
    variants = [(label, section) for section, labels in SECTION_NAMES.items() for label in labels]
    expression = "|".join(re.escape(label) for label, _ in sorted(variants, key=lambda item: len(item[0]), reverse=True))
    markers: list[tuple[int, int, str]] = []
    pattern = rf"(?<!\w)(?P<label>{expression})\s*:?(?=\s|$)"
    for match in re.finditer(pattern, source, re.I | re.M):
        label = match.group("label").casefold()
        section = next(section for raw, section in variants if raw.casefold() == label)
        markers.append((match.start("label"), match.end(), section))
    return markers


def _section_at(position: int, markers: list[tuple[int, int, str]]) -> str:
    section = "traits"
    for marker_position, _, marker_section in markers:
        if marker_position > position:
            break
        section = marker_section
    return section


def _candidate_segments(source: str, markers: list[tuple[int, int, str]]) -> list[tuple[int, str, str, str]]:
    """Find named clauses inside explicit statblock sections, including one plain paragraph."""
    start_pattern = re.compile(
        r"(?:^|\n|[.!?]\s+)(?P<name>[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9'’ -]{1,68}?)"
        r"(?P<uses>\s*\([^()\n]{1,60}\))?\s*[.:—]\s+",
        re.M,
    )
    rejected = {
        "hit", "попадание", "damage", "урон", "effect", "эффект", "target", "цель", "on a failed save",
        "при провале", "при успехе", "armor class", "hit points", "speed", "saving throws", "skills",
        "damage resistances", "damage immunities", "condition immunities", "senses", "languages", "challenge",
        "кд", "оз", "хиты", "скорость", "спасброски", "навыки", "сопротивления", "иммунитеты", "чувства", "языки",
        "имя", "name", "класс", "class", "раса", "race", "вид", "species", "ресурсы", "resources",
    }
    mechanics = re.compile(
        r"\b\d+\s*[dк]\s*\d+|[+−-]\s*\d+\s*(?:to hit|к (?:атаке|попаданию))|"
        r"(?:attack|атака|saving throw|спасбросок|save DC|Сл\s*\d+|DC\s*\d+|recharge|перезарядка|"
        r"healing|лечение|regains?|восстанавливает|makes?\s+\w*\s*attacks?|совершает\s+\w*\s*атак)", re.I,
    )
    results: list[tuple[int, str, str, str]] = []
    action_sections = {"actions", "bonus", "reactions", "legendary"}
    for index, (marker_start, marker_end, section) in enumerate(markers):
        body_end = markers[index + 1][0] if index + 1 < len(markers) else len(source)
        span = source[marker_end:body_end].strip()
        if not span:
            continue
        offset = source.find(span, marker_end, body_end)
        raw_starts = list(start_pattern.finditer(span))
        valid: list[re.Match[str]] = []
        for raw_index, match in enumerate(raw_starts):
            name = re.sub(r"\s+", " ", match.group("name")).strip()
            folded = name.casefold()
            next_start = raw_starts[raw_index + 1].start() if raw_index + 1 < len(raw_starts) else len(span)
            immediate_body = span[match.end():next_start]
            if folded in rejected or len(name.split()) > 9 or re.match(rf"^(?:{FIELD_LABELS})(?!\w)", name, re.I):
                continue
            if folded.startswith(("the target", "the dragon", "each creature", "a creature", "the creature", "цель ", "существо ", "каждое существо")):
                continue
            uses = match.group("uses") or ""
            if mechanics.search(uses + " " + immediate_body) or section == "traits":
                valid.append(match)
        for valid_index, match in enumerate(valid):
            next_start = valid[valid_index + 1].start() if valid_index + 1 < len(valid) else len(span)
            name = re.sub(r"\s+", " ", match.group("name")).strip()
            uses = match.group("uses") or ""
            body = re.sub(r"\s+", " ", uses + " " + span[match.end():next_start]).strip()
            if section in action_sections and mechanics.search(body):
                results.append((offset + match.start("name"), name, body, section))
            elif section == "traits" and body:
                results.append((offset + match.start("name"), name, body, section))
    return results

def _action_from_segment(name: str, body: str, section: str) -> tuple[Action, tuple[int, int, str] | None]:
    attack_match = _first([
        r"(?:Melee|Ranged|Weapon|Spell|Рукопашная|Дальнобойная|Оружейная|Заклинательная)[^.:;]{0,55}(?:Attack|атака)\s*:\s*([+−-]\s*\d+)",
        r"(?:атака(?:\s+заклинанием)?|бросок\s+атаки|attack(?:\s+roll)?)[^\d+−-]{0,35}([+−-]\s*\d+)",
        r"([+−-]\s*\d+)\s*(?:к\s+(?:атаке|попаданию)|to\s+hit)",
    ], body)
    attack_bonus = _integer(attack_match)

    dice = re.search(r"(?<!\w)(\d+\s*[dк]\s*\d+(?:\s*[+−-]\s*\d+)?)", body, re.I)
    damage = dice.group(1).replace(" ", "").replace("к", "d").replace("К", "d").replace("−", "-") if dice else "0"
    healing = bool(re.search(r"лечение|исцел|восстанавливает\s+\d|healing|regains?\s+\d", body, re.I))

    save_dc_match = _first([r"(?:Сл|DC)\s*(\d+)", r"(?:сложност[ьи]|difficulty)\s*(\d+)"], body)
    save_dc = _integer(save_dc_match)
    save_context = ""
    if save_dc_match:
        save_context = body[max(0, save_dc_match.start() - 55):save_dc_match.end() + 70]
    save_match = re.search(r"(?:спасбросок|saving\s+throw|save)", body, re.I)
    save_ability = _ability_from_text(save_context or body) if (save_match or save_dc is not None) else ""

    half_on_save = bool(re.search(r"половин|half(?:\s+as\s+much)?", body, re.I))
    range_match = _first([
        r"(?:дистанция|range)\s*[:—-]?\s*(\d+)",
        r"(?:досягаемость|reach)\s*[:—-]?\s*(\d+)",
    ], body)
    range_ft = _integer(range_match) or (60 if re.search(r"ranged|дальнобойн", body, re.I) else 5)
    damage_type = next((word for word in DAMAGE_WORDS if re.search(word, body, re.I)), "")

    uses: tuple[int, int, str] | None = None
    use_match = re.search(r"\((\d+)\s*/\s*(\d+)(?:\s*[,;]\s*([^)]+))?\)", body)
    per_day = re.search(r"\((\d+)\s*/\s*(?:day|день|сутки)(?:\s+each|\s+кажд\w*)?\)", body, re.I)
    if use_match:
        uses = (int(use_match.group(1)), int(use_match.group(2)), use_match.group(3) or "")
    elif per_day:
        uses = (int(per_day.group(1)), int(per_day.group(1)), "long")

    recharge_match = re.search(r"(?:Recharge|Перезарядка)\s*(\d)(?:\s*[–—-]\s*(\d))?", body, re.I)
    recharge = ""
    if recharge_match:
        recharge = recharge_match.group(1) + (f"-{recharge_match.group(2)}" if recharge_match.group(2) else "")

    if healing:
        kind = "heal"
    elif save_dc is not None or save_match:
        kind = "save"
    elif attack_bonus is not None:
        kind = "attack"
    elif dice:
        kind = "damage"
    else:
        kind = "utility"
    action = Action(
        name=name[:80], kind=kind, attack_bonus=attack_bonus, damage=damage, damage_type=damage_type,
        save_ability=save_ability or "dex" if kind == "save" else "", save_dc=save_dc,
        half_on_save=half_on_save, range_ft=range_ft, section=section, recharge=recharge, description=body,
    )
    return action, uses


def parse_stat_block(source: str, side: str = "enemy") -> ParseResult:
    """Deterministically parse explicit fields while preserving ``source`` character-for-character."""
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Вставьте текст статблока")
    if side not in {"hero", "enemy"}:
        raise ValueError("Неизвестная сторона участника")

    clean = source.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in clean.splitlines() if line.strip()]
    explicit_name = _label_value(clean, r"Имя|Name")
    if explicit_name:
        name = explicit_name[:120]
    else:
        first = lines[0] if lines else "Безымянный"
        # A one-line explicit statblock may begin with the name immediately before its first field.
        first = re.split(rf"\s+(?=(?:{FIELD_LABELS})\s*[:—-])", first, maxsplit=1, flags=re.I)[0]
        name = first.strip("# *")[:120] or "Безымянный"

    combatant = Combatant(name=name, side=side, source_text=source)
    result = ParseResult(combatant)
    if explicit_name or name != "Безымянный":
        result.found.append("имя")
    if not explicit_name:
        result.warnings.append("Имя взято из первой строки — проверьте его в предпросмотре.")

    class_name = _label_value(clean, r"Класс(?!\s+Доспеха)|(?<!Armor\s)Class")
    race = _label_value(clean, r"Раса|Race|Вид|Species")
    creature_type = _label_value(clean, r"Тип\s+существа|Creature\s+Type")
    if class_name:
        combatant.class_name = class_name[:100]
        result.found.append("класс")
    if race:
        combatant.race = race[:120]
        result.found.append("раса/вид")
    if creature_type:
        combatant.creature_type = creature_type[:120]
        combatant.race = combatant.race or creature_type[:120]
        result.found.append("тип существа")
    if not race and not creature_type:
        _standard_identity(lines, combatant, result.found)

    numeric_patterns = {
        "armor_class": [r"(?:^|\n|(?<=\s))(?:КД|Класс\s+Доспеха|Armor\s+Class|AC)\s*[:—-]?\s*(\d+)"],
        "hp": [r"(?:^|\n|(?<=\s))(?:ОЗ|Хиты|Hit\s+Points|HP)\s*[:—-]?\s*(\d+)(?:\s*/\s*(\d+))?"],
        "speed": [r"(?:^|\n|(?<=\s))(?:Скорость|Speed)\s*[:—-]?\s*(\d+)\s*(?:фт|фут|ft)?"],
        "level": [r"(?:^|\n|(?<=\s))(?:Уровень|Level)\s*[:—-]?\s*(\d+)"],
        "proficiency": [r"(?:Бонус\s+мастерства|Proficiency(?:\s+Bonus)?)\s*[:—-]?\s*\+?(\d+)"],
        "initiative_bonus": [r"(?:Инициатива|Initiative)\s*[:—-]?\s*([+−-]?\d+)"],
    }
    labels = {"armor_class": "КД", "hp": "ОЗ", "speed": "скорость", "level": "уровень", "proficiency": "мастерство", "initiative_bonus": "инициатива"}
    hp_match: re.Match[str] | None = None
    for attr, patterns in numeric_patterns.items():
        match = _first(patterns, clean)
        if attr == "hp":
            hp_match = match
        value = _integer(match)
        if value is None:
            continue
        result.found.append(labels[attr])
        if attr == "hp":
            maximum = _integer(match, 2) if match and match.lastindex and match.lastindex >= 2 else None
            combatant.hp = value
            combatant.max_hp = max(1, maximum or value)
        else:
            setattr(combatant, attr, value)

    # Scores written as labels next to values.
    score_count = 0
    for ability, aliases in ABILITY_ALIASES.items():
        alias_expression = "|".join(re.escape(alias) for alias in aliases)
        match = _first([rf"(?<!\w)(?:{alias_expression})(?!\w)\s*[:—-]?\s*(\d{{1,2}})(?!\d)"], clean)
        value = _integer(match)
        if value is not None and 0 <= value <= 40:
            combatant.stats[ability] = value
            result.found.append(ability.upper())
            score_count += 1

    # Common two-row statblock table: STR DEX CON INT WIS CHA / 18 12 16 7 10 8.
    if score_count < 6:
        table = re.search(
            r"(?:STR|СИЛ)\s+(?:DEX|ЛОВ)\s+(?:CON|ТЕЛ)\s+(?:INT|ИНТ)\s+(?:WIS|МДР)\s+(?:CHA|ХАР)"
            r"\s+(\d{1,2})(?:\s*\([+−-]?\d+\))?\s+(\d{1,2})(?:\s*\([+−-]?\d+\))?\s+"
            r"(\d{1,2})(?:\s*\([+−-]?\d+\))?\s+(\d{1,2})(?:\s*\([+−-]?\d+\))?\s+"
            r"(\d{1,2})(?:\s*\([+−-]?\d+\))?\s+(\d{1,2})(?:\s*\([+−-]?\d+\))?",
            clean, re.I,
        )
        if table:
            for ability, value in zip(ABILITIES, table.groups()):
                combatant.stats[ability] = int(value)
                if ability.upper() not in result.found:
                    result.found.append(ability.upper())
            score_count = 6

    saves = _label_value(clean, r"Спасброски|Saving\s+Throws|Saves")
    skills = _label_value(clean, r"Навыки|Skills")
    if saves:
        combatant.saves = _signed_pairs(saves)
        if combatant.saves:
            result.found.append("спасброски")
    if skills:
        combatant.skills = _skill_pairs(skills)
        if combatant.skills:
            result.found.append("навыки")

    list_fields = (
        ("resistances", r"Сопротивления(?:\s+урону)?|Damage\s+Resistances", "сопротивления"),
        ("vulnerabilities", r"Уязвимости(?:\s+к\s+урону)?|Damage\s+Vulnerabilities", "уязвимости"),
        ("immunities", r"Иммунитеты(?!\s+к\s+состояниям)(?:\s+к\s+урону)?|Damage\s+Immunities", "иммунитеты"),
        ("condition_immunities", r"Иммунитеты\s+к\s+состояниям|Condition\s+Immunities", "иммунитеты к состояниям"),
    )
    for attr, pattern, label in list_fields:
        value = _label_value(clean, pattern)
        if value:
            setattr(combatant, attr, _split_list(value))
            result.found.append(label)
    for attr, pattern, label in (
        ("senses", r"Чувства|Senses", "чувства"),
        ("languages", r"Языки|Languages", "языки"),
        ("challenge_rating", r"Опасность|ПО|Challenge|CR", "опасность/CR"),
    ):
        value = _label_value(clean, pattern)
        if value:
            setattr(combatant, attr, value[:240])
            result.found.append(label)

    # Explicit current/maximum resources anywhere in the block.
    resource_spans: list[tuple[int, int, Resource]] = []
    resource_pattern = re.compile(
        r"(?P<label>[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9 '’()_-]{1,70}?)\s*(?:[:—-]|\()?\s*"
        r"(?P<cur>\d+)\s*/\s*(?P<max>\d+)(?:\s*[,;]\s*(?P<recovery>[^)\n.;]{2,40}))?\)?",
        re.I,
    )
    for match in resource_pattern.finditer(clean):
        context = clean[max(0, match.start() - 18):match.end() + 8]
        if re.search(r"(?:ОЗ|HP|Hit\s+Points|Hit\s+Dice|Кость\s+Хитов)", context, re.I):
            continue
        current, maximum = int(match.group("cur")), int(match.group("max"))
        if maximum <= 0 or current > maximum:
            continue
        label = re.split(r"[.!?]\s+|\n", match.group("label"))[-1].strip(" -–—:()")
        if not label:
            label = "Ресурс"
        recovery_text = match.group("recovery") or ""
        recovery = "short" if re.search(r"корот|short", recovery_text, re.I) else "long"
        resource = Resource(name=label[:80], current=current, maximum=maximum, recovery=recovery)
        combatant.resources.append(resource)
        resource_spans.append((match.start(), match.end(), resource))
        result.found.append(f"ресурс {resource.name}")

    markers = _find_section_markers(clean)
    segments = _candidate_segments(clean, markers)
    # Published 5e blocks usually place named traits between Challenge and Actions without a "Traits" heading.
    first_action_marker = next((marker for marker in markers if marker[2] in {"actions", "bonus", "reactions", "legendary"}), None)
    if first_action_marker and not any(marker[2] == "traits" and marker[0] < first_action_marker[0] for marker in markers):
        implicit_markers = [(0, 0, "traits"), first_action_marker]
        implicit_traits = [item for item in _candidate_segments(clean, implicit_markers) if item[3] == "traits"]
        segments = implicit_traits + segments
    action_names: set[tuple[str, str]] = set()
    for position, action_name, body, section in segments:
        if section == "traits":
            trait_text = f"{action_name}. {body}"
            if trait_text not in combatant.traits:
                combatant.traits.append(trait_text)
                result.found.append(f"особенность: {action_name}")
            _, uses = _action_from_segment(action_name, body, section)
            if uses and not any(r.name.casefold() == action_name.casefold() for r in combatant.resources):
                current, maximum, recovery_text = uses
                recovery = "short" if re.search(r"корот|short", recovery_text, re.I) else "long"
                resource = Resource(name=action_name, current=current, maximum=maximum, recovery=recovery)
                combatant.resources.append(resource); result.found.append(f"ресурс {resource.name}")
            continue
        action, uses = _action_from_segment(action_name, body, section)
        key = (action.name.casefold(), action.description.casefold())
        if key in action_names:
            continue
        action_names.add(key)
        if uses:
            current, maximum, recovery_text = uses
            resource = next((r for r in combatant.resources if r.current == current and r.maximum == maximum and r.name.casefold() in action.name.casefold()), None)
            if not resource:
                recovery = "short" if re.search(r"корот|short", recovery_text, re.I) else "long"
                resource = Resource(name=action.name, current=current, maximum=maximum, recovery=recovery)
                combatant.resources.append(resource)
                result.found.append(f"ресурс {resource.name}")
            action.resource_id = resource.id
        combatant.actions.append(action)
        result.found.append(f"{section}: {action.name}")
        full_text = f"{action.name}. {body}"
        if section == "reactions":
            combatant.reactions.append(full_text)
        elif section == "legendary":
            combatant.legendary_actions.append(full_text)

    if any(section == "legendary" for _, _, section in markers):
        combatant.is_boss = True
        result.found.append("легендарные действия / босс")

    # Compact custom format can omit an Actions heading; mechanics on separate lines still become actions.
    if not combatant.actions:
        for raw_line in lines:
            if not re.search(r"\d+\s*[dк]\s*\d+|to hit|к (?:атаке|попаданию)|спасбросок|saving throw", raw_line, re.I):
                continue
            split = re.match(r"^(.{2,80}?)(?:\.|:|—)\s+(.+)$", raw_line)
            if not split:
                continue
            action, uses = _action_from_segment(split.group(1).strip(), split.group(2).strip(), "actions")
            if action.kind == "utility" and action.damage == "0":
                continue
            if uses:
                current, maximum, recovery_text = uses
                recovery = "short" if re.search(r"корот|short", recovery_text, re.I) else "long"
                resource = Resource(name=action.name, current=current, maximum=maximum, recovery=recovery)
                combatant.resources.append(resource)
                action.resource_id = resource.id
            combatant.actions.append(action)
            result.found.append(f"actions: {action.name}")

    if combatant.initiative_bonus == 0 and "инициатива" not in result.found and score_count:
        combatant.initiative_bonus = combatant.ability_mod("dex")
        result.warnings.append("Инициатива не указана; для боя вычислен модификатор ЛОВ по правилам 5e.")
    if not combatant.actions:
        result.warnings.append("Боевые действия не распознаны; исходный текст сохранён для ручной проверки.")
    if "КД" not in result.found:
        result.warnings.append("КД не указана; в рабочей схеме показано безопасное значение 10.")
    if hp_match is None:
        result.warnings.append("ОЗ не указаны; в рабочей схеме показано безопасное значение 10/10.")
    if "скорость" not in result.found:
        result.warnings.append("Скорость не указана; в рабочей схеме показано безопасное значение 30 фт.")
    if score_count == 0:
        result.warnings.append("Характеристики не указаны; значения схемы 10 отмечены как отсутствующие, а не найденные.")

    # Stable audit order, without claiming defaults were found in the source.
    result.found = list(dict.fromkeys(result.found))
    combatant.audit = [
        *(f"Найдено: {item}" for item in result.found),
        *(f"Проверить: {warning}" for warning in result.warnings),
    ]
    return result
