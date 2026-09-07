"""Конструктор встреч: XP, множители и сложность."""

import pytest

from dragon_saga import encounter


def test_xp_table_basics():
    assert encounter.xp_for_cr("0") == 10
    assert encounter.xp_for_cr("1/4") == 50
    assert encounter.xp_for_cr("1/2") == 100
    assert encounter.xp_for_cr("5") == 1800
    assert encounter.xp_for_cr("30") == 155000
    with pytest.raises(ValueError):
        encounter.xp_for_cr("42")


def test_normalize_cr():
    assert encounter.normalize_cr("0.5") == "1/2"
    assert encounter.normalize_cr("0.25") == "1/4"
    assert encounter.normalize_cr("0.125") == "1/8"
    assert encounter.normalize_cr("2.0") == "2"
    assert encounter.normalize_cr("3") == "3"


def test_multiplier_steps():
    assert encounter.multiplier(1) == 1.0
    assert encounter.multiplier(2) == 1.5
    assert encounter.multiplier(3) == 2.0
    assert encounter.multiplier(6) == 2.0
    assert encounter.multiplier(7) == 2.5
    assert encounter.multiplier(10) == 2.5
    assert encounter.multiplier(11) == 3.0
    assert encounter.multiplier(14) == 3.0
    assert encounter.multiplier(15) == 4.0


def test_party_thresholds_sum():
    thresholds = encounter.party_thresholds([3, 3, 3, 4])
    assert thresholds == {"лёгкий": 350, "средний": 700, "тяжёлый": 1050, "смертельный": 1700}


def test_assess_difficulty_bands():
    report = encounter.assess([3, 3, 3, 4], ["2"])
    assert report.raw_xp == 450 and report.adjusted_xp == 450
    assert report.difficulty == "лёгкая"
    assert report.per_character_xp == 112
    deadly = encounter.assess([1, 1], ["5"])
    assert deadly.difficulty == "смертельная"
    pack = encounter.assess([5, 5, 5, 5], ["1/4"] * 6)
    assert pack.multiplier == 2.0 and pack.adjusted_xp == 600
    trivial = encounter.assess([10, 10, 10, 10], ["0"])
    assert trivial.difficulty == "пустяковая"


def test_assess_validates_input():
    with pytest.raises(ValueError):
        encounter.assess([], ["1"])
    with pytest.raises(ValueError):
        encounter.assess([3], [])
