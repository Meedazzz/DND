"""Конструктор встреч: XP-бюджет и сложность боя (D&D 5e, таблицы 2014).

Считает сырой и скорректированный опыт группы противников, пороги
сложности партии и итоговую оценку «легко / средне / тяжело / смертельно».
Чистые функции без Qt — используются и страницей калькуляторов, и тестами.
"""

from __future__ import annotations

from dataclasses import dataclass


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
