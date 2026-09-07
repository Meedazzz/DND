"""Каталог состояний D&D 5e для трекера «Драконьей Саги».

Пятнадцать базовых состояний редакций 2014/2024, плюс служебные отметки
боя («Стабилизирован», «Мёртв»), которые движок выставляет автоматически
при спасбросках от смерти. Тексты краткие и нейтральные: трактовка
спорных случаев остаётся за мастером стола.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Condition:
    name_ru: str
    name_en: str
    summary: str
    special: bool = False  # служебная отметка, а не правило из книги


CATALOG: tuple[Condition, ...] = (
    Condition("Без сознания", "Unconscious", "Недееспособен, падает ничком; атаки вблизи по нему критуют."),
    Condition("Испуганный", "Frightened", "Помеха проверкам и атакам, пока источник страха в поле зрения; нельзя добровольно приближаться."),
    Condition("Истощение", "Exhaustion", "Накопительные уровни штрафов; шестой уровень — смерть."),
    Condition("Невидимый", "Invisible", "Атаки по нему с помехой, его атаки с преимуществом."),
    Condition("Недееспособный", "Incapacitated", "Не может совершать действия, бонусные действия и реакции."),
    Condition("Оглушённый", "Deafened", "Автоматически проваливает проверки, требующие слуха."),
    Condition("Окаменевший", "Petrified", "Недееспособен, сопротивление всему урону, атаки по нему с преимуществом."),
    Condition("Опутанный", "Restrained", "Скорость 0; атаки по нему с преимуществом, его атаки и спасброски ЛОВ с помехой."),
    Condition("Ослеплённый", "Blinded", "Атаки с помехой, атаки по нему с преимуществом; проваливает проверки зрения."),
    Condition("Отравленный", "Poisoned", "Помеха броскам атаки и проверкам характеристик."),
    Condition("Очарованный", "Charmed", "Не может вредить очарователю; тот получает преимущество в общении."),
    Condition("Ошеломлённый", "Stunned", "Недееспособен; атаки по нему с преимуществом, проваливает спасброски СИЛ/ЛОВ."),
    Condition("Парализованный", "Paralyzed", "Ошеломлён; атаки в упор по нему автоматически критуют."),
    Condition("Сбитый с ног", "Prone", "Лежит ничком: его атаки с помехой; вблизи по нему бьют с преимуществом, издалека — с помехой."),
    Condition("Схваченный", "Grappled", "Скорость 0; состояние кончается, если схвативший недееспособен."),
    Condition("Стабилизирован", "Stabilized", "Три успешных спасброска от смерти: не умирает, но остаётся при 0 ОЗ.", True),
    Condition("Мёртв", "Dead", "Три провала спасбросков от смерти. Воскрешение — за мастером.", True),
)

_BY_RU = {c.name_ru.lower(): c for c in CATALOG}
_BY_EN = {c.name_en.lower(): c for c in CATALOG}


def all() -> tuple[Condition, ...]:
    return CATALOG


def names() -> list[str]:
    return [c.name_ru for c in CATALOG]


def find(query: str) -> Condition | None:
    """Точный поиск по русскому или английскому имени (без регистра)."""
    key = query.strip().lower()
    if not key:
        return None
    return _BY_RU.get(key) or _BY_EN.get(key)


def search(query: str) -> list[Condition]:
    """Нечёткий поиск для диалога: подстрока по RU/EN имени и описанию."""
    key = query.strip().lower()
    if not key:
        return list(CATALOG)
    return [
        c for c in CATALOG
        if key in c.name_ru.lower() or key in c.name_en.lower() or key in c.summary.lower()
    ]


def describe(name: str) -> str:
    """Однострочная подсказка для подписей и всплывающих текстов."""
    condition = find(name)
    return f"{condition.name_ru}: {condition.summary}" if condition else name


def split_known(entries: list[str]) -> tuple[list[str], list[str]]:
    """Разделить список состояний участника на каталоговые и свои (пустые игнорируются)."""
    known, custom = [], []
    for entry in entries:
        if not entry or not entry.strip():
            continue
        (known if find(entry) else custom).append(entry)
    return known, custom
