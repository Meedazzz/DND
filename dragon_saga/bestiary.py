"""Встроенный бестиарий «Драконьей Саги» — готовые существа в один клик.

Десять оригинальных существ трёх рангов (моб / элита / босс) с полными
боевыми листами: характеристики, защиты, действия, ресурсы, исходный
текст и аудит. Это не выдержки из книг — существа написаны для саги и
сбалансированы под конструктор встреч (CR совместим с таблицей XP 5e).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ABILITIES, Action, Combatant, Resource


@dataclass(frozen=True)
class BestiaryEntry:
    id: str
    name: str
    rank: str  # mob | elite | boss
    cr: str
    blurb: str


ENTRIES: tuple[BestiaryEntry, ...] = (
    BestiaryEntry("bandit", "Рубака тракта", "mob", "1/8", "Лиходей с большой дороги: скимитар и лёгкий арбалет."),
    BestiaryEntry("goblin", "Гоблин-застрельщик", "mob", "1/4", "Проворный стрелок; отходит бонусным действием."),
    BestiaryEntry("wolf", "Степной волк", "mob", "1/4", "Быстрая стая: 40 футов хода и тяжёлый укус."),
    BestiaryEntry("skeleton", "Костяной страж", "mob", "1/4", "Нежить-караульщик; боится дробящего урона."),
    BestiaryEntry("zombie", "Могильный мертвяк", "mob", "1/4", "Медленный, но невероятно живучий."),
    BestiaryEntry("cultist", "Фанатик Багрового Хора", "mob", "2", "Культист с боевой руной и огненной вспышкой."),
    BestiaryEntry("ogre", "Огр-громила", "elite", "2", "Гора мышц с двуручной палицей и дротиками."),
    BestiaryEntry("ash_knight", "Рыцарь пепла", "elite", "3", "Закалённый ветеран в чёрной броне, парный удар мечом."),
    BestiaryEntry("choir_archmage", "Архимаг Багрового Хора", "boss", "6", "Голос культа: багровые разряды и легендарное сопротивление."),
    BestiaryEntry("ash_wyrm", "Древний змей Золы", "boss", "8", "Крылатый ужас с пепельным дыханием (перезарядка 5–6)."),
)

_BY_ID = {entry.id: entry for entry in ENTRIES}


def entries() -> tuple[BestiaryEntry, ...]:
    return ENTRIES


def entry(entry_id: str) -> BestiaryEntry:
    if entry_id not in _BY_ID:
        raise KeyError(f"В бестиарии нет существа: {entry_id}")
    return _BY_ID[entry_id]


def _base(
    entry_id: str,
    *,
    name: str,
    ac: int,
    hp: int,
    speed: int,
    size: str,
    ctype: str,
    alignment: str,
    stats: tuple[int, int, int, int, int, int],
    blurb: str,
    source: str,
) -> Combatant:
    meta = _BY_ID[entry_id]
    return Combatant(
        name=name,
        side="enemy",
        rank=meta.rank,
        is_boss=meta.rank == "boss",
        armor_class=ac,
        hp=hp,
        max_hp=hp,
        speed=speed,
        proficiency=2 if meta.rank == "mob" else (3 if meta.rank == "elite" else 4),
        stats=dict(zip(ABILITIES, stats)),
        creature_size=size,
        creature_type=ctype,
        alignment=alignment,
        challenge_rating=meta.cr,
        source_text=source,
        audit=[
            f"Бестиарий «Драконьей Саги 5.0»: {meta.name} (CR {meta.cr}).",
            f"Ранг: { {'mob': 'моб', 'elite': 'элита', 'boss': 'босс'}[meta.rank] } — портретная заглушка выбирается автоматически.",
            "Характеристики и действия сверены с конструктором встреч; исходный текст сохранён дословно.",
        ],
    )


def _bandit() -> Combatant:
    c = _base(
        "bandit", name="Рубака тракта", ac=12, hp=11, speed=30, size="Средний",
        ctype="гуманоид", alignment="хаотично-нейтральный", stats=(11, 12, 12, 10, 10, 10),
        blurb="", source="Рубака тракта. Средний гуманоид, хаотично-нейтральный. КД 12 (кожаный доспех), ОЗ 11, скорость 30 фт. Скимитар +3 (1d6+1), лёгкий арбалет +3 (1d8+1, 80/320 фт).",
    )
    c.actions = [
        Action(name="Скимитар", kind="attack", attack_bonus=3, damage="1d6+1", damage_type="рубящий", range_ft=5),
        Action(name="Лёгкий арбалет", kind="attack", attack_bonus=3, damage="1d8+1", damage_type="колющий", range_ft=80),
    ]
    c.languages = "общий"
    return c


def _goblin() -> Combatant:
    c = _base(
        "goblin", name="Гоблин-застрельщик", ac=15, hp=7, speed=30, size="Маленький",
        ctype="гуманоид", alignment="нейтрально-злой", stats=(8, 14, 10, 10, 8, 8),
        blurb="", source="Гоблин-застрельщик. Маленький гуманоид, нейтрально-злой. КД 15 (кожаный доспех, щит), ОЗ 7, скорость 30 фт. Скимитар +4 (1d6+2), короткий лук +4 (1d6+2, 80/320 фт). Проворство: бонусным действием Отход или Засада.",
    )
    c.stats["dex"] = 14
    c.actions = [
        Action(name="Скимитар", kind="attack", attack_bonus=4, damage="1d6+2", damage_type="рубящий", range_ft=5),
        Action(name="Короткий лук", kind="attack", attack_bonus=4, damage="1d6+2", damage_type="колющий", range_ft=80),
        Action(name="Проворство: Отход или Засада", kind="utility", section="bonus", description="Гоблин совершает Отход или Затаивается.", damage="0"),
    ]
    c.skills = {"Скрытность": 6}
    c.senses = "тёмное зрение 60 фт"
    c.languages = "общий, гоблинский"
    return c


def _wolf() -> Combatant:
    c = _base(
        "wolf", name="Степной волк", ac=13, hp=11, speed=40, size="Средний",
        ctype="зверь", alignment="без мировоззрения", stats=(12, 15, 12, 3, 12, 6),
        blurb="", source="Степной волк. Средний зверь. КД 13 (природный), ОЗ 11, скорость 40 фт. Укус +4 (2d4+2), при попадании цель СИЛ Сл 11 или сбита с ног.",
    )
    c.actions = [
        Action(name="Укус", kind="attack", attack_bonus=4, damage="2d4+2", damage_type="колющий", range_ft=5, description="Попадание: цель совершает спасбросок СИЛ Сл 11 или падает ничком."),
    ]
    c.traits = ["Стайная тактика: преимущество атак, если союзник в 5 футах от цели"]
    c.skills = {"Восприятие": 3, "Скрытность": 4}
    return c


def _skeleton() -> Combatant:
    c = _base(
        "skeleton", name="Костяной страж", ac=13, hp=13, speed=30, size="Средний",
        ctype="нежить", alignment="беззаконно-злой", stats=(10, 14, 15, 6, 8, 5),
        blurb="", source="Костяной страж. Средняя нежить, беззаконно-злая. КД 13 (обломки доспеха), ОЗ 13, скорость 30 фт. Короткий меч +4 (1d6+2), короткий лук +4 (1d6+2, 80/320 фт). Уязвимость дробящему, иммунитет яду.",
    )
    c.actions = [
        Action(name="Короткий меч", kind="attack", attack_bonus=4, damage="1d6+2", damage_type="колющий", range_ft=5),
        Action(name="Короткий лук", kind="attack", attack_bonus=4, damage="1d6+2", damage_type="колющий", range_ft=80),
    ]
    c.vulnerabilities = ["дробящий"]
    c.immunities = ["яд"]
    c.condition_immunities = ["Отравленный", "Истощение"]
    c.senses = "тёмное зрение 60 фт"
    return c


def _zombie() -> Combatant:
    c = _base(
        "zombie", name="Могильный мертвяк", ac=8, hp=22, speed=20, size="Средний",
        ctype="нежить", alignment="нейтрально-злой", stats=(13, 6, 16, 3, 6, 5),
        blurb="", source="Могильный мертвяк. Средняя нежить, нейтрально-злая. КД 8, ОЗ 22, скорость 20 фт. Удар +3 (1d6+1). Неумирающая стойкость: при смертельном уроне спасбросок ТЕЛ Сл 5 + урон, при успехе остаётся 1 ОЗ.",
    )
    c.actions = [
        Action(name="Удар", kind="attack", attack_bonus=3, damage="1d6+1", damage_type="дробящий", range_ft=5),
    ]
    c.traits = ["Неумирающая стойкость: спасбросок ТЕЛ Сл 5+урон при падении до 0 ОЗ — при успехе остаётся 1 ОЗ"]
    c.immunities = ["яд"]
    c.condition_immunities = ["Отравленный"]
    c.senses = "тёмное зрение 60 фт"
    return c


def _cultist() -> Combatant:
    c = _base(
        "cultist", name="Фанатик Багрового Хора", ac=13, hp=33, speed=30, size="Средний",
        ctype="гуманоид", alignment="беззаконно-злой", stats=(11, 12, 10, 10, 13, 14),
        blurb="", source="Фанатик Багрового Хора. Средний гуманоид, беззаконно-злой. КД 13 (кожаный доспех), ОЗ 33, скорость 30 фт. Ритуальный клинок +4 (1d6+2 плюс 1d6 огнём), Огненная вспышка: спасбросок ЛОВ Сл 12, 2d6 огня (2/день).",
    )
    c.saves = {"wis": 3}
    resource = Resource(name="Огненная вспышка", current=2, maximum=2)
    c.resources = [resource]
    c.actions = [
        Action(name="Ритуальный клинок", kind="attack", attack_bonus=4, damage="1d6+2", damage_type="колющий", range_ft=5, description="Плюс 1d6 огненного урона при попадании (глашатай пламени)."),
        Action(name="Огненная вспышка", kind="save", save_ability="dex", save_dc=12, damage="2d6", damage_type="огонь", half_on_save=True, range_ft=30, resource_id=resource.id),
    ]
    c.languages = "общий"
    return c


def _ogre() -> Combatant:
    c = _base(
        "ogre", name="Огр-громила", ac=11, hp=59, speed=40, size="Большой",
        ctype="великан", alignment="хаотично-злой", stats=(19, 8, 16, 5, 7, 7),
        blurb="", source="Огр-громила. Большой великан, хаотично-злой. КД 11 (шкуры), ОЗ 59, скорость 40 фт. Двуручная палица +6 (2d8+4), дротик +6 (2d6+4, 30/120 фт).",
    )
    c.actions = [
        Action(name="Двуручная палица", kind="attack", attack_bonus=6, damage="2d8+4", damage_type="дробящий", range_ft=5),
        Action(name="Дротик", kind="attack", attack_bonus=6, damage="2d6+4", damage_type="колющий", range_ft=30),
    ]
    c.hit_die = 10
    c.hit_dice_current = 7
    c.hit_dice_max = 7
    c.languages = "общий, великаний"
    return c


def _ash_knight() -> Combatant:
    c = _base(
        "ash_knight", name="Рыцарь пепла", ac=18, hp=52, speed=30, size="Средний",
        ctype="гуманоид", alignment="беззаконно-нейтральный", stats=(16, 11, 14, 11, 11, 15),
        blurb="", source="Рыцарь пепла. Средний гуманоид, беззаконно-нейтральный. КД 18 (латный доспех), ОЗ 52, скорость 30 фт. Парный удар мечом +5 (2d8+6), тяжёлый арбалет +2 (1d10, 100/400 фт). Спасброски ТЕЛ +4, МДР +2.",
    )
    c.saves = {"con": 4, "wis": 2}
    c.actions = [
        Action(name="Парный удар мечом", kind="attack", attack_bonus=5, damage="2d8+6", damage_type="рубящий", range_ft=5, description="Мультиатака: два удара длинным мечом одной кнопкой."),
        Action(name="Тяжёлый арбалет", kind="attack", attack_bonus=2, damage="1d10", damage_type="колющий", range_ft=100),
    ]
    c.traits = ["Хладнокровие: атаки с преимуществом, пока союзник рядом и не недееспособен"]
    return c


def _choir_archmage() -> Combatant:
    c = _base(
        "choir_archmage", name="Архимаг Багрового Хора", ac=15, hp=99, speed=30, size="Средний",
        ctype="гуманоид", alignment="беззаконно-злой", stats=(9, 14, 14, 17, 15, 18),
        blurb="", source="Архимаг Багрового Хора. Средний гуманоид, беззаконно-злой. КД 15 (мантия хоров), ОЗ 99, скорость 30 фт. Посох хора +6 (1d8+2 плюс 2d6 некротического), Багровый разряд: спасбросок ЛОВ Сл 15, 6d6 некротического (половина при успехе). Легендарное сопротивление 3/день.",
    )
    c.saves = {"int": 6, "wis": 5}
    resistance = Resource(name="Легендарное сопротивление", current=3, maximum=3)
    legendary = Resource(name="Легендарные действия", current=3, maximum=3)
    c.resources = [resistance, legendary]
    c.actions = [
        Action(name="Посох хора", kind="attack", attack_bonus=6, damage="1d8+2", damage_type="дробящий", range_ft=5, description="Плюс 2d6 некротического урона при попадании."),
        Action(name="Багровый разряд", kind="save", save_ability="dex", save_dc=15, damage="6d6", damage_type="некротический", half_on_save=True, range_ft=60),
        Action(name="Хоровая поступь", kind="utility", description="Архимаг телепортируется на 20 футов в свободное место.", damage="0"),
    ]
    c.legendary_actions = [
        "Певучий шаг (1): перемещается без провоцированных атак",
        "Диссонанс (2): цель, спасбросок МДР Сл 15, иначе испуг до конца следующего хода",
        "Крещендо (3): багровый импульс 1d6 всем врагам в авангарде",
    ]
    c.traits = ["Глас хора: союзники культа в 30 футах получают +2 к спасброскам от страха"]
    c.skills = {"Магия": 6, "История": 6}
    c.languages = "общий, бездны"
    c.is_boss = True
    return c


def _ash_wyrm() -> Combatant:
    c = _base(
        "ash_wyrm", name="Древний змей Золы", ac=17, hp=152, speed=40, size="Огромный",
        ctype="змей", alignment="хаотично-злой", stats=(23, 12, 21, 12, 13, 17),
        blurb="", source="Древний змей Золы. Огромный змей, хаотично-злой. КД 17 (природный), ОЗ 152, скорость 40 фт, полёт 80 фт. Укус +9 (2d6+6), когти +9 (2d8+6), Пепельное дыхание (перезарядка 5-6): спасбросок ЛОВ Сл 16, 10d6 огня. Легендарное сопротивление 3/день.",
    )
    c.saves = {"dex": 4, "con": 8, "wis": 4, "cha": 6}
    resistance = Resource(name="Легендарное сопротивление", current=3, maximum=3)
    c.resources = [resistance]
    c.actions = [
        Action(name="Укус", kind="attack", attack_bonus=9, damage="2d6+6", damage_type="колющий", range_ft=10),
        Action(name="Когти", kind="attack", attack_bonus=9, damage="2d8+6", damage_type="рубящий", range_ft=5),
        Action(name="Пепельное дыхание", kind="save", save_ability="dex", save_dc=16, damage="10d6", damage_type="огонь", half_on_save=True, range_ft=40, recharge="5-6"),
    ]
    c.traits = ["Пугающее присутствие: враги в 60 футах — спасбросок МДР Сл 16 или испуг на 1 минуту"]
    c.legendary_actions = [
        "Взмах крыльев (2): все рядом — спасбросок ЛОВ Сл 16 или сбиты с ног; змей взлетает",
        "Удар хвостом (1): +9, 1d8+6 дробящего",
        "Пепельный шлейф (3): облако золы, тяжело заслонённая местность до конца следующего хода",
    ]
    c.immunities = ["огонь"]
    c.skills = {"Восприятие": 10, "Скрытность": 7}
    c.senses = "слепое зрение 60 фт, тёмное зрение 120 фт"
    c.languages = "общий, драконий"
    c.hit_die = 12
    c.hit_dice_current = 12
    c.hit_dice_max = 12
    c.is_boss = True
    return c


_BUILDERS = {
    "bandit": _bandit,
    "goblin": _goblin,
    "wolf": _wolf,
    "skeleton": _skeleton,
    "zombie": _zombie,
    "cultist": _cultist,
    "ogre": _ogre,
    "ash_knight": _ash_knight,
    "choir_archmage": _choir_archmage,
    "ash_wyrm": _ash_wyrm,
}


def create(entry_id: str, *, number: int = 0) -> Combatant:
    """Новый экземпляр существа; ``number`` добавляет нумерацию к имени.

    Нумерация римскими (II, III…) — чтобы группы однотипных мобов
    различались на сцене и в инициативе.
    """
    if entry_id not in _BUILDERS:
        raise KeyError(f"В бестиарии нет существа: {entry_id}")
    combatant = _BUILDERS[entry_id]()
    if number >= 2:
        numerals = ["", "II", "III", "IV", "V", "VI", "VII", "VIII"]
        suffix = numerals[number - 1] if number - 1 < len(numerals) else str(number)
        combatant.name = f"{combatant.name} {suffix}"
    return combatant


def preview_html(entry_id: str) -> str:
    """Краткая сводка для предпросмотра в диалоге (без Qt)."""
    import html as _html

    meta = entry(entry_id)
    c = create(entry_id)
    rank = {"mob": "МОБ", "elite": "ЭЛИТА", "boss": "БОСС"}[meta.rank]
    section_ru = {"actions": "действие", "bonus": "бонус", "reactions": "реакция", "legendary": "легендарное"}
    abilities = " &nbsp; ".join(f"<b>{key.upper()}</b> {c.stats[key]}" for key in ABILITIES)
    actions = "".join(
        f"<li><b>{_html.escape(a.name)}</b> · {section_ru.get(a.section, _html.escape(a.section))} · "
        f"{_html.escape(a.damage)}{(' · Сл ' + str(a.save_dc)) if a.save_dc else ''}"
        f"{(' · ' + _html.escape(a.recharge)) if a.recharge else ''}</li>"
        for a in c.actions
    )
    resources = "".join(f"<li>{_html.escape(r.name)}: <b>{r.current}/{r.maximum}</b></li>" for r in c.resources) or "<li>Нет</li>"
    defenses = []
    for label, values in (("Сопротивления", c.resistances), ("Иммунитеты", c.immunities), ("Уязвимости", c.vulnerabilities)):
        if values:
            defenses.append(f"{label}: {_html.escape(', '.join(values))}")
    defense_line = f"<p>{_html.escape(' · '.join(defenses))}</p>" if defenses else ""
    return f"""
    <div style='color:#d9cec4'>
      <p style='color:#b94d3f;letter-spacing:2px'><b>{rank} · CR {_html.escape(meta.cr)}</b></p>
      <h1 style='font-family:Georgia;color:#f0e4d8'>{_html.escape(c.name)}</h1>
      <p style='color:#91847f'>{_html.escape(' · '.join(x for x in (c.creature_size, c.creature_type, c.alignment) if x))}</p>
      <p style='color:#c9b48a'>{_html.escape(meta.blurb)}</p>
      <table cellspacing='8'><tr><td><b>КД</b><br>{c.armor_class}</td><td><b>ОЗ</b><br>{c.max_hp}</td><td><b>Скорость</b><br>{c.speed} фт</td></tr></table>
      <p>{abilities}</p>{defense_line}
      <h3>Действия</h3><ul>{actions}</ul>
      <h3>Ресурсы</h3><ul>{resources}</ul>
    </div>"""
