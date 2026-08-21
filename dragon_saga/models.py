from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import uuid4


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
ZONES = ("T1", "A1", "A2", "T2")


@dataclass
class Action:
    id: str = field(default_factory=lambda: uid("act"))
    name: str = "Действие"
    kind: str = "attack"  # attack, save, damage, heal, utility
    attack_bonus: int | None = None
    damage: str = "1d4"
    damage_type: str = ""
    save_ability: str = ""
    save_dc: int | None = None
    half_on_save: bool = False
    range_ft: int = 5
    resource_id: str = ""
    section: str = "actions"  # actions, bonus, reactions, legendary
    recharge: str = ""
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Action":
        allowed = cls.__dataclass_fields__
        return cls(**{k: v for k, v in raw.items() if k in allowed})


@dataclass
class Resource:
    id: str = field(default_factory=lambda: uid("res"))
    name: str = "Ресурс"
    current: int = 1
    maximum: int = 1
    recovery: str = "long"

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Resource":
        allowed = cls.__dataclass_fields__
        return cls(**{k: v for k, v in raw.items() if k in allowed})


@dataclass
class Combatant:
    id: str = field(default_factory=lambda: uid("char"))
    name: str = "Безымянный"
    side: str = "hero"
    class_name: str = ""
    race: str = ""
    level: int = 1
    armor_class: int = 10
    hp: int = 10
    max_hp: int = 10
    temp_hp: int = 0
    speed: int = 30
    initiative_bonus: int = 0
    proficiency: int = 2
    stats: dict[str, int] = field(default_factory=lambda: {key: 10 for key in ABILITIES})
    saves: dict[str, int] = field(default_factory=dict)
    skills: dict[str, int] = field(default_factory=dict)
    creature_size: str = ""
    creature_type: str = ""
    alignment: str = ""
    challenge_rating: str = ""
    resistances: list[str] = field(default_factory=list)
    vulnerabilities: list[str] = field(default_factory=list)
    immunities: list[str] = field(default_factory=list)
    condition_immunities: list[str] = field(default_factory=list)
    senses: str = ""
    languages: str = ""
    traits: list[str] = field(default_factory=list)
    reactions: list[str] = field(default_factory=list)
    legendary_actions: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    resources: list[Resource] = field(default_factory=list)
    source_text: str = ""
    audit: list[str] = field(default_factory=list)
    image_path: str = ""
    model_path: str = ""
    model_scale: int = 100
    owner_id: str = ""
    is_boss: bool = False
    telegraph: str = ""
    telegraph_dc: int = 14
    telegraph_counter: str = ""
    hit_die: int = 8
    hit_dice_current: int = 1
    hit_dice_max: int = 1

    def __post_init__(self) -> None:
        self.max_hp = max(1, int(self.max_hp))
        self.hp = max(0, min(int(self.hp), self.max_hp))
        self.armor_class = max(0, int(self.armor_class))
        self.speed = max(0, int(self.speed))
        self.stats = {key: int(self.stats.get(key, 10)) for key in ABILITIES}
        self.saves = {str(key): int(value) for key, value in self.saves.items()}
        self.skills = {str(key): int(value) for key, value in self.skills.items()}
        for attr in ("resistances", "vulnerabilities", "immunities", "condition_immunities", "traits", "reactions", "legendary_actions", "conditions"):
            setattr(self, attr, [str(x) for x in getattr(self, attr)])
        self.actions = [x if isinstance(x, Action) else Action.from_dict(x) for x in self.actions]
        self.resources = [x if isinstance(x, Resource) else Resource.from_dict(x) for x in self.resources]

    @property
    def alive(self) -> bool:
        return self.hp > 0

    def ability_mod(self, ability: str) -> int:
        return (self.stats.get(ability, 10) - 10) // 2

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Combatant":
        allowed = cls.__dataclass_fields__
        data = {k: v for k, v in raw.items() if k in allowed}
        data["actions"] = [Action.from_dict(x) for x in raw.get("actions", [])]
        data["resources"] = [Resource.from_dict(x) for x in raw.get("resources", [])]
        return cls(**data)


@dataclass
class BattleState:
    positions: dict[str, str] = field(default_factory=dict)
    initiative: list[dict[str, Any]] = field(default_factory=list)
    turn_index: int = 0
    round_number: int = 0
    active: bool = False
    target_id: str = ""
    movement_left: dict[str, int] = field(default_factory=dict)
    turn_start_zone: dict[str, str] = field(default_factory=dict)
    flags: dict[str, dict[str, Any]] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "BattleState":
        allowed = cls.__dataclass_fields__
        return cls(**{k: v for k, v in raw.items() if k in allowed})


@dataclass
class Campaign:
    schema: str = "dragon-saga-python"
    version: str = "4.0.0"
    title: str = "Драконья Сага"
    edition: str = "2024"
    role: str = "gm"
    assigned_character_id: str = ""
    characters: list[Combatant] = field(default_factory=list)
    battle: BattleState = field(default_factory=BattleState)
    recent_rolls: list[str] = field(default_factory=list)
    assets: list[dict[str, str]] = field(default_factory=list)

    def character(self, character_id: str) -> Combatant | None:
        return next((x for x in self.characters if x.id == character_id), None)

    def positioned(self, zone: str) -> list[Combatant]:
        return [x for x in self.characters if self.battle.positions.get(x.id) == zone]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Campaign":
        if raw.get("schema") != "dragon-saga-python":
            raise ValueError("Это не сохранение «Драконьей Саги» Python")
        allowed = cls.__dataclass_fields__
        data = {k: v for k, v in raw.items() if k in allowed and k not in {"characters", "battle"}}
        data["characters"] = [Combatant.from_dict(x) for x in raw.get("characters", [])]
        data["battle"] = BattleState.from_dict(raw.get("battle", {}))
        return cls(**data)


def starter_campaign() -> Campaign:
    archetypes = [
        ("Северный страж", "Воин", 17, 34, "Длинный меч", 5, "1d8+3", "T1"),
        ("Следопыт перевала", "Следопыт", 15, 27, "Охотничий лук", 5, "1d8+3", "T1"),
        ("Хранительница рун", "Волшебник", 13, 20, "Ледяной луч", 5, "1d8+3", "A1"),
        ("Певчая зари", "Бард", 14, 24, "Резкий аккорд", 5, "1d6+3", "A1"),
        ("Странник", "Плут", 15, 25, "Короткий клинок", 5, "1d6+3", "reserve"),
    ]
    campaign = Campaign()
    for index, (name, cls_name, ac, hp, action_name, bonus, damage, zone) in enumerate(archetypes):
        hero = Combatant(
            name=name,
            class_name=cls_name,
            armor_class=ac,
            hp=hp,
            max_hp=hp,
            initiative_bonus=2 + (index % 2),
            stats={"str": 14, "dex": 15, "con": 14, "int": 12, "wis": 13, "cha": 12},
            actions=[Action(name=action_name, attack_bonus=bonus, damage=damage, range_ft=60 if "лук" in action_name or "луч" in action_name else 5)],
            source_text="Нейтральный стартовый лист-заполнитель. Замените его импортом собственного персонажа.",
            audit=["Стартовый заполнитель: не является готовым персонажем кампании."],
        )
        campaign.characters.append(hero)
        campaign.battle.positions[hero.id] = zone
    campaign.battle.log.append("Сцена готова. Четыре героя выставлены, один находится в резерве.")
    return campaign
