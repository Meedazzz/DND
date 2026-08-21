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


def test_continuous_russian_creature_splits_sections_actions_and_resource():
    source = "Имя: Гниющий Страж КД: 15 ОЗ: 68 Скорость: 30 фт СИЛ 18 ЛОВ 12 ТЕЛ 16 ИНТ 6 МДР 10 ХАР 7 Сопротивления урону: некротический Иммунитеты к состояниям: отравление Опасность: 4 Бонус мастерства: +2 Действия: Ржавый тесак. Атака +6, урон 1d10+4 рубящий. Могильный холод (2/2, долгий отдых). Спасбросок ТЕЛ Сл 14, урон 3d6 холод, половина при успехе. Реакции: Костяной заслон. Атака +6, урон 1d6+4 дробящий."
    actor = parse_stat_block(source, "enemy").combatant
    assert actor.source_text == source
    assert [action.name for action in actor.actions] == ["Ржавый тесак", "Могильный холод", "Костяной заслон"]
    assert [action.section for action in actor.actions] == ["actions", "actions", "reactions"]
    assert actor.actions[0].damage == "1d10+4"
    assert actor.actions[1].save_dc == 14 and actor.actions[1].resource_id == actor.resources[0].id
    assert actor.actions[0].resource_id == ""
    assert [(item.current, item.maximum) for item in actor.resources] == [(2, 2)]
    assert actor.resistances == ["некротический"]
    assert actor.condition_immunities == ["отравление"] and actor.immunities == []


def test_standard_english_colonless_labels_keep_hit_clause_and_legendary_section():
    source = """Young Red Dragon
Large dragon, chaotic evil
Armor Class 18 (natural armor)
Hit Points 178 (17d10 + 85)
Speed 40 ft., climb 40 ft., fly 80 ft.
STR DEX CON INT WIS CHA
23 (+6) 10 (+0) 21 (+5) 14 (+2) 11 (+0) 19 (+4)
Saving Throws DEX +4, CON +9, WIS +4, CHA +8
Skills Perception +8, Stealth +4
Damage Immunities fire
Senses blindsight 30 ft., darkvision 120 ft., passive Perception 18
Languages Common, Draconic
Challenge 10 (5,900 XP) Proficiency Bonus +4
Legendary Resistance (3/Day). If the dragon fails a saving throw, it can choose to succeed instead.
Magic Weapons. The dragon's weapon attacks are magical.
Actions
Bite. Melee Weapon Attack: +10 to hit, reach 10 ft., one target. Hit: 17 (2d10 + 6) piercing damage plus 3 (1d6) fire damage.
Fire Breath (Recharge 5-6). Each creature must make a DC 17 Dexterity saving throw, taking 56 (16d6) fire damage on a failed save, or half as much damage on a successful one.
Legendary Actions
Tail Attack. Melee Weapon Attack: +10 to hit, reach 15 ft., one target. Hit: 15 (2d8 + 6) bludgeoning damage."""
    result = parse_stat_block(source, "enemy")
    actor = result.combatant
    assert actor.class_name == ""
    assert actor.creature_size == "Large" and actor.creature_type == "dragon"
    assert actor.saves == {"dex": 4, "con": 9, "wis": 4, "cha": 8}
    assert actor.immunities == ["fire"] and actor.challenge_rating.startswith("10")
    assert [(x.name, x.damage, x.section) for x in actor.actions] == [
        ("Bite", "2d10+6", "actions"), ("Fire Breath", "16d6", "actions"), ("Tail Attack", "2d8+6", "legendary")
    ]
    assert actor.actions[1].recharge == "5-6" and actor.is_boss
    assert len(actor.traits) == 2 and actor.traits[0].startswith("Legendary Resistance")
    assert [(item.name, item.current, item.maximum) for item in actor.resources] == [("Legendary Resistance", 3, 3)]


def test_missing_fields_are_warned_not_invented_from_context():
    source = "Тень без чисел\nОписание существа и его повадок."
    result = parse_stat_block(source)
    assert result.combatant.name == "Тень без чисел"
    assert result.combatant.armor_class == 10
    assert result.combatant.hp == 10
    assert not result.combatant.actions
    assert len(result.warnings) >= 4
