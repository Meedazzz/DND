"""Каталог состояний D&D 5e."""

from dragon_saga import conditions


def test_catalog_integrity():
    catalog = conditions.all()
    assert len(catalog) >= 15
    ru_names = [c.name_ru for c in catalog]
    assert len(set(ru_names)) == len(ru_names), "русские имена должны быть уникальны"
    for condition in catalog:
        assert condition.name_en and condition.summary
    core = {"Ослеплённый", "Очарованный", "Оглушённый", "Испуганный", "Схваченный",
            "Недееспособный", "Невидимый", "Окаменевший", "Отравленный", "Сбитый с ног",
            "Опутанный", "Ошеломлённый", "Без сознания", "Парализованный", "Истощение"}
    assert core <= set(ru_names)


def test_find_by_ru_and_en():
    assert conditions.find("испуганный").name_en == "Frightened"
    assert conditions.find("PRONE").name_ru == "Сбитый с ног"
    assert conditions.find("  ") is None
    assert conditions.find("небывалое") is None


def test_search_matches_name_and_summary():
    results = conditions.search("ослеп")
    assert any(c.name_ru == "Ослеплённый" for c in results)
    assert conditions.search("") == list(conditions.all())
    assert not conditions.search("zzzz")


def test_special_marks_exist_for_death_saves():
    assert conditions.find("Стабилизирован").special
    assert conditions.find("Мёртв").special


def test_split_known():
    known, custom = conditions.split_known(["Без сознания", "Горение 1d6", "Prone", ""])
    assert "Без сознания" in known and "Prone" in known
    assert custom == ["Горение 1d6"]
