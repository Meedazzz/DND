"""Конструктор встреч: XP-бюджет и сложность боя (D&D 5e, таблицы 2014).

Считает сырой и скорректированный опыт группы противников, пороги
сложности партии и итоговую оценку «легко / средне / тяжело / смертельно».
Чистые функции без Qt — используются и страницей калькуляторов, и тестами.

С версии 5.1.0 здесь же живёт генератор встреч: подбор состава из
бестиария под заказанную сложность (офлайн-эвристика, без внешних ИИ).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import bestiary


# CR → XP. Ключи строками, чтобы совпадать с parser/bestiary («1/4», «5»…).
XP_BY_CR: dict[str, int] = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100,
    "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800,
    "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900,
    "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000,
    "16": 15000, "17": 18000, "18": 20000, "19": 22000, "20": 25000,
    "21": 33000, "22": 41000, "23": 50000, "24": 62000, "25": 75000,
    "26": 90000, "27": 105000, "28": 120000, "29": 135000, "30": 155000,
}

# Уровень → (легко, средне, тяжело, смертельно) XP на персонажа.
THRESHOLDS_BY_LEVEL: dict[int, tuple[int, int, int, int]] = {
    1: (25, 50, 75, 100), 2: (50, 100, 150, 200), 3: (75, 150, 225, 400),
    4: (125, 250, 375, 500), 5: (250, 500, 750, 1100), 6: (300, 600, 900, 1400),
    7: (350, 750, 1100, 1700), 8: (450, 900, 1400, 2100), 9: (550, 1100, 1600, 2400),
    10: (600, 1200, 1900, 2800), 11: (800, 1600, 2400, 3600), 12: (1000, 2000, 3000, 4500),
    13: (1100, 2200, 3400, 5100), 14: (1250, 2500, 3800, 5700), 15: (1400, 2800, 4300, 6400),
    16: (1600, 3200, 4800, 7200), 17: (2000, 3900, 5900, 8800), 18: (2100, 4200, 6300, 9500),
    19: (2400, 4900, 7300, 10900), 20: (2800, 5700, 8500, 12700),
}

DIFFICULTIES = ("пустяковая", "лёгкая", "средняя", "тяжёлая", "смертельная")


def normalize_cr(cr: str | int | float) -> str:
    """Привести CR к канонической строке таблицы."""
    text = str(cr).strip().replace(",", ".")
    if text in {"0.125", ".125"}:
        return "1/8"
    if text in {"0.25", ".25"}:
        return "1/4"
    if text in {"0.5", ".5"}:
        return "1/2"
    if text.endswith(".0"):
        text = text[:-2]
    return text


def xp_for_cr(cr: str) -> int:
    key = normalize_cr(cr)
    if key not in XP_BY_CR:
        raise ValueError(f"Неизвестный показатель опасности: {cr!r}")
    return XP_BY_CR[key]


def party_thresholds(levels: list[int]) -> dict[str, int]:
    """Суммарные пороги партии по уровням персонажей (1..20)."""
    totals = [0, 0, 0, 0]
    for level in levels:
        row = THRESHOLDS_BY_LEVEL.get(min(20, max(1, int(level))))
        if row:
            for index in range(4):
                totals[index] += row[index]
    keys = ("лёгкий", "средний", "тяжёлый", "смертельный")
    return {keys[index]: totals[index] for index in range(4)}


def multiplier(count: int) -> float:
    """Множитель XP за численность противников."""
    if count <= 1:
        return 1.0
    if count == 2:
        return 1.5
    if count <= 6:
        return 2.0
    if count <= 10:
        return 2.5
    if count <= 14:
        return 3.0
    return 4.0


@dataclass
class EncounterReport:
    raw_xp: int
    adjusted_xp: int
    monsters: int
    multiplier: float
    thresholds: dict[str, int]
    difficulty: str
    per_character_xp: int

    @property
    def summary(self) -> str:
        return (
            f"{self.raw_xp} XP · скорректировано {self.adjusted_xp} (×{self.multiplier:g}) · "
            f"сложность: {self.difficulty} · награда {self.per_character_xp} XP на героя"
        )


def assess(party_levels: list[int], monster_crs: list[str]) -> EncounterReport:
    """Оценить встречу: список уровней героев против списка CR врагов."""
    if not party_levels:
        raise ValueError("Укажите хотя бы одного героя")
    if not monster_crs:
        raise ValueError("Укажите хотя бы одного противника")
    raw = sum(xp_for_cr(cr) for cr in monster_crs)
    factor = multiplier(len(monster_crs))
    adjusted = int(raw * factor)
    thresholds = party_thresholds(party_levels)
    easy, medium, hard, deadly = (thresholds[key] for key in ("лёгкий", "средний", "тяжёлый", "смертельный"))
    if adjusted < easy:
        difficulty = "пустяковая"
    elif adjusted < medium:
        difficulty = "лёгкая"
    elif adjusted < hard:
        difficulty = "средняя"
    elif adjusted < deadly:
        difficulty = "тяжёлая"
    else:
        difficulty = "смертельная"
    return EncounterReport(
        raw_xp=raw,
        adjusted_xp=adjusted,
        monsters=len(monster_crs),
        multiplier=factor,
        thresholds=thresholds,
        difficulty=difficulty,
        per_character_xp=raw // max(1, len(party_levels)),
    )


# ------------------------------------------------------------------
# Генератор встреч 5.1.0: подбор состава из бестиария под сложность
# ------------------------------------------------------------------

#: Тематические пулы бестиария: id темы → (подпись, id существ).
THEMES: dict[str, tuple[str, tuple[str, ...]]] = {
    "any": ("Любая", ()),
    "undead": ("Нежить", ("skeleton", "zombie")),
    "wilds": ("Дикая природа", ("wolf", "spider", "harpy", "troll")),
    "brigands": ("Лихие люди", ("bandit", "goblin", "kobold", "ogre", "ash_knight")),
    "cult": ("Багровый Хор", ("cultist", "choir_hunter", "choir_archmage")),
    "ash": ("Пепел", ("ash_knight", "cultist", "ash_wyrm", "ash_matriarch")),
}

_DIFFICULTY_ALIASES = {
    "пустяковая": "пустяковая",
    "легкая": "лёгкая", "лёгкая": "лёгкая",
    "средняя": "средняя",
    "тяжелая": "тяжёлая", "тяжёлая": "тяжёлая",
    "смертельная": "смертельная",
}


def theme_pool(theme: str) -> list[str]:
    """Id существ темы; неизвестная/пустая тема — весь бестиарий."""
    _label, ids = THEMES.get(theme, THEMES["any"])
    known = {entry.id for entry in bestiary.entries()}
    pool = [entry_id for entry_id in ids if entry_id in known]
    return pool or [entry.id for entry in bestiary.entries()]


def _band_bounds(difficulty: str, thresholds: dict[str, int]) -> tuple[int, int, int]:
    """Границы заказанной сложности: (низ, верх, прицел).

    Верхняя граница исключительная — как в :func:`assess` (полоса
    «лёгкая» заканчивается там, где начинается «средняя»).
    """
    easy, medium, hard, deadly = (thresholds[key] for key in ("лёгкий", "средний", "тяжёлый", "смертельный"))
    if difficulty == "пустяковая":
        return 0, max(1, easy), max(1, easy // 2)
    if difficulty == "лёгкая":
        return easy, medium, easy + (medium - easy) * 3 // 4
    if difficulty == "средняя":
        return medium, hard, medium + (hard - medium) * 3 // 4
    if difficulty == "тяжёлая":
        return hard, deadly, hard + (deadly - hard) * 3 // 4
    return deadly, deadly * 2, deadly + deadly // 5


@dataclass
class GeneratedEncounter:
    """Подобранная встреча: состав, CR и готовый отчёт конструктора."""

    picks: list[tuple[str, int]] = field(default_factory=list)  # (entry_id, count)
    monster_crs: list[str] = field(default_factory=list)
    monster_names: list[str] = field(default_factory=list)
    report: EncounterReport | None = None
    requested: str = "средняя"
    theme: str = "any"
    seed: int = 0
    note: str = ""

    @property
    def summary(self) -> str:
        parts = ", ".join(f"{name} ×{count}" if count > 1 else name for name, count in self._named_picks())
        return f"{parts} — {self.report.difficulty if self.report else '—'}"

    def _named_picks(self) -> list[tuple[str, int]]:
        names = []
        for entry_id, count in self.picks:
            try:
                names.append((bestiary.entry(entry_id).name, count))
            except KeyError:
                names.append((entry_id, count))
        return names


def _adjusted_xp(crs: list[str]) -> int:
    return int(sum(xp_for_cr(cr) for cr in crs) * multiplier(len(crs)))


def _strategies_for(difficulty: str) -> tuple[str, ...]:
    if difficulty == "пустяковая":
        return ("single",)
    if difficulty == "лёгкая":
        return ("pack", "mixed", "pack", "mixed")
    if difficulty == "средняя":
        return ("mixed", "pack", "elite", "mixed", "elite")
    if difficulty == "тяжёлая":
        return ("elite", "mixed", "boss", "elite", "boss")
    return ("boss", "elite", "boss", "mixed", "elite")


def _attempt_picks(rng: random.Random, pool: list[str], strategy: str,
                   max_monsters: int, hi: int, target: int) -> list[str]:
    """Одна попытка собрать состав; возвращает список id существ."""
    by_rank: dict[str, list[str]] = {"mob": [], "elite": [], "boss": []}
    for entry_id in pool:
        by_rank[bestiary.entry(entry_id).rank].append(entry_id)
    mobs = by_rank["mob"] or pool
    elites = by_rank["elite"] or mobs
    bosses = by_rank["boss"] or elites

    def crs_of(picks: list[str]) -> list[str]:
        return [bestiary.entry(p).cr for p in picks]

    if strategy == "single":
        weakest = min(pool, key=lambda e: xp_for_cr(bestiary.entry(e).cr))
        return [weakest]

    picks: list[str] = []
    if strategy == "boss":
        picks.append(rng.choice(bosses))
        adds = rng.randint(0, 3)
        followers = mobs
    elif strategy == "elite":
        picks.append(rng.choice(elites))
        adds = rng.randint(1, 4)
        followers = mobs
    elif strategy == "pack":
        picks.append(rng.choice(mobs))
        adds = rng.randint(2, 5)
        followers = mobs
    else:  # mixed
        picks.append(rng.choice(pool))
        adds = rng.randint(1, 5)
        followers = pool

    for _ in range(adds):
        if len(picks) >= max_monsters:
            break
        candidate = rng.choice(followers)
        trial = picks + [candidate]
        if _adjusted_xp(crs_of(trial)) >= hi and picks:
            cheaper = [c for c in followers
                       if xp_for_cr(bestiary.entry(c).cr) < xp_for_cr(bestiary.entry(candidate).cr)]
            if cheaper:
                gentle = rng.choice(cheaper)
                trial = picks + [gentle]
                if _adjusted_xp(crs_of(trial)) >= hi:
                    break
            else:
                break
        picks = trial
        if _adjusted_xp(crs_of(picks)) >= target and rng.random() < 0.65:
            break
    if not picks:
        picks = [min(pool, key=lambda e: xp_for_cr(bestiary.entry(e).cr))]
    return picks[:max_monsters]


def generate(party_levels: list[int], difficulty: str = "средняя", *,
             theme: str = "any", max_monsters: int = 8, seed: int | None = None,
             attempts: int = 120) -> GeneratedEncounter:
    """Подобрать встречу из бестиария под партию и заказанную сложность.

    ``seed`` делает подбор воспроизводимым: один и тот же сид всегда
    даёт один и тот же состав. Без сида используется случайный.
    """
    if not party_levels:
        raise ValueError("Укажите хотя бы одного героя")
    canonical = _DIFFICULTY_ALIASES.get(difficulty.strip().lower(), "")
    if not canonical:
        raise ValueError(f"Неизвестная сложность: {difficulty!r}")
    pool = theme_pool(theme)
    if not pool:
        raise ValueError("Пустой пул существ для генерации")
    max_monsters = min(12, max(1, int(max_monsters)))
    if seed is None:
        seed = random.randint(0, 999_999)
    rng = random.Random(seed)
    thresholds = party_thresholds(party_levels)
    lo, hi, target = _band_bounds(canonical, thresholds)

    best: list[str] = []
    best_score: tuple[float, float] | None = None
    strategies = _strategies_for(canonical)
    for i in range(max(1, attempts)):
        strategy = strategies[i % len(strategies)]
        picks = _attempt_picks(rng, pool, strategy, max_monsters, hi, target)
        crs = [bestiary.entry(p).cr for p in picks]
        adjusted = _adjusted_xp(crs)
        if lo <= adjusted < hi:
            score = (0.0, float(target - adjusted))  # в полосе: ближе к прицелу
        elif adjusted < lo:
            score = (float(lo - adjusted), 0.0)  # недобрали
        else:
            score = (float((adjusted - hi) * 3 + 10_000), 0.0)  # перелёт хуже
        if best_score is None or score < best_score:
            best_score = score
            best = picks

    crs = [bestiary.entry(p).cr for p in best]
    report = assess(party_levels, crs)
    grouped: list[tuple[str, int]] = []
    for entry_id in best:
        for index, (known_id, count) in enumerate(grouped):
            if known_id == entry_id:
                grouped[index] = (known_id, count + 1)
                break
        else:
            grouped.append((entry_id, 1))
    hit = report.difficulty == canonical
    note = ("Состав точно в заказанной сложности." if hit
            else f"Ближайшее к заказу ({canonical}): вышло «{report.difficulty}» — пул темы слабоват, добавьте существ или поднимите лимит.")
    return GeneratedEncounter(
        picks=grouped,
        monster_crs=crs,
        monster_names=[bestiary.entry(p).name for p in best],
        report=report,
        requested=canonical,
        theme=theme if theme in THEMES else "any",
        seed=seed,
        note=note,
    )
