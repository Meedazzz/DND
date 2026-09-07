"""Реестр встроенных художественных ресурсов «Драконьей Саги».

Сцена и стандартные портретные заглушки рисуются как оригинальные
иконки-заполнители и поставляются вместе с приложением в каталоге
``dragon_saga/resources``. Пользовательские изображения всегда имеют
приоритет: этот модуль лишь возвращает нейтральную заглушку для
участника, у которого нет собственного файла.

Ресурсы не хранятся в сохранениях кампании: подбор заглушки выполняется
в момент отрисовки, поэтому JSON-стол остаётся переносимым между
компьютерами и сетевыми участниками.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # без импорта Qt и models на этапе анализа
    from .models import Combatant


def resources_root() -> Path:
    """Каталог ресурсов и в исходниках, и в PyInstaller-сборке."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled) / "dragon_saga" / "resources"
    return Path(__file__).resolve().parent / "resources"


ART: dict[str, str] = {
    "hero_warrior": "portraits/hero_warrior.png",
    "hero_ranger": "portraits/hero_ranger.png",
    "hero_mage": "portraits/hero_mage.png",
    "hero_bard": "portraits/hero_bard.png",
    "hero_rogue": "portraits/hero_rogue.png",
    "hero_generic": "portraits/hero_generic.png",
    "enemy_mob": "portraits/enemy_mob.png",
    "enemy_elite": "portraits/enemy_elite.png",
    "enemy_boss": "portraits/enemy_boss.png",
    "backdrop_battle": "scene/backdrop_battle.png",
    "banner_logo": "scene/banner_logo.png",
}

# Узнаваемые архетипы стартовой сцены и типовые классы героев.
_ARCHETYPE_ALIASES: tuple[tuple[str, str], ...] = (
    ("северный страж", "hero_warrior"),
    ("следопыт перевала", "hero_ranger"),
    ("хранительница рун", "hero_mage"),
    ("певчая зари", "hero_bard"),
    ("странник", "hero_rogue"),
    ("воин", "hero_warrior"),
    ("fighter", "hero_warrior"),
    ("страж", "hero_warrior"),
    ("следопыт", "hero_ranger"),
    ("рейнджер", "hero_ranger"),
    ("ranger", "hero_ranger"),
    ("охотник", "hero_ranger"),
    ("волшебник", "hero_mage"),
    ("маг", "hero_mage"),
    ("чародей", "hero_mage"),
    ("wizard", "hero_mage"),
    ("mage", "hero_mage"),
    ("sorcerer", "hero_mage"),
    ("бард", "hero_bard"),
    ("bard", "hero_bard"),
    ("пев", "hero_bard"),
    ("плут", "hero_rogue"),
    ("rogue", "hero_rogue"),
    ("странник", "hero_rogue"),
    ("жрец", "hero_generic"),
    ("cleric", "hero_generic"),
    ("паладин", "hero_warrior"),
    ("paladin", "hero_warrior"),
    ("warlock", "hero_mage"),
    ("колдун", "hero_mage"),
)


def art_path(key: str) -> Path:
    """Абсолютный путь к ресурсу по ключу из :data:`ART`."""
    if key not in ART:
        raise KeyError(f"Неизвестный ресурс: {key}")
    return resources_root() / ART[key]


def art_available(key: str) -> bool:
    try:
        return art_path(key).is_file()
    except KeyError:
        return False


def backdrop_path() -> Path | None:
    return art_path("backdrop_battle") if art_available("backdrop_battle") else None


def banner_path() -> Path | None:
    return art_path("banner_logo") if art_available("banner_logo") else None


def placeholder_key(side: str, rank: str = "", is_boss: bool = False) -> str:
    """Ключ заглушки по стороне и рангу участника."""
    if is_boss or rank == "boss":
        return "enemy_boss"
    if side == "hero":
        return "hero_generic"
    return "enemy_elite" if rank == "elite" else "enemy_mob"


def _alias_lookup(name: str, class_name: str) -> str:
    haystacks = (name.strip().lower(), class_name.strip().lower())
    for needle, key in _ARCHETYPE_ALIASES:
        for hay in haystacks:
            if hay and needle in hay:
                return key
    return ""


def portrait_path_for(combatant: "Combatant") -> Path | None:
    """Заглушка портрета для участника без собственного изображения.

    Порядок: узнаваемый архетип (имя/класс) → заглушка ранга/стороны.
    Файл из ``combatant.image_path`` сюда не попадает: интерфейс
    проверяет его первым.
    """
    key = _alias_lookup(combatant.name, combatant.class_name)
    if not key:
        key = placeholder_key(combatant.side, getattr(combatant, "rank", ""), combatant.is_boss)
    candidate = art_path(key)
    if candidate.is_file():
        return candidate
    fallback = art_path(placeholder_key(combatant.side, getattr(combatant, "rank", ""), combatant.is_boss))
    return fallback if fallback.is_file() else None


def manifest() -> list[str]:
    """Отсутствующие ресурсы — полезно для самодиагностики сборки."""
    return [key for key in ART if not art_available(key)]
