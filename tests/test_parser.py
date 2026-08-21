from dragon_saga.parser import parse_stat_block


def test_russian_import_is_deterministic_and_preserves_source():
    source = """Ледяной огр
КД 15
ОЗ 59
Скорость 40 фт
СИЛ 19 ЛОВ 8 ТЕЛ 16 ИНТ 5 МДР 9 ХАР 7
Ледяной рёв (2/2, долгий отдых). Сл 14 ЛОВ, урон 2d6+3 холодом.
Дубина. +6 к атаке, досягаемость 10 фт, попадание 2d8+4 дробящего урона."""
    result = parse_stat_block(source, "enemy")
    actor = result.combatant
    assert actor.source_text == source
    assert actor.name == "Ледяной огр"
    assert (actor.armor_class, actor.hp, actor.max_hp, actor.speed) == (15, 59, 59, 40)
    assert actor.stats["str"] == 19 and actor.stats["dex"] == 8
    assert len(actor.resources) == 1
    assert (actor.resources[0].current, actor.resources[0].maximum) == (2, 2)
    assert len(actor.actions) == 2
    assert actor.actions[0].save_dc == 14
    assert actor.actions[1].attack_bonus == 6
    assert actor.actions[1].damage == "2d8+4"


def test_missing_fields_are_warned_not_invented_from_context():
    source = "Тень без чисел\nОписание существа и его повадок."
    result = parse_stat_block(source)
    assert result.combatant.name == "Тень без чисел"
    assert result.combatant.armor_class == 10
    assert result.combatant.hp == 10
    assert not result.combatant.actions
    assert len(result.warnings) >= 4
