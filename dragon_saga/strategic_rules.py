"""Стратегический бой: чистая логика без Qt.

Модуль 5.1.0 — математика глобальной карты, отделённая от отрисовки:
дистанции на квадратной и гексагональной сетке, проверка движения,
броски атаки и урона, инициатива, фланг и определение победителя.

Все броски идут через инжектируемый ``randint`` — в бою это
:func:`random.randint`, в тестах — фиксированная функция.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

Randint = Callable[[int, int], int]

GRID_SQUARE = "square"
GRID_HEX = "hex"


@dataclass(frozen=True)
class CellPos:
    """Позиция на поле: строка и столбец (для гексов — odd-r offset)."""

    row: int
    col: int


# ------------------------------------------------------------------
# Дистанции
# ------------------------------------------------------------------

def square_distance(a: CellPos, b: CellPos) -> int:
    """Дистанция Чебышева: диагональ стоит 1 клетку (вариант 5e «1-1»)."""
    return max(abs(a.row - b.row), abs(a.col - b.col))


def _offset_to_axial(pos: CellPos) -> tuple[int, int]:
    """odd-r offset → axial (pointy-top)."""
    q = pos.col - (pos.row - (pos.row & 1)) // 2
    return q, pos.row


def hex_distance(a: CellPos, b: CellPos) -> int:
    """Дистанция между гексами через кубические координаты."""
    aq, ar = _offset_to_axial(a)
    bq, br = _offset_to_axial(b)
    ax, az = aq, ar
    bx, bz = bq, br
    ay, by = -ax - az, -bx - bz
    return (abs(ax - bx) + abs(ay - by) + abs(az - bz)) // 2


def grid_distance(a: CellPos, b: CellPos, grid_type: str = GRID_SQUARE) -> int:
    """Дистанция в клетках для выбранного типа сетки."""
    if grid_type == GRID_HEX:
        return hex_distance(a, b)
    return square_distance(a, b)


def distance_ft(a: CellPos, b: CellPos, grid_type: str = GRID_SQUARE, cell_ft: int = 5) -> int:
    """Дистанция в футах (1 клетка = ``cell_ft`` футов)."""
    return grid_distance(a, b, grid_type) * max(1, cell_ft)


def in_range(attacker: CellPos, target: CellPos, range_ft: int,
             grid_type: str = GRID_SQUARE, cell_ft: int = 5) -> tuple[bool, int]:
    """Проверка досягаемости. Возвращает (достаёт, дистанция_в_футах).

    Ближний бой (5 футов и меньше) бьёт только по соседним клеткам.
    """
    dist = distance_ft(attacker, target, grid_type, cell_ft)
    if range_ft <= 5:
        return grid_distance(attacker, target, grid_type) == 1, dist
    return dist <= max(0, range_ft), dist


def max_cells(speed_ft: int, cell_ft: int = 5) -> int:
    """Сколько клеток юнит проходит за ход."""
    return max(0, int(speed_ft) // max(1, cell_ft))


def can_move(origin: CellPos, destination: CellPos, speed_ft: int,
             grid_type: str = GRID_SQUARE, cell_ft: int = 5,
             passable: bool = True, occupied: bool = False) -> tuple[bool, str]:
    """Можно ли пройти из клетки в клетку за один ход.

    Возвращает (разрешено, причина_на_русском).
    """
    if origin == destination:
        return False, "юнит уже стоит на этой клетке"
    if not passable:
        return False, "клетка непроходима"
    if occupied:
        return False, "клетка занята другим юнитом"
    need = grid_distance(origin, destination, grid_type)
    budget = max_cells(speed_ft, cell_ft)
    if need > budget:
        return False, f"нужно {need} кл., а скорости хватает на {budget}"
    return True, "ход разрешён"


# ------------------------------------------------------------------
# Кубы
# ------------------------------------------------------------------

def d20(modifier: int = 0, randint: Randint | None = None,
        advantage: int = 0) -> tuple[int, list[int], int]:
    """Бросок d20: (итог, кубы, натуральное значение)."""
    dice_fn = randint or random.randint
    if advantage == 0:
        dice = [dice_fn(1, 20)]
        natural = dice[0]
    else:
        dice = [dice_fn(1, 20), dice_fn(1, 20)]
        natural = max(dice) if advantage > 0 else min(dice)
    return natural + modifier, dice, natural


_DICE_RE = re.compile(r"^\s*(?:(\d*)d(\d+))?\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


def roll_dice(formula: str, randint: Randint | None = None) -> tuple[int, list[int]]:
    """Бросок вида ``2d6+3`` или plain-числа. Возвращает (итог, кубы)."""
    dice_fn = randint or random.randint
    clean = (formula or "").strip().lower().replace(" ", "")
    if re.fullmatch(r"[+-]?\d+", clean or "0"):
        return int(clean or 0), [int(clean or 0)]
    match = _DICE_RE.match(clean)
    if not match or "d" not in clean:
        raise ValueError(f"Неверная формула урона: {formula!r}")
    count = int(match.group(1) or 1)
    die = int(match.group(2))
    modifier = int((match.group(3) or "0").replace(" ", ""))
    if not 1 <= count <= 100 or not 2 <= die <= 1000:
        raise ValueError("Формула выходит за безопасные пределы")
    parts = [dice_fn(1, die) for _ in range(count)]
    return sum(parts) + modifier, parts


# ------------------------------------------------------------------
# Атака
# ------------------------------------------------------------------

@dataclass
class StrikeResult:
    attacker_name: str
    target_name: str
    hit: bool
    critical: bool = False
    fumble: bool = False
    total: int = 0
    dice: list[int] = field(default_factory=list)
    target_ac: int = 10
    damage: int = 0
    target_hp_left: int = 0
    destroyed: bool = False
    detail: str = ""


def resolve_strike(attacker_name: str, attack_bonus: int, damage: str,
                   target_name: str, target_ac: int, target_hp: int,
                   randint: Randint | None = None, advantage: int = 0) -> StrikeResult:
    """Разрешить удар юнита по юниту: попадание, крит, урон, добивание.

    Натуральная 20 — крит (кубы урона удваиваются), натуральная 1 — промах.
    """
    total, dice, natural = d20(attack_bonus, randint, advantage)
    critical = natural == 20
    fumble = natural == 1
    hit = critical or (not fumble and total >= target_ac)
    dealt = 0
    if hit:
        dealt, _ = roll_dice(damage, randint)
        if critical:
            extra, _ = roll_dice(re.sub(r"([+-]\d+)$", "", damage.strip() or "1"), randint)
            dealt += extra
        dealt = max(0, dealt)
    left = max(0, target_hp - dealt)
    roll_text = "/".join(map(str, dice))
    if critical:
        detail = (f"{attacker_name} → {target_name}: {roll_text} {attack_bonus:+d} = {total} "
                  f"против КД {target_ac} — КРИТ! Урон {dealt} (осталось {left} ОЗ)")
    elif hit:
        detail = (f"{attacker_name} → {target_name}: {roll_text} {attack_bonus:+d} = {total} "
                  f"против КД {target_ac} — попадание. Урон {dealt} (осталось {left} ОЗ)")
    elif fumble:
        detail = (f"{attacker_name} → {target_name}: {roll_text} — критический промах!")
    else:
        detail = (f"{attacker_name} → {target_name}: {roll_text} {attack_bonus:+d} = {total} "
                  f"против КД {target_ac} — промах")
    if hit and left == 0:
        detail += f" · {target_name} уничтожен!"
    return StrikeResult(
        attacker_name=attacker_name, target_name=target_name, hit=hit,
        critical=critical, fumble=fumble, total=total, dice=dice,
        target_ac=target_ac, damage=dealt, target_hp_left=left,
        destroyed=hit and left == 0, detail=detail,
    )


# ------------------------------------------------------------------
# Инициатива, фланг, исход
# ------------------------------------------------------------------

def roll_initiative(entries: Iterable[tuple[str, int]],
                    randint: Randint | None = None) -> list[tuple[str, int]]:
    """Порядок ходов: d20 + модификатор ЛОВ, ничья — по модификатору.

    ``entries`` — (id юнита, мод ЛОВ). Возвращает [(id, итог)] по убыванию.
    Стабильная сортировка: полные ничьи сохраняют входной порядок.
    """
    rolled = []
    for unit_id, dex_mod in entries:
        total, _, _ = d20(int(dex_mod), randint)
        rolled.append((unit_id, total, int(dex_mod)))
    rolled.sort(key=lambda item: (item[1], item[2]), reverse=True)
    return [(unit_id, total) for unit_id, total, _ in rolled]


def flanking(attacker: CellPos, target: CellPos, allies: Iterable[CellPos],
             grid_type: str = GRID_SQUARE) -> bool:
    """Фланг: союзник стоит с противоположной от атакующего стороны цели.

    Обе клетки должны примыкать к цели, а векторы «цель→атакующий» и
    «цель→союзник» — смотреть в разные стороны (скалярное произведение < 0).
    Фланг даёт атакующему преимущество.
    """
    def vector(frm: CellPos, to: CellPos) -> tuple[float, float]:
        if grid_type == GRID_HEX:
            fq, fr = _offset_to_axial(frm)
            tq, tr = _offset_to_axial(to)
            # axial → пиксельные координаты pointy-top для честного угла
            fx, fy = fq + fr / 2, fr * 0.866
            tx, ty = tq + tr / 2, tr * 0.866
            return tx - fx, ty - fy
        return to.col - frm.col, to.row - frm.row

    if grid_distance(attacker, target, grid_type) != 1:
        return False
    attack_vector = vector(target, attacker)
    for ally in allies:
        if ally == attacker:
            continue
        if grid_distance(ally, target, grid_type) != 1:
            continue
        ally_vector = vector(target, ally)
        dot = attack_vector[0] * ally_vector[0] + attack_vector[1] * ally_vector[1]
        if dot < 0:
            return True
    return False


def battle_outcome(hp_by_side: dict[str, int]) -> str | None:
    """Исход битвы: сторона-победитель, ``\"draw\"`` или None (бой идёт).

    ``hp_by_side`` — суммарные текущие ОЗ живых юнитов каждой стороны.
    """
    alive = {side: hp for side, hp in hp_by_side.items() if hp > 0}
    if not alive:
        return "draw"
    if len(alive) == 1:
        return next(iter(alive))
    return None
