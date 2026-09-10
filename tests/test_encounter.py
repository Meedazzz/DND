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


def test_generate_deterministic_with_seed():
    first = encounter.generate([3, 3, 3, 4], "средняя", seed=42)
    second = encounter.generate([3, 3, 3, 4], "средняя", seed=42)
    assert first.picks == second.picks
    assert first.report.adjusted_xp == second.report.adjusted_xp
    assert first.seed == 42


def test_generate_hits_requested_band():
    party = [5, 5, 5, 5]
    for difficulty in ("лёгкая", "средняя", "тяжёлая"):
        result = encounter.generate(party, difficulty, seed=7)
        assert result.requested == difficulty
        assert result.report.difficulty == difficulty, (difficulty, result.picks)
        assert 1 <= len(result.monster_crs) <= 8
        assert result.report.monsters == len(result.monster_crs)


def test_generate_deadly_prefers_boss_or_elite():
    from dragon_saga import bestiary
    result = encounter.generate([8, 8, 8, 8], "смертельная", seed=11)
    ranks = {bestiary.entry(entry_id).rank for entry_id, _ in result.picks}
    assert ranks & {"boss", "elite"}
    assert result.report.difficulty in {"тяжёлая", "смертельная"}


def test_generate_respects_theme_and_cap():
    result = encounter.generate([3, 3, 3], "средняя", theme="undead", max_monsters=4, seed=3)
    assert result.theme == "undead"
    assert len(result.monster_crs) <= 4
    assert {entry_id for entry_id, _ in result.picks} <= {"skeleton", "zombie"}
    text = result.summary.lower()
    assert "страж" in text or "мертвяк" in text


def test_generate_validates_input():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        encounter.generate([], "средняя")
    with _pytest.raises(ValueError):
        encounter.generate([3], "невозможная")


def test_theme_pool_falls_back_to_full_catalog():
    from dragon_saga import bestiary
    assert len(encounter.theme_pool("no-such-theme")) == len(bestiary.entries())
    assert set(encounter.theme_pool("cult")) == {"cultist", "choir_hunter", "choir_archmage"}
