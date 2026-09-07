"""
Стратегический режим — армия на армию, юниты на юниты, вид сверху.

Заглушка с редактируемыми настройками и понятными интерфейсами.
Позже здесь будет:
- Сетка клеток (квадратная) и гексагональная сетка, переключаемая в настройках.
- Токены юнитов, перемещаемые по клеткам/гексам.
- Дистанция в клетках (1 клетка = 5 футов по умолчанию).
- Движение, окружение, фланг, атаки между юнитами/армиями.
- Очередь юнитов, инициатива, бой по клеткам.

Сейчас — заглушка с настройками, двумя лагерями и минимальной отрисовкой поля.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
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
    speed_ft: int = 30  # скорость в футах (позже переводится в клетки)
    range_ft: int = 5  # дистанция атаки в футах
    actions_per_turn: int = 1  # сколько действий у юнита за ход (заглушка)
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

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        padding = 12
        w = rect.width() - padding * 2
        h = rect.height() - padding * 2
        top = padding
        left = padding
        cell_w = w / self.cols
        cell_h = h / self.rows

        # Фон поля
        painter.fillRect(rect, QColor("#0c0a0b"))

        # Клетки
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cells[r][c]
                x = left + c * cell_w
                y = top + r * cell_h
                if cell.unit_id:
                    painter.fillRect(int(x) + 1, int(y) + 1, int(cell_w) - 2, int(cell_h) - 2, QColor("#3a2a26"))
                    painter.setPen(QPen(QColor("#c9a77a"), 1))
                    painter.drawRect(int(x) + 1, int(y) + 1, int(cell_w) - 2, int(cell_h) - 2)
                else:
                    painter.setPen(QPen(QColor("#2a2523"), 1))
                    painter.setBrush(QColor("#1a1614"))
                    painter.drawRect(int(x) + 0, int(y) + 0, int(cell_w) - 1, int(cell_h) - 1)

        # Выделенная клетка
        if hasattr(self, "_selected") and self._selected:
            r, c = self._selected
            x = left + c * cell_w
            y = top + r * cell_h
            painter.setPen(QPen(QColor("#d98c4e"), 2))
            painter.drawRect(int(x) + 1, int(y) + 1, int(cell_w) - 2, int(cell_h) - 2)

        # Юниты (на клетках)
        for r in range(self.rows):
            for c in range(self.cols):
                cell = self.cells[r][c]
                if cell.unit_id:
                    x = left + c * cell_w + cell_w / 2
                    y = top + r * cell_h + cell_h / 2
                    painter.setPen(QColor("#d98c4e"))
                    painter.drawEllipse(int(x - 10), int(y - 10), 20, 20)

        painter.end()

    def mousePressEvent(self, event):  # type: ignore[override]
        rect = self.rect().adjusted(2, 2, -2, -2)
        padding = 12
        w = rect.width() - padding * 2
        h = rect.height() - padding * 2
        top = padding
        left = padding
        cell_w = w / self.cols
        cell_h = h / self.rows
        c = min(self.cols - 1, max(0, int((event.pos().x() - left) / cell_w)))
        r = min(self.rows - 1, max(0, int((event.pos().y() - top) / cell_h)))
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self._selected = (r, c)
            self.cell_selected.emit(r, c)
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

    def occupied_cells(self) -> dict[str, tuple[int, int]]:
        """Вернуть карту id юнита → (row, col)."""
        result: dict[str, tuple[int, int]] = {}
        for r in range(self.rows):
            for c in range(self.cols):
                if self.cells[r][c].unit_id:
                    result[self.cells[r][c].unit_id] = (r, c)
        return result

    def reset_selection(self) -> None:
        if hasattr(self, "_selected"):
            del self._selected
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

    def current_army(self) -> Army | None:
        if self.current_turn not in self.armies:
            return None
        return self.armies[self.current_turn]

    def next_turn(self) -> None:
        if not self.active:
            return
        self.turn_index += 1
        if self.turn_index >= len(self.initiative_order):
            self.turn_index = 0
        current_id = self.initiative_order[self.turn_index] if self.initiative_order else ""
        if current_id:
            for side, army in self.armies.items():
                if any(u.id == current_id for u in army.units):
                    self.current_turn = side
                    break
        self.log.append(f"Ход: {self.current_turn} (юнит {self.initiative_order[self.turn_index] if self.initiative_order else '—'})")

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

        self.damage_input = QLineEdit(self.unit.damage)

        self.damage_type_combo = QComboBox()
        damage_types = ["", "огневое", "холодное", "ламповое", "кинетическое", "мор/токсик", "психическое", "неконтагиозное"]
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
        self.melee_check.setChecked(self.range_ft <= 5)

        self.ranged_check = QCheckBox("Дальний бой")
        self.ranged_check.setChecked(self.range_ft > 5)

        for label, widget in (
            ("Имя", self.name_input),
            ("Сторона", self.side_combo),
            ("Текущие ОЗ", self.hp_input),
            ("Максимум ОЗ", self.max_hp_input),
            ("КД", self.ac_input),
            ("Бонус атаки", self.attack_input),
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
        self.init_ui()
        self.init_field()
        self.init_armies()
        self.connect_signals()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        title = QLabel("СТРАТЕГИЧЕСКИЙ РЕЖИМ · Армия на армию (заглушка)")
        title.setObjectName("title")
        layout.addWidget(title)

        # Выбор типа сетки
        grid_type_label = QLabel("Тип поля:")
        grid_type_label.setObjectName("muted")
        self.grid_type_combo = QComboBox()
        self.grid_type_combo.addItems(["Квадратная сетка", "Гексагональная сетка"])
        self.grid_type_combo.setCurrentIndex(0)
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
        settings_layout.addWidget(self.cell_size_spin)
        settings_layout.addStretch()
        layout.addLayout(settings_layout)

        # Поле
        self.field = GridField(rows=10, cols=10, cell_size=50)
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.field)

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
        self.end_button = QPushButton("Завершить битву")
        self.end_button.clicked.connect(self._end_battle)
        self.reset_button = QPushButton("Сбросить поле")
        self.reset_button.clicked.connect(self._reset_field)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.step_button)
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

    def _refresh_unit_list(self, widget: QWidget, side: str) -> None:
        list_widget = widget.findChild(QListWidget)
        if list_widget:
            list_widget.clear()
            army = self.battle.armies.get(side)
            if army:
                for unit in army.units:
                    item_text = f"{unit.name} · ОЗ {unit.hp}/{unit.max_hp} · КД {unit.ac} · Уроб {unit.damage} · Скорость {unit.speed_ft}фт"
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
            )
            army.units.append(unit)
            self._refresh_army_widgets()
            self.battle.log.append(f"Добавлен юнит {unit.name} в лагерь {'Герои' if side == 'hero' else 'Враги'}")

    def _remove_unit(self, side: str) -> None:
        """Удалить выбранный юнит."""
        widget = self.hero_army_widget if side == "hero" else self.enemy_army_widget
        list_widget = widget.findChild(QListWidget)
        if list_widget and list_widget.currentRow() >= 0:
            army = self.battle.armies.get(side)
            if army and list_widget.currentRow() < len(army.units):
                removed = army.units.pop(list_widget.currentRow())
                self._refresh_army_widgets()
                self.battle.log.append(f"Удалён юнит {removed.name}")

    def _select_unit(self, side: str, row: int) -> None:
        """Выбрать юнит для перемещения."""
        army = self.battle.armies.get(side)
        if army and 0 <= row < len(army.units):
            unit = army.units[row]
            self.field.reset_selection()
            for r in range(self.field.rows):
                for c in range(self.field.cols):
                    if self.field.cells[r][c].unit_id == unit.id:
                        self.field._selected = (r, c)
                        self.field.update()
                        break

    def _on_cell_selected(self, row: int, col: int) -> None:
        """Переместить выбранный юнит на выбранную клетку."""
        if not self.battle.active:
            return
        # Найти выбранный юнит по текущему лагерю
        army = self.battle.current_army()
        if army and army.alive_units():
            # Попробуем найти юнит, который сейчас "выбран" (по последнему клику)
            selected_unit = army.alive_units()[0]  # заглушка — позже будет реальный выбор
            # Проверка: можно ли переместиться (осталось ли движение)
            current_pos = None
            for r in range(self.field.rows):
                for c in range(self.field.cols):
                    if self.field.cells[r][c].unit_id == selected_unit.id:
                        current_pos = (r, c)
                        break
            if current_pos:
                dist = abs(row - current_pos[0]) + abs(col - current_pos[1])  # Манхэттен для заглушки
                max_cells = selected_unit.speed_ft // 5  # 1 клетка = 5 футов
                if dist <= max_cells:
                    # Очистить текущую клетку
                    for r in range(self.field.rows):
                        for c in range(self.field.cols):
                            if self.field.cells[r][c].unit_id == selected_unit.id:
                                self.field.cells[r][c].unit_id = None
                    # Установить новую
                    self.field.cells[row][col].unit_id = selected_unit.id
                    self.field.update()
                    self.battle.log.append(f"{selected_unit.name} → ({row}, {col})")
                    self.field._selected = (row, col)
                    self.field.update()

    def _start_battle(self) -> None:
        self.battle.active = True
        self.battle.turn_index = 0
        # Формируем инициативную очередь (заглушка — по ОЗ, позже по инициативе)
        all_units: list[UnitToken] = []
        for army in self.battle.armies.values():
            all_units.extend(army.units)
        all_units.sort(key=lambda u: u.ac, reverse=True)
        self.battle.initiative_order = [u.id for u in all_units if u.hp > 0]
        self.battle.current_turn = "hero"
        self._refresh_army_widgets()
        self.log_list.clear()
        self.battle.log.append("Битва началась!")
        self.log_list.addItem("Битва началась!")

    def _next_turn(self) -> None:
        if not self.battle.active:
            return
        self.battle.next_turn()
        army = self.battle.current_army()
        self.log_list.addItem(f"Ход: {army.name if army else '—'}")
        self._refresh_army_widgets()

    def _end_battle(self) -> None:
        self.battle.end_battle()
        self.log_list.addItem("Битва завершена")
        self._refresh_army_widgets()

    def _reset_field(self) -> None:
        for r in range(self.field.rows):
            for c in range(self.field.cols):
                self.field.cells[r][c].unit_id = None
        self.field.reset_selection()
        self.field.update()

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
