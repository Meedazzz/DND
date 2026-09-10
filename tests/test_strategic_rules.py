"""Стратегический движок: дистанции, движение, удары, инициатива, фланг."""

import pytest

from dragon_saga.strategic_rules import (
    CellPos,
    battle_outcome,
    can_move,
    distance_ft,
    flanking,
    grid_distance,
    hex_distance,
    in_range,
    max_cells,
    roll_dice,
    roll_initiative,
    resolve_strike,
    square_distance,
)


def test_square_distance_chebyshev():
    assert square_distance(CellPos(0, 0), CellPos(0, 0)) == 0
    assert square_distance(CellPos(0, 0), CellPos(1, 1)) == 1  # диагональ = 1
    assert square_distance(CellPos(2, 3), CellPos(5, 7)) == 4


def test_hex_distance_known_values():
    origin = CellPos(4, 4)
    assert hex_distance(origin, origin) == 0
    # Соседи odd-r для чётной строки: (4,3),(4,5),(3,3),(3,4),(5,3),(5,4)
    for neighbour in (CellPos(4, 3), CellPos(4, 5), CellPos(3, 3),
                      CellPos(3, 4), CellPos(5, 3), CellPos(5, 4)):
        assert hex_distance(origin, neighbour) == 1, neighbour
    assert hex_distance(origin, CellPos(4, 6)) == 2
    assert hex_distance(CellPos(0, 0), CellPos(2, 0)) == 2


def test_grid_distance_switch_and_feet():
    a, b = CellPos(0, 0), CellPos(3, 4)
    assert grid_distance(a, b, "square") == 4
    assert distance_ft(a, b, "square", 5) == 20
    assert distance_ft(a, b, "square", 10) == 40


def test_melee_only_hits_adjacent():
    me, foe = CellPos(5, 5), CellPos(6, 6)
    ok, dist = in_range(me, foe, 5, "square", 5)
    assert ok and dist == 5
    far = CellPos(7, 7)
    ok, _ = in_range(me, far, 5, "square", 5)
    assert not ok
    ok, dist = in_range(me, far, 30, "square", 5)
    assert ok and dist == 10  # Чебышев: 2 клетки


def test_movement_budget_and_blockers():
    origin = CellPos(0, 0)
    assert can_move(origin, CellPos(0, 6), 30, "square", 5) == (True, "ход разрешён")
    ok, reason = can_move(origin, CellPos(0, 7), 30, "square", 5)
    assert not ok and "скорости" in reason
    assert can_move(origin, origin, 30)[0] is False
    assert can_move(origin, CellPos(0, 1), 30, passable=False)[0] is False
    assert can_move(origin, CellPos(0, 1), 30, occupied=True)[0] is False
    assert max_cells(30, 5) == 6
    assert max_cells(0, 5) == 0


def test_roll_dice_shapes():
    assert roll_dice("7", lambda a, b: 1) == (7, [7])
    total, parts = roll_dice("2d6+3", lambda a, b: 6)
    assert (total, parts) == (15, [6, 6])
    with pytest.raises(ValueError):
        roll_dice("кубики", lambda a, b: 1)


def test_strike_crit_and_fumble_are_forced():
    crit = resolve_strike("Герой", 5, "1d8+2", "Гоблин", 10, 20, lambda a, b: b)
    assert crit.critical and crit.hit and crit.damage >= 3
    assert "КРИТ" in crit.detail
    fumble = resolve_strike("Герой", 5, "1d8+2", "Гоблин", 10, 20, lambda a, b: a)
    assert fumble.fumble and not fumble.hit and fumble.damage == 0


def test_strike_miss_and_destroy():
    miss = resolve_strike("Герой", 0, "1d6", "Тень", 30, 10, lambda a, b: 10)
    assert not miss.hit and miss.target_hp_left == 10 and not miss.destroyed
    kill = resolve_strike("Герой", 10, "10", "Гоблин", 5, 6, lambda a, b: 10)
    assert kill.hit and kill.destroyed and kill.target_hp_left == 0
    assert "уничтожен" in kill.detail


def test_initiative_orders_by_roll_then_dex():
    order = roll_initiative([("a", 1), ("b", 3), ("c", 0)], lambda a, b: 10)
    assert [unit_id for unit_id, _ in order] == ["b", "a", "c"]
    assert all(total == 10 + mod for (_, total), mod in zip(order, (3, 1, 0)))


def test_flanking_opposite_sides():
    target = CellPos(5, 5)
    assert flanking(CellPos(5, 4), target, [CellPos(5, 6)])
    assert flanking(CellPos(4, 4), target, [CellPos(6, 6)])
    assert not flanking(CellPos(5, 4), target, [CellPos(4, 4)])  # рядом, не напротив
    assert not flanking(CellPos(5, 4), target, [CellPos(5, 7)])  # не примыкает
    assert not flanking(CellPos(5, 3), target, [CellPos(5, 6)])  # сам далеко


def test_flanking_hex():
    target = CellPos(4, 4)
    # (4,3) слева и (4,5) справа — строго напротив
    assert flanking(CellPos(4, 3), target, [CellPos(4, 5)], "hex")
    assert not flanking(CellPos(4, 3), target, [CellPos(3, 3)], "hex")


def test_battle_outcome():
    assert battle_outcome({"hero": 10, "enemy": 5}) is None
    assert battle_outcome({"hero": 10, "enemy": 0}) == "hero"
    assert battle_outcome({"hero": 0, "enemy": 0}) == "draw"
