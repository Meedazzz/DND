"""
Стратегический режим — армия на армию, юниты на юниты, вид сверху.

С версии 5.1.0 — полноценный бой на глобальной карте:
- квадратная и гексагональная сетка, переключаемая в настройках;
- токены юнитов, перемещаемые по клеткам/гексам с учётом скорости;
- дистанция в клетках (1 клетка = 5 футов по умолчанию);
- атаки d20 против КД с критами, дистанцией и флангом;
- инициатива d20 + ЛОВ, очередь ходов, определение победителя.

Математика боя живёт в :mod:`dragon_saga.strategic_rules` (без Qt,
покрыта тестами); здесь — поле, лагеря и журнал.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable
from uuid import uuid4

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QPainterPath, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import Combatant
from .strategic_rules import (
    GRID_HEX,
    GRID_SQUARE,
    CellPos,
    StrikeResult,
    battle_outcome,
    can_move,
    flanking,
    in_range,
    resolve_strike,
    roll_initiative,
)


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


# ------------------------------------------------------------------
# Токен юнита (заглушка, позже — полноценный юнит с ОЗ, атакой, скоростью, дистанцией)
# ------------------------------------------------------------------


@dataclass
class UnitToken:
    """Юнит в стратегическом режиме. Пока без событий, позже будет с логикой боя."""

    id: str = field(default_factory=lambda: uid("unit"))
    name: str = "Юнит"
    side: str = "hero"
    hp: int = 10
    max_hp: int = 10
    ac: int = 10
    attack_bonus: int = 0
    damage: str = "1d6"
    damage_type: str = ""
    speed_ft: int = 30  # скорость в футах (переводится в клетки через cell_ft)
    range_ft: int = 5  # дистанция атаки в футах
    dex_mod: int = 0  # модификатор ЛОВ для инициативы
    actions_per_turn: int = 1  # сколько действий у юнита за ход
    icon_path: str = ""  # путь к иконке (пока пусто — позже загрузить из LSS или загрузить файл)
    conditions: list[str] = field(default_factory=list)
    selected: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "side": self.side,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "ac": self.ac,
            "attack_bonus": self.attack_bonus,
            "damage": self.damage,
            "damage_type": self.damage_type,
            "speed_ft": self.speed_ft,
            "range_ft": self.range_ft,
            "dex_mod": self.dex_mod,
            "actions_per_turn": self.actions_per_turn,
            "icon_path": self.icon_path,
            "conditions": self.conditions,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnitToken":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ------------------------------------------------------------------
# Поле: сетка клеток (квадратная) и гексагональная сетка
# ------------------------------------------------------------------


@dataclass
class Cell:
    """Клетка на сетке. Пока заглушка — позже будет высота, проходимость, окружение."""

    row: int
    col: int
    unit_id: str | None = None
    passable: bool = True
    elevation: int = 0  # по умолчанию 0 (позже — высота для прикрытия)


class GridField(QFrame):
    """Квадратное поле с клетками. Пока заглушка, позже — гексагональная сетка и движение."""

    cell_selected = Signal(int, int)  # row, col

    def __init__(self, rows: int = 12, cols: int = 12, cell_size: int = 50, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("battlefield")
        self.rows = rows
        self.cols = cols
        self.cell_size = cell_size
        self.cells: list[list[Cell]] = [
            [Cell(row=r, col=c, passable=True) for c in range(cols)] for r in range(rows)
        ]
        self.setMinimumSize(cols * cell_size, rows * cell_size)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grid_type: str = GRID_SQUARE
        self._selected: tuple[int, int] | None = None
        self._units: dict[str, UnitToken] = {}
        self._hex_size: float = 20.0
        self._hex_origin: tuple[float, float] = (0.0, 0.0)

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.fillRect(rect, QColor("#0c0a0b"))
        if self.grid_type == GRID_HEX:
            self._paint_hex(painter, rect)
        else:
            self._paint_square(painter, rect)
        painter.end()

    # -- квадратная сетка -------------------------------------------

    def _square_geometry(self, rect):  # type: ignore[no-untyped-def]
        padding = 12
        left = rect.left() + padding
        top = rect.top() + padding
        cell_w = (rect.width() - padding * 2) / max(1, self.cols)
        cell_h = (rect.height() - padding * 2) / max(1, self.rows)
        return left, top, cell_w, cell_h

    def _paint_square(self, painter, rect):  # type: ignore[no-untyped-def]
        left, top, cell_w, cell_h = self._square_geometry(rect)
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cells[r][c]
                x = int(left + c * cell_w)
                y = int(top + r * cell_h)
                w, h = int(cell_w), int(cell_h)
                if cell.unit_id:
                    painter.fillRect(x + 1, y + 1, w - 2, h - 2, QColor("#3a2a26"))
                    painter.setPen(QPen(QColor("#c9a77a"), 1))
                    painter.drawRect(x + 1, y + 1, w - 2, h - 2)
                elif not cell.passable:
                    painter.setPen(QPen(QColor("#4a2626"), 1))
                    painter.setBrush(QColor("#241414"))
                    painter.drawRect(x, y, w - 1, h - 1)
                else:
                    painter.setPen(QPen(QColor("#2a2523"), 1))
                    painter.setBrush(QColor("#1a1614"))
                    painter.drawRect(x, y, w - 1, h - 1)
        if self._selected is not None:
            r, c = self._selected
            x = int(left + c * cell_w)
            y = int(top + r * cell_h)
            painter.setPen(QPen(QColor("#d98c4e"), 2))
            painter.drawRect(x + 1, y + 1, int(cell_w) - 2, int(cell_h) - 2)
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c].unit_id:
                    cx = left + c * cell_w + cell_w / 2
                    cy = top + r * cell_h + cell_h / 2
                    self._paint_token(painter, cx, cy, self.cells[r][c].unit_id, min(cell_w, cell_h))

    # -- гексагональная сетка (pointy-top, odd-r) --------------------

    def _hex_geometry(self, rect):  # type: ignore[no-untyped-def]
        import math

        margin = 12
        w = max(50, rect.width() - margin * 2)
        h = max(50, rect.height() - margin * 2)
        size = min(w / (math.sqrt(3) * (self.cols + 0.5)), h / (1.5 * self.rows + 0.5))
        size = max(8.0, size)
        total_w = math.sqrt(3) * size * (self.cols + 0.5)
        total_h = size * (1.5 * self.rows + 0.5)
        ox = rect.left() + (rect.width() - total_w) / 2
        oy = rect.top() + (rect.height() - total_h) / 2
        return size, ox, oy

    def _hex_center(self, row: int, col: int, size: float, ox: float, oy: float) -> tuple[float, float]:
        import math

        x = ox + math.sqrt(3) * size * (col + 0.5 + 0.5 * (row & 1))
        y = oy + size * (1.5 * row + 1)
        return x, y

    def _paint_hex(self, painter, rect):  # type: ignore[no-untyped-def]
        import math

        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF

        size, ox, oy = self._hex_geometry(rect)
        self._hex_size = size
        self._hex_origin = (ox, oy)
        for r in range(self.rows):
            for c in range(self.cols):
                cx, cy = self._hex_center(r, c, size, ox, oy)
                points = []
                for i in range(6):
                    angle = math.radians(60 * i - 30)
                    points.append(QPointF(cx + size * 0.95 * math.cos(angle), cy + size * 0.95 * math.sin(angle)))
                poly = QPolygonF(points)
                cell = self.cells[r][c]
                if self._selected == (r, c):
                    painter.setPen(QPen(QColor("#d98c4e"), 2))
                    painter.setBrush(QColor("#3a2a20"))
                elif cell.unit_id:
                    painter.setPen(QPen(QColor("#c9a77a"), 1))
                    painter.setBrush(QColor("#3a2a26"))
                elif not cell.passable:
                    painter.setPen(QPen(QColor("#4a2626"), 1))
                    painter.setBrush(QColor("#241414"))
                else:
                    painter.setPen(QPen(QColor("#2a2523"), 1))
                    painter.setBrush(QColor("#1a1614"))
                painter.drawPolygon(poly)
                if cell.unit_id:
                    self._paint_token(painter, cx, cy, cell.unit_id, size * 1.2)

    # -- токены ------------------------------------------------------

    def _paint_token(self, painter, cx: float, cy: float, unit_id: str, span: float) -> None:  # type: ignore[no-untyped-def]
        unit = self._units.get(unit_id)
        side = unit.side if unit else "hero"
        radius = max(6.0, min(16.0, span / 3.2))
        color = QColor("#7ab87a") if side == "hero" else QColor("#c65a4a")
        if unit is not None and unit.hp <= 0:
            color = QColor("#5a5a5a")
        painter.setPen(QPen(color, 2))
        painter.setBrush(QColor("#141010"))
        painter.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        if unit is not None:
            painter.setPen(color)
            font = QFont("Georgia", max(7, int(radius * 0.9)))
            font.setBold(True)
            painter.setFont(font)
            initial = (unit.name.strip() or "?")[:1].upper()
            painter.drawText(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2),
                             Qt.AlignmentFlag.AlignCenter, initial)
            hp_font = QFont("Segoe UI", 7)
            painter.setFont(hp_font)
            painter.setPen(QColor("#d9cec4"))
            painter.drawText(int(cx - radius - 8), int(cy + radius), int(radius * 2) + 16, 12,
                             Qt.AlignmentFlag.AlignCenter, f"{unit.hp}/{unit.max_hp}")

    def mousePressEvent(self, event):  # type: ignore[override]
        if self.grid_type == GRID_HEX:
            self._click_hex(event)
        else:
            self._click_square(event)

    def _click_square(self, event) -> None:  # type: ignore[no-untyped-def]
        rect = self.rect().adjusted(2, 2, -2, -2)
        left, top, cell_w, cell_h = self._square_geometry(rect)
        c = min(self.cols - 1, max(0, int((event.pos().x() - left) / cell_w)))
        r = min(self.rows - 1, max(0, int((event.pos().y() - top) / cell_h)))
        self._selected = (r, c)
        self.cell_selected.emit(r, c)
        self.update()

    def _click_hex(self, event) -> None:  # type: ignore[no-untyped-def]
        import math

        rect = self.rect().adjusted(2, 2, -2, -2)
        size, ox, oy = self._hex_geometry(rect)
        px, py = event.pos().x(), event.pos().y()
        best: tuple[int, int] | None = None
        best_dist = size * 1.1
        for r in range(self.rows):
            for c in range(self.cols):
                cx, cy = self._hex_center(r, c, size, ox, oy)
                dist = math.hypot(px - cx, py - cy)
                if dist < best_dist:
                    best_dist = dist
                    best = (r, c)
        if best is not None:
            self._selected = best
            self.cell_selected.emit(*best)
            self.update()


    def set_unit_on_cell(self, unit_id: str, row: int, col: int) -> None:
        """Переместить юнит на клетку. Убрать с предыдущей клетки."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c].unit_id == unit_id:
                    self.cells[r][c].unit_id = None
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self.cells[row][col].unit_id = unit_id
            self.update()

    def set_grid_type(self, grid_type: str) -> None:
        """Переключить отрисовку: 'square' или 'hex'."""
        self.grid_type = GRID_HEX if grid_type == GRID_HEX else GRID_SQUARE
        self.update()

    def set_units(self, units: dict[str, "UnitToken"]) -> None:
        """Передать токены для отрисовки имён, сторон и ОЗ."""
        self._units = dict(units)
        self.update()

    def unit_at(self, row: int, col: int) -> str | None:
        """Id юнита на клетке или None."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            return self.cells[row][col].unit_id
        return None

    def occupied_cells(self) -> dict[str, tuple[int, int]]:
        """Вернуть карту id юнита → (row, col)."""
        result: dict[str, tuple[int, int]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c].unit_id:
                    result[self.cells[r][c].unit_id] = (r, c)
        return result

    def reset_selection(self) -> None:
        self._selected = None
        self.update()


# ------------------------------------------------------------------
# Лагерь (армия)
# ------------------------------------------------------------------


@dataclass
class Army:
    """Армия — набор юнитов + название стороны."""

    side: str = "hero"
    name: str = "Сторона"
    units: list[UnitToken] = field(default_factory=list)
    win_count: int = 0
    losses: int = 0

    def alive_units(self) -> list[UnitToken]:
        return [u for u in self.units if u.hp > 0]

    def total_hp(self) -> int:
        return sum(u.hp for u in self.units)

    def max_hp(self) -> int:
        return sum(u.max_hp for u in self.units)

    def total_actions(self) -> int:
        return sum(u.actions_per_turn for u in self.alive_units())


# ------------------------------------------------------------------
# Стратегическая битва (заглушка)
# ------------------------------------------------------------------


@dataclass
class StrategicBattle:
    """Стратегическая битва — два лагеря + поле + очередь."""

    armies: dict[str, Army] = field(default_factory=dict)  # side → Army
    grid: GridField | None = None
    turn_index: int = 0
    current_turn: str = "hero"
    active: bool = False
    log: list[str] = field(default_factory=list)
    initiative_order: list[str] = field(default_factory=list)  # id юнитов в порядке инициативы
    cell_ft: int = 5  # футов в одной клетке
    grid_type: str = GRID_SQUARE  # 'square' | 'hex'
    randint: Callable[[int, int], int] | None = None  # инжекция кубов (тесты/симуляции)

    def _dice(self) -> Callable[[int, int], int]:
        return self.randint or random.randint

    def current_army(self) -> Army | None:
        if self.current_turn not in self.armies:
            return None
        return self.armies[self.current_turn]

    def unit_by_id(self, unit_id: str) -> UnitToken | None:
        for army in self.armies.values():
            for unit in army.units:
                if unit.id == unit_id:
                    return unit
        return None

    def all_units(self) -> list[UnitToken]:
        result: list[UnitToken] = []
        for army in self.armies.values():
            result.extend(army.units)
        return result

    def position_of(self, unit_id: str) -> CellPos | None:
        if self.grid is None:
            return None
        pos = self.grid.occupied_cells().get(unit_id)
        return CellPos(row=pos[0], col=pos[1]) if pos else None

    def current_unit(self) -> UnitToken | None:
        if not self.initiative_order:
            return None
        self.turn_index %= len(self.initiative_order)
        return self.unit_by_id(self.initiative_order[self.turn_index])

    def roll_initiative(self) -> list[tuple[str, int]]:
        """Инициатива d20 + ЛОВ по живым юнитам; возвращает [(id, итог)]."""
        entries = [(u.id, u.dex_mod) for u in self.all_units() if u.hp > 0]
        ordered = roll_initiative(entries, self._dice())
        self.initiative_order = [unit_id for unit_id, _ in ordered]
        self.turn_index = 0
        first = self.current_unit()
        if first is not None:
            self.current_turn = first.side
        for unit_id, total in ordered:
            unit = self.unit_by_id(unit_id)
            if unit is not None:
                self.log.append(f"Инициатива · {unit.name}: {total} (ЛОВ {unit.dex_mod:+d})")
        return ordered

    def next_turn(self) -> None:
        if not self.active or not self.initiative_order:
            return
        for _ in range(len(self.initiative_order)):
            self.turn_index = (self.turn_index + 1) % len(self.initiative_order)
            current = self.current_unit()
            if current is not None and current.hp > 0:
                self.current_turn = current.side
                self.log.append(f"Ход: {current.name} ({'герои' if current.side == 'hero' else 'враги'})")
                return
        self.log.append("Ходить некому: все юниты выбыли")

    def move_unit(self, unit_id: str, row: int, col: int) -> tuple[bool, str]:
        """Переместить юнита с проверкой скорости и занятости клетки."""
        unit = self.unit_by_id(unit_id)
        if unit is None:
            return False, "юнит не найден"
        if self.grid is None:
            return False, "поле не готово"
        if not (0 <= row < self.grid.rows and 0 <= col < self.grid.cols):
            return False, "клетка за пределами поля"
        origin = self.position_of(unit_id)
        if origin is None:
            return False, "юнит не выставлен на поле"
        cell = self.grid.cells[row][col]
        occupied = cell.unit_id is not None and cell.unit_id != unit_id
        ok, reason = can_move(origin, CellPos(row=row, col=col), unit.speed_ft,
                              self.grid_type, self.cell_ft, cell.passable, occupied)
        if not ok:
            return False, reason
        self.grid.set_unit_on_cell(unit_id, row, col)
        self.log.append(f"{unit.name}: ({origin.row}, {origin.col}) → ({row}, {col})")
        return True, "ход разрешён"

    def attack(self, attacker_id: str, target_id: str) -> StrikeResult:
        """Удар юнита по юниту: дистанция, фланг, кубы, добивание."""
        attacker = self.unit_by_id(attacker_id)
        target = self.unit_by_id(target_id)
        if attacker is None or target is None:
            raise ValueError("Атакующий или цель не найдены")
        if attacker.side == target.side:
            raise ValueError("Цельтесь во вражеского юнита")
        if attacker.hp <= 0:
            raise ValueError(f"{attacker.name} выбыл из боя")
        if target.hp <= 0:
            raise ValueError(f"{target.name} уже уничтожен")
        origin = self.position_of(attacker_id)
        foe_pos = self.position_of(target_id)
        if origin is None or foe_pos is None:
            raise ValueError("Оба юнита должны стоять на поле")
        reaches, dist_ft = in_range(origin, foe_pos, attacker.range_ft, self.grid_type, self.cell_ft)
        if not reaches:
            raise ValueError(f"{target.name} вне дистанции: {dist_ft} фт при досягаемости {attacker.range_ft} фт")
        allies = [pos for u in self.all_units()
                  if u.side == attacker.side and u.id != attacker.id and u.hp > 0
                  and (pos := self.position_of(u.id)) is not None]
        advantage = 1 if flanking(origin, foe_pos, allies, self.grid_type) else 0
        if advantage:
            self.log.append(f"Фланг! {attacker.name} бьёт с преимуществом")
        result = resolve_strike(attacker.name, attacker.attack_bonus, attacker.damage,
                                target.name, target.ac, target.hp, self._dice(), advantage)
        target.hp = result.target_hp_left
        self.log.append(result.detail)
        if result.destroyed and self.grid is not None:
            for r in range(self.grid.rows):
                for c in range(self.grid.cols):
                    if self.grid.cells[r][c].unit_id == target.id:
                        self.grid.cells[r][c].unit_id = None
            self.grid.update()
        winner = self.check_winner()
        if winner is not None:
            self.active = False
            if winner == "draw":
                self.log.append("Битва завершена: взаимное уничтожение!")
            else:
                name = "Герои" if winner == "hero" else "Враги"
                self.log.append(f"Битва завершена: побеждают {name}!")
        return result

    def check_winner(self) -> str | None:
        """Победитель ('hero'/'enemy'/'draw') или None — бой продолжается."""
        totals = {side: sum(u.hp for u in army.units if u.hp > 0) for side, army in self.armies.items()}
        return battle_outcome(totals)

    def end_battle(self) -> None:
        self.active = False
        self.log.append("Битва завершена")


class UnitEditorDialog(QDialog):
    """Диалог редактирования юнита в стратегическом режиме — редактируемые параметры."""

    def __init__(self, unit: UnitToken | None = None, side: str = "hero", parent: QWidget | None = None):
        super().__init__(parent)
        self.unit = unit or UnitToken(side=side)
        self.side = side
        self.setWindowTitle(f"Редактирование юнита · {'Герои' if side == 'hero' else 'Враги'}")
        self.resize(500, 650)
        self.init_ui()

    def init_ui(self) -> None:
        from PySide6.QtWidgets import QDialogButtonBox, QFormLayout, QComboBox, QCheckBox

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.name_input = QLineEdit(self.unit.name)

        self.side_combo = QComboBox()
        self.side_combo.addItem("Герои", "hero")
        self.side_combo.addItem("Враги", "enemy")
        self.side_combo.setCurrentIndex(0 if self.side == "hero" else 1)

        self.hp_input = QSpinBox()
        self.hp_input.setRange(0, 999)
        self.hp_input.setValue(self.unit.hp)

        self.max_hp_input = QSpinBox()
        self.max_hp_input.setRange(1, 999)
        self.max_hp_input.setValue(self.unit.max_hp)

        self.ac_input = QSpinBox()
        self.ac_input.setRange(0, 99)
        self.ac_input.setValue(self.unit.ac)

        self.attack_input = QSpinBox()
        self.attack_input.setRange(-20, 40)
        self.attack_input.setValue(self.unit.attack_bonus)
        self.attack_input.setPrefix("+")

        self.dex_input = QSpinBox()
        self.dex_input.setRange(-10, 20)
        self.dex_input.setValue(self.unit.dex_mod)
        self.dex_input.setPrefix("+")

        self.damage_input = QLineEdit(self.unit.damage)

        self.damage_type_combo = QComboBox()
        damage_types = ["", "дробящий", "колющий", "рубящий", "огонь", "холод", "электричество", "кислота", "яд", "звук", "некротический", "излучение", "психический", "силовой"]
        self.damage_type_combo.addItems(damage_types)
        self.damage_type_combo.setCurrentIndex(damage_types.index(self.unit.damage_type) if self.unit.damage_type in damage_types else 0)

        self.speed_input = QSpinBox()
        self.speed_input.setRange(0, 200)
        self.speed_input.setValue(self.unit.speed_ft)
        self.speed_input.setSuffix(" футов")

        self.range_input = QSpinBox()
        self.range_input.setRange(0, 600)
        self.range_input.setValue(self.unit.range_ft)
        self.range_input.setSuffix(" футов")

        self.actions_input = QSpinBox()
        self.actions_input.setRange(0, 10)
        self.actions_input.setValue(self.unit.actions_per_turn)
        self.actions_input.setSuffix(" действий за ход")

        self.icon_input = QLineEdit(self.unit.icon_path)

        self.conditions_input = QLineEdit(", ".join(self.unit.conditions))

        self.melee_check = QCheckBox("Ближний бой")
        self.melee_check.setChecked(self.unit.range_ft <= 5)

        self.ranged_check = QCheckBox("Дальний бой")
        self.ranged_check.setChecked(self.unit.range_ft > 5)

        for label, widget in (
            ("Имя", self.name_input),
            ("Сторона", self.side_combo),
            ("Текущие ОЗ", self.hp_input),
            ("Максимум ОЗ", self.max_hp_input),
            ("КД", self.ac_input),
            ("Бонус атаки", self.attack_input),
            ("Мод. ЛОВ (инициатива)", self.dex_input),
            ("Урон (формула)", self.damage_input),
            ("Тип урона", self.damage_type_combo),
            ("Скорость", self.speed_input),
            ("Дистанция атаки", self.range_input),
            ("Действий за ход", self.actions_input),
            ("Значок (путь к файлу)", self.icon_input),
            ("Состояния (через запятую)", self.conditions_input),
        ):
            if widget:
                form.addRow(label, widget)
            else:
                form.addRow(label, widget)  # тип выпадающего списка уже добавлен

        layout.addLayout(form)

        # Чекбоксы режима атаки
        check_row = QHBoxLayout()
        check_row.addWidget(self.melee_check)
        check_row.addWidget(self.ranged_check)
        check_row.addStretch()
        layout.addLayout(check_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class StrategicStage(QWidget):
    """Заглушка стратегического режима. Позже — полноценный бой по клеткам с миникартой."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.battle = StrategicBattle()
        self.selected_unit_id: str | None = None
        self.target_unit_id: str | None = None
        self._shown_log = 0
        self.init_ui()
        self.init_field()
        self.init_armies()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        title = QLabel("СТРАТЕГИЧЕСКИЙ РЕЖИМ · Армия на армию")
        title.setObjectName("title")
        layout.addWidget(title)

        # Выбор типа сетки
        grid_type_label = QLabel("Тип поля:")
        grid_type_label.setObjectName("muted")
        self.grid_type_combo = QComboBox()
        self.grid_type_combo.addItems(["Квадратная сетка", "Гексагональная сетка"])
        self.grid_type_combo.setCurrentIndex(0)
        self.grid_type_combo.currentIndexChanged.connect(self._on_grid_type_changed)
        grid_type_layout = QHBoxLayout()
        grid_type_layout.addWidget(grid_type_label)
        grid_type_layout.addWidget(self.grid_type_combo)
        grid_type_layout.addStretch()
        layout.addLayout(grid_type_layout)

        # Настройки клетки
        settings_label = QLabel("Настройки клетки:")
        settings_label.setObjectName("muted")
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(QLabel("Размер клетки (футов):"))
        self.cell_size_spin = QSpinBox()
        self.cell_size_spin.setRange(1, 20)
        self.cell_size_spin.setValue(5)
        self.cell_size_spin.setSuffix(" футов")
        self.cell_size_spin.valueChanged.connect(lambda value: setattr(self.battle, "cell_ft", value))
        settings_layout.addWidget(self.cell_size_spin)
        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Поле
        self.field = GridField(rows=10, cols=10, cell_size=50)
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.field)
        self.turn_label = QLabel("Битва не начата: расставьте юнитов и нажмите «Начать битву».")
        self.turn_label.setWordWrap(True)
        self.turn_label.setObjectName("muted")
        layout.addWidget(self.turn_label)
        self.selection_label = QLabel("Атакующий: — · Цель: —")
        self.selection_label.setWordWrap(True)
        self.selection_label.setObjectName("muted")
        layout.addWidget(self.selection_label)

        # Панель лагерей
        armies_layout = QHBoxLayout()
        self.hero_army_widget = self._create_army_widget("hero", "Герои")
        self.enemy_army_widget = self._create_army_widget("enemy", "Враги")
        armies_layout.addWidget(self.hero_army_widget)
        armies_layout.addWidget(self.enemy_army_widget)
        layout.addLayout(armies_layout)

        # Лог боя
        log_label = QLabel("Лог боя:")
        log_label.setObjectName("muted")
        layout.addWidget(log_label)
        self.log_list = QListWidget()
        self.log_list.setMaximumHeight(150)
        layout.addWidget(self.log_list)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.start_button = QPushButton("Начать битву")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start_battle)
        self.step_button = QPushButton("Следующий ход")
        self.step_button.clicked.connect(self._next_turn)
        self.attack_button = QPushButton("⚔ Атаковать цель")
        self.attack_button.clicked.connect(self._attack_target)
        self.end_button = QPushButton("Завершить битву")
        self.end_button.clicked.connect(self._end_battle)
        self.reset_button = QPushButton("Сбросить поле")
        self.reset_button.clicked.connect(self._reset_field)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.step_button)
        buttons_layout.addWidget(self.attack_button)
        buttons_layout.addWidget(self.end_button)
        buttons_layout.addWidget(self.reset_button)
        layout.addLayout(buttons_layout)

    def _create_army_widget(self, side: str, name: str) -> QWidget:
        widget = QWidget()
        widget.setObjectName("panel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        header = QHBoxLayout()
        header_label = QLabel(f"ЛАГЕРЬ · {name.upper()}")
        header_label.setObjectName("section")
        header.addWidget(header_label)
        header.addStretch()

        add_unit_button = QPushButton("＋ Добавить юнит")
        add_unit_button.clicked.connect(lambda: self._add_unit(side))
        remove_unit_button = QPushButton("✕ Удалить юнит")
        remove_unit_button.clicked.connect(lambda: self._remove_unit(side))
        header.addWidget(add_unit_button)
        header.addWidget(remove_unit_button)
        layout.addLayout(header)

        self.unit_list = QListWidget()
        self.unit_list.setMinimumHeight(120)
        self.unit_list.currentRowChanged.connect(
            lambda row: self._select_unit(side, row)
        )
        layout.addWidget(self.unit_list)

        stats_label = QLabel("Юнитов: 0 · ОЗ: 0/0 · Действий: 0")
        stats_label.setObjectName("muted")
        stats_label.setWordWrap(True)
        layout.addWidget(stats_label)

        edit_army_button = QPushButton("Редактировать состав")
        edit_army_button.clicked.connect(lambda: self._edit_army(side))
        layout.addWidget(edit_army_button)

        self._army_side = side
        self._army_name = name
        return widget

    def init_field(self) -> None:
        self.battle.grid = self.field
        self.field.cell_selected.connect(self._on_cell_selected)
        self.field.reset_selection()

    def init_armies(self) -> None:
        self.battle.armies["hero"] = Army(side="hero", name="Герои")
        self.battle.armies["enemy"] = Army(side="enemy", name="Враги")
        self.battle.initiative_order = []
        self._refresh_army_widgets()

    def _refresh_army_widgets(self) -> None:
        self._refresh_unit_list(self.hero_army_widget, "hero")
        self._refresh_unit_list(self.enemy_army_widget, "enemy")
        self.field.set_units({u.id: u for u in self.battle.all_units()})
        self._update_selection_hint()

    def _refresh_unit_list(self, widget: QWidget, side: str) -> None:
        list_widget = widget.findChild(QListWidget)
        if list_widget:
            list_widget.clear()
            army = self.battle.armies.get(side)
            if army:
                for unit in army.units:
                    marker = " ▶" if unit.id == self._current_unit_id() else ""
                    dead = " ☠" if unit.hp <= 0 else ""
                    item_text = f"{unit.name}{marker}{dead} · ОЗ {unit.hp}/{unit.max_hp} · КД {unit.ac} · Урон {unit.damage} · ЛОВ {unit.dex_mod:+d}"
                    if unit.conditions:
                        item_text += f" · Состояния: {', '.join(unit.conditions)}"
                    list_widget.addItem(item_text)
                list_widget.setCurrentRow(-1)

    def _add_unit(self, side: str) -> None:
        """Добавить юнит в лагерь. Пока заглушка — позже будет форма редактирования."""
        army = self.battle.armies.get(side)
        if army:
            unit = UnitToken(
                name=f"Юнит {len(army.units) + 1}",
                side=side,
                hp=10,
                max_hp=10,
                ac=10,
                attack_bonus=0,
                damage="1d6",
                speed_ft=30,
                range_ft=5,
                dex_mod=1,
            )
            army.units.append(unit)
            self._refresh_army_widgets()
            self.battle.log.append(f"Добавлен юнит {unit.name} в лагерь {'Герои' if side == 'hero' else 'Враги'}")
            self._sync_log()

    def _remove_unit(self, side: str) -> None:
        """Удалить выбранный юнит."""
        widget = self.hero_army_widget if side == "hero" else self.enemy_army_widget
        list_widget = widget.findChild(QListWidget)
        if list_widget and list_widget.currentRow() >= 0:
            army = self.battle.armies.get(side)
            if army and list_widget.currentRow() < len(army.units):
                removed = army.units.pop(list_widget.currentRow())
                if self.selected_unit_id == removed.id:
                    self.selected_unit_id = None
                if self.target_unit_id == removed.id:
                    self.target_unit_id = None
                self._refresh_army_widgets()
                self.battle.log.append(f"Удалён юнит {removed.name}")
                self._sync_log()

    def _select_unit(self, side: str, row: int) -> None:
        """Выбрать юнита: свой в свой ход — атакующий, вражеский — цель."""
        army = self.battle.armies.get(side)
        if not army or not (0 <= row < len(army.units)):
            return
        unit = army.units[row]
        current = self.battle.current_unit() if self.battle.active else None
        if current is not None and unit.id != current.id and unit.side != current.side and unit.hp > 0:
            self.target_unit_id = unit.id
        else:
            self.selected_unit_id = unit.id
        pos = self.battle.position_of(unit.id)
        if pos is not None:
            self.field._selected = (pos.row, pos.col)
            self.field.update()
        self._update_selection_hint()
        self._refresh_army_widgets()

    def _on_cell_selected(self, row: int, col: int) -> None:
        """Клик по полю: вражеский токен — цель, пустая клетка — движение."""
        occupant = self.field.unit_at(row, col)
        if occupant is not None:
            unit = self.battle.unit_by_id(occupant)
            current = self.battle.current_unit() if self.battle.active else None
            if unit is not None and current is not None and unit.side != current.side and unit.hp > 0:
                self.target_unit_id = unit.id
                self._update_selection_hint()
                return
            self.selected_unit_id = occupant
            self._update_selection_hint()
            return
        if self.selected_unit_id is None:
            self.battle.log.append("Выберите юнита в списке лагеря, затем клетку для движения")
            self._sync_log()
            return
        ok, reason = self.battle.move_unit(self.selected_unit_id, row, col)
        if not ok:
            self.battle.log.append(f"Движение невозможно: {reason}")
        self.field.set_units({u.id: u for u in self.battle.all_units()})
        self._sync_log()

    def _start_battle(self) -> None:
        if not self.battle.all_units():
            self.battle.log.append("Добавьте юнитов в лагеря перед битвой")
            self._sync_log()
            return
        self._auto_deploy()
        self.battle.active = True
        self.battle.log.append("Битва началась!")
        self.battle.roll_initiative()
        current = self.battle.current_unit()
        if current is not None:
            self.selected_unit_id = current.id
            self.battle.log.append(f"Первый ход: {current.name}")
        self.target_unit_id = None
        self._refresh_army_widgets()
        self._refresh_turn_label()
        self._sync_log()

    def _next_turn(self) -> None:
        if not self.battle.active:
            return
        self.battle.next_turn()
        current = self.battle.current_unit()
        if current is not None:
            self.selected_unit_id = current.id
        self.target_unit_id = None
        self._refresh_army_widgets()
        self._refresh_turn_label()
        self._sync_log()

    def _end_battle(self) -> None:
        self.battle.end_battle()
        self._refresh_army_widgets()
        self._refresh_turn_label()
        self._sync_log()

    def _reset_field(self) -> None:
        for r in range(self.field.rows):
            for c in range(self.field.cols):
                self.field.cells[r][c].unit_id = None
        self.field.reset_selection()
        self.field.update()

    def _attack_target(self) -> None:
        """Выполнить атаку текущего юнита по выбранной цели."""
        if not self.battle.active:
            self.battle.log.append("Сначала нажмите «Начать битву»")
            self._sync_log()
            return
        current = self.battle.current_unit()
        attacker_id = current.id if current is not None else self.selected_unit_id
        if attacker_id is None:
            self.battle.log.append("Нет атакующего: очередь ходов пуста")
            self._sync_log()
            return
        if self.target_unit_id is None:
            self.battle.log.append("Выберите цель: кликните по вражескому юниту на поле или в списке")
            self._sync_log()
            return
        try:
            self.battle.attack(attacker_id, self.target_unit_id)
        except ValueError as exc:
            self.battle.log.append(f"Атака невозможна: {exc}")
            self._sync_log()
            return
        if not self.battle.active:
            self.target_unit_id = None
        self.field.set_units({u.id: u for u in self.battle.all_units()})
        self._refresh_army_widgets()
        self._refresh_turn_label()
        self._sync_log()

    def _auto_deploy(self) -> None:
        """Расставить невыставленных юнитов: герои слева, враги справа."""
        placed = self.field.occupied_cells()
        heroes = [u for u in self.battle.armies.get("hero", Army()).units if u.id not in placed and u.hp > 0]
        enemies = [u for u in self.battle.armies.get("enemy", Army()).units if u.id not in placed and u.hp > 0]
        rows, cols = self.field.rows, self.field.cols
        half = max(1, cols // 2)
        for index, unit in enumerate(heroes):
            r, c = index % rows, (index // rows) % half
            if self.field.cells[r][c].unit_id is None:
                self.field.set_unit_on_cell(unit.id, r, c)
        for index, unit in enumerate(enemies):
            r, c = index % rows, cols - 1 - (index // rows) % half
            if self.field.cells[r][c].unit_id is None:
                self.field.set_unit_on_cell(unit.id, r, c)
        self.field.set_units({u.id: u for u in self.battle.all_units()})

    def _sync_log(self) -> None:
        """Добавить новые записи журнала боя в виджет."""
        while self._shown_log < len(self.battle.log):
            self.log_list.addItem(self.battle.log[self._shown_log])
            self._shown_log += 1
        self.log_list.scrollToBottom()

    def _current_unit_id(self) -> str | None:
        current = self.battle.current_unit() if self.battle.active else None
        return current.id if current is not None else None

    def _refresh_turn_label(self) -> None:
        if not self.battle.active:
            winner = self.battle.check_winner()
            if winner == "hero":
                self.turn_label.setText("Победа героев! Начните новую битву или переставьте юнитов.")
            elif winner == "enemy":
                self.turn_label.setText("Победа врагов! Начните новую битву или переставьте юнитов.")
            elif winner == "draw":
                self.turn_label.setText("Ничья: обе армии уничтожены.")
            else:
                self.turn_label.setText("Битва не начата: расставьте юнитов и нажмите «Начать битву».")
            return
        current = self.battle.current_unit()
        if current is None:
            self.turn_label.setText("Очередь пуста.")
        else:
            self.turn_label.setText(
                f"Ходит: {current.name} · ОЗ {current.hp}/{current.max_hp} · "
                f"{current.damage} (досягаемость {current.range_ft} фт)"
            )

    def _update_selection_hint(self) -> None:
        attacker = self.battle.unit_by_id(self.selected_unit_id) if self.selected_unit_id else None
        target = self.battle.unit_by_id(self.target_unit_id) if self.target_unit_id else None
        left = attacker.name if attacker else "—"
        right = target.name if target else "—"
        extra = ""
        if attacker is not None and target is not None:
            apos = self.battle.position_of(attacker.id)
            tpos = self.battle.position_of(target.id)
            if apos is not None and tpos is not None:
                reaches, dist = in_range(apos, tpos, attacker.range_ft, self.battle.grid_type, self.battle.cell_ft)
                extra = f" · {dist} фт — {'достаёт' if reaches else 'далеко'}"
        self.selection_label.setText(f"Атакующий: {left} · Цель: {right}{extra}")

    def _on_grid_type_changed(self, index: int) -> None:
        grid_type = GRID_HEX if index == 1 else GRID_SQUARE
        self.field.set_grid_type(grid_type)
        self.battle.grid_type = grid_type
        self._update_selection_hint()

    def _edit_army(self, side: str) -> None:
        """Открыть диалог редактирования состава армии — по юнитам через UnitEditorDialog."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel

        army = self.battle.armies.get(side)
        if not army:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Редактирование армии · {'Герои' if side == 'hero' else 'Враги'}")
        dialog.resize(520, 360)
        layout = QVBoxLayout(dialog)

        selector_label = QLabel("Выберите юнита для редактирования:")
        selector_label.setObjectName("muted")
        layout.addWidget(selector_label)

        unit_list = QListWidget()
        for i, u in enumerate(army.units):
            unit_list.addItem(f"{i + 1}. {u.name} · ОЗ {u.hp}/{u.max_hp} · КД {u.ac}")
        unit_list.setMaximumHeight(150)
        layout.addWidget(unit_list, 1)

        row = QHBoxLayout()
        edit_button = QPushButton("Редактировать выбранного")
        edit_button.setObjectName("primary")
        edit_button.clicked.connect(lambda: self._edit_single_unit(side, unit_list.currentRow(), dialog))
        row.addWidget(edit_button)
        add_button = QPushButton("Добавить нового")
        add_button.clicked.connect(lambda: self._add_unit(side))
        row.addWidget(add_button)
        remove_button = QPushButton("Удалить выбранного")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(lambda: self._remove_unit_with_confirm(side, unit_list.currentRow()))
        row.addWidget(remove_button)
        row.addStretch()
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        dialog.exec()

    def _edit_single_unit(self, side: str, index: int, parent_dialog: QDialog | None = None) -> None:
        """Редактировать отдельного юнита через UnitEditorDialog."""
        army = self.battle.armies.get(side)
        if not army or not (0 <= index < len(army.units)):
            return
        unit = army.units[index]
        editor = UnitEditorDialog(unit=unit, side=side, parent=parent_dialog or self)
        if editor.exec() == QDialog.DialogCode.Accepted:
            unit.name = editor.name_input.text().strip() or unit.name
            unit.side = editor.side_combo.currentData()
            unit.hp = editor.hp_input.value()
            unit.max_hp = editor.max_hp_input.value()
            if unit.hp > unit.max_hp:
                unit.hp = unit.max_hp
            unit.ac = editor.ac_input.value()
            unit.attack_bonus = editor.attack_input.value()
            unit.dex_mod = editor.dex_input.value()
            unit.damage = editor.damage_input.text().strip() or "1d6"
            unit.damage_type = editor.damage_type_combo.currentText()
            unit.speed_ft = editor.speed_input.value()
            unit.range_ft = editor.range_input.value()
            unit.actions_per_turn = editor.actions_input.value()
            unit.icon_path = editor.icon_input.text().strip()
            unit.conditions = [x.strip() for x in editor.conditions_input.text().split(",") if x.strip()]
            self._refresh_army_widgets()
            self.battle.log.append(f"Юнит «{unit.name}» отредактирован")

    def _remove_unit_with_confirm(self, side: str, index: int) -> None:
        """Удалить юнит с подтверждением."""
        from PySide6.QtWidgets import QMessageBox
        army = self.battle.armies.get(side)
        if not army or not (0 <= index < len(army.units)):
            return
        removed = army.units[index]
        if QMessageBox.question(self, "Удалить юнита", f"Удалить «{removed.name}» из армии?") != QMessageBox.StandardButton.Yes:
            return
        army.units.pop(index)
        self._refresh_army_widgets()
        self.battle.log.append(f"Удалён юнит {removed.name}")
