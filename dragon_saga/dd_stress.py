"""
Darkest Dungeon-стиль боя — очередь, позиции (фронт/тыл), стресс, критические удары.

Заглушка. Позже:
- Позиции: фронт, тыл, flanked, под ударами.
- Стресс: накопление стресса от событий боя, внезапная смерть, безнадёжность.
- Крит: критические удары и критические промахи с эффектами (например, ранение, помешательство).
- Очередь действий: враги и герои действуют по очереди, можно перемещаться между позициями.

Файл использует структуры из models.py (Combatant, Action, Resource) для совместимости.
Позже будет расширен для работы с бросками из rules.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .models import Combatant


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class Position(Enum):
    FRONT = "фронт"
    REAR = "тыл"
    FLANKED = "окружённый"


class StressLevel(Enum):
    CALM = "спокоен"
    STRESSED = "напряжён"
    TRAUMATIZED = "травмо́ван"
    BROKEN = "сломлен"


class CriticalEffect(Enum):
    NONE = "обычный"
    HIT_CRIT = "крит. удар"
    MISS_CRIT = "крит. промах"
    STUN = "оглушение"
    BLEED = "кровотечение"
    FEAR = "страх"


@dataclass
class DDParticipant:
    """Участник в DD-бою. Связан с Combatant, но содержит DD-специфичные поля."""

    id: str = field(default_factory=lambda: uid("ddpart"))
    combatant_id: str = ""  # ссылка на Combatant
    name: str = "Участник"
    side: str = "hero"
    position: Position = Position.FRONT
    hp: int = 10
    max_hp: int = 10
    stress: int = 0  # 0-100, позже — пороговые эффекты
    stress_level: StressLevel = StressLevel.CALM
    crit_count: int = 0  # количество критов за бой (для статистики)
    crit_effects: list[CriticalEffect] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    actions_left: int = 1  # сколько действий осталось за ход

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "combatant_id": self.combatant_id,
            "name": self.name,
            "side": self.side,
            "position": self.position.value,
            "hp": self.hp,
            "max_hp": self.max_hp,
            "stress": self.stress,
            "stress_level": self.stress_level.value,
            "crit_count": self.crit_count,
            "crit_effects": [e.value for e in self.crit_effects],
            "conditions": self.conditions,
            "actions_left": self.actions_left,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DDParticipant":
        pos_val = data.get("position", Position.FRONT.value)
        try:
            pos = Position(pos_val)
        except ValueError:
            pos = Position.FRONT
        stress_val = data.get("stress_level", StressLevel.CALM.value)
        try:
            stress_level = StressLevel(stress_val)
        except ValueError:
            stress_level = StressLevel.CALM
        return cls(
            id=data.get("id", ""),
            combatant_id=data.get("combatant_id", ""),
            name=data.get("name", "Участник"),
            side=data.get("side", "hero"),
            position=pos,
            hp=data.get("hp", 10),
            max_hp=data.get("max_hp", 10),
            stress=data.get("stress", 0),
            stress_level=stress_level,
            crit_count=data.get("crit_count", 0),
            crit_effects=[CriticalEffect(e) for e in data.get("crit_effects", [])],
            conditions=data.get("conditions", []),
            actions_left=data.get("actions_left", 1),
        )


@dataclass
class DDCombatRound:
    """Ход в DD-бою — очередь участников и результат."""

    participants: list[DDParticipant] = field(default_factory=list)
    current_index: int = 0
    log: list[str] = field(default_factory=list)

    def current(self) -> DDParticipant | None:
        if not self.participants or self.current_index >= len(self.participants):
            return None
        return self.participants[self.current_index]

    def next(self) -> None:
        if not self.participants:
            return
        self.current_index = (self.current_index + 1) % len(self.participants)
        self.log.append(f"Ход переходит к {self.participants[self.current_index].name}")


class DDRoundPanel(QWidget):
    """Панель текущего хода в DD-стиле. Заглушка — позже будет очередь с перетаскиванием."""

    action_requested = Signal(str, str)  # participant_id, action_name

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.round = DDCombatRound()
        self.current_participant = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("РАУНД В СТИЛЕ DARKEST DUNGEON · заглушка")
        title.setObjectName("eyebrow")
        layout.addWidget(title)

        self.status_label = QLabel("Ожидание участников...")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("muted")
        layout.addWidget(self.status_label)

        self.current_frame = QFrame()
        self.current_frame.setObjectName("panel")
        current_layout = QHBoxLayout(self.current_frame)
        current_layout.addWidget(QLabel("Текущий участник:"))
        self.current_name = QLabel("—")
        self.current_name.setStyleSheet("font-family: Georgia; font-weight: 700; color: #f0e4d8;")
        current_layout.addWidget(self.current_name)
        current_layout.addStretch()
        layout.addWidget(self.current_frame)

        self.position_label = QLabel("Позиция: —")
        self.position_label.setObjectName("muted")
        layout.addWidget(self.position_label)

        self.stress_label = QLabel("Стресс: —")
        self.stress_label.setObjectName("muted")
        layout.addWidget(self.stress_label)

        self.actions_label = QLabel("Действий осталось: —")
        self.actions_label.setObjectName("muted")
        layout.addWidget(self.actions_label)

        # Кнопки действий (заглушка)
        self.action_buttons = QHBoxLayout()
        self.attack_button = QPushButton("Атаковать")
        self.attack_button.setObjectName("primary")
        self.attack_button.clicked.connect(lambda: self._request_action("атака"))
        self.defend_button = QPushButton("Защита")
        self.defend_button.clicked.connect(lambda: self._request_action("защита"))
        self.magic_button = QPushButton("Магия/Сплайт")
        self.magic_button.clicked.connect(lambda: self._request_action("магия"))
        self.special_button = QPushButton("Особое")
        self.special_button.clicked.connect(lambda: self._request_action("особое"))
        self.action_buttons.addWidget(self.attack_button)
        self.action_buttons.addWidget(self.defend_button)
        self.action_buttons.addWidget(self.magic_button)
        self.action_buttons.addWidget(self.special_button)
        layout.addLayout(self.action_buttons)

        self.next_button = QPushButton("Следующий участник")
        self.next_button.clicked.connect(self.round.next)
        layout.addWidget(self.next_button)

        self.log_label = QLabel("Лог:")
        self.log_label.setObjectName("muted")
        layout.addWidget(self.log_label)
        self.log_list = QListWidget()
        self.log_list.setMaximumHeight(100)
        layout.addWidget(self.log_list)

    def _request_action(self, action_name: str) -> None:
        if self.current_participant:
            self.action_requested.emit(self.current_participant.id, action_name)
            self.log_list.addItem(f"{self.current_participant.name}: {action_name}")

    def set_participant(self, participant: DDParticipant | None) -> None:
        self.current_participant = participant
        if participant:
            self.current_name.setText(participant.name)
            self.position_label.setText(f"Позиция: {participant.position.value}")
            self.stress_label.setText(f"Стресс: {participant.stress} / 100")
            self.actions_label.setText(f"Действий осталось: {participant.actions_left}")
            self.status_label.setText(f"Ход участника: {participant.name}")
        else:
            self.current_name.setText("—")
            self.position_label.setText("Позиция: —")
            self.stress_label.setText("Стресс: —")
            self.actions_label.setText("Действий осталось: —")
            self.status_label.setText("Ожидание участников...")


class DDParticipantEditor(QDialog):
    """Диалог редактирования участника DD-бота — редактируемые параметры."""

    def __init__(self, participant: DDParticipant | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.participant = participant or DDParticipant()
        self.setWindowTitle("Редактирование участника")
        self.resize(480, 600)
        self.init_ui()

    def init_ui(self) -> None:
        from PySide6.QtWidgets import QDialogButtonBox, QFormLayout, QComboBox, QCheckBox, QSpinBox

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self.name_input = QLineEdit(self.participant.name)

        self.side_combo = QComboBox()
        self.side_combo.addItem("Герои", "hero")
        self.side_combo.addItem("Враги", "enemy")
        self.side_combo.setCurrentIndex(0 if self.participant.side == "hero" else 1)

        self.position_combo = QComboBox()
        self.position_combo.addItem("Фронт", Position.FRONT.value)
        self.position_combo.addItem("Тыл", Position.REAR.value)
        self.position_combo.addItem("Окружённый", Position.FLANKED.value)
        self.position_combo.setCurrentIndex(self.position_combo.findText(self.participant.position.value))

        self.hp_input = QSpinBox()
        self.hp_input.setRange(0, 999)
        self.hp_input.setValue(self.participant.hp)

        self.max_hp_input = QSpinBox()
        self.max_hp_input.setRange(1, 999)
        self.max_hp_input.setValue(self.participant.max_hp)

        self.stress_input = QSpinBox()
        self.stress_input.setRange(0, 100)
        self.stress_input.setValue(self.participant.stress)
        self.stress_input.setSuffix(" стресса")

        self.stress_level_combo = QComboBox()
        self.stress_level_combo.addItems([s.value for s in StressLevel])
        self.stress_level_combo.setCurrentIndex(self.stress_level_combo.findText(self.participant.stress_level.value))

        self.crit_count_input = QSpinBox()
        self.crit_count_input.setRange(0, 999)
        self.crit_count_input.setValue(self.participant.crit_count)

        self.actions_input = QSpinBox()
        self.actions_input.setRange(0, 10)
        self.actions_input.setValue(self.participant.actions_left)
        self.actions_input.setSuffix(" действий")

        self.conditions_input = QLineEdit(", ".join(self.participant.conditions))

        for label, widget in (
            ("Имя", self.name_input),
            ("Сторона", self.side_combo),
            ("Позиция", self.position_combo),
            ("Текущие ОЗ", self.hp_input),
            ("Максимум ОЗ", self.max_hp_input),
            ("Стресс", self.stress_input),
            ("Уровень стресса", self.stress_level_combo),
            ("Критов за бой", self.crit_count_input),
            ("Действий за ход", self.actions_input),
            ("Состояния (через запятую)", self.conditions_input),
        ):
            form.addRow(label, widget)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        self.participant.name = self.name_input.text().strip() or self.participant.name
        self.participant.side = self.side_combo.currentData()
        pos_val = self.position_combo.currentText()
        try:
            self.participant.position = Position(pos_val)
        except ValueError:
            self.participant.position = Position.FRONT
        self.participant.hp = self.hp_input.value()
        self.participant.max_hp = self.max_hp_input.value()
        if self.participant.hp > self.participant.max_hp:
            self.participant.hp = self.participant.max_hp
        self.participant.stress = self.stress_input.value()
        stress_val = self.stress_level_combo.currentText()
        try:
            self.participant.stress_level = StressLevel(stress_val)
        except ValueError:
            self.participant.stress_level = StressLevel.CALM
        self.participant.crit_count = self.crit_count_input.value()
        self.participant.actions_left = self.actions_input.value()
        self.participant.conditions = [x.strip() for x in self.conditions_input.text().split(",") if x.strip()]
        super().accept()


class DDBattleStage(QWidget):
    """Экран DD-стиля — заглушка. Позже — позиции, стресс, крит, очередь."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.battle = DDCombatRound()
        self.participants: list[DDParticipant] = []
        self.init_ui()
        self.init_participants()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("БОЙ В СТИЛЕ DARKEST DUNGEON · заглушка")
        title.setObjectName("title")
        layout.addWidget(title)

        desc = QLabel(
            "Это заглушка режима Darkest Dungeon.\n"
            "Позже здесь будут:\n"
            "- Позиции: фронт / тыл / окружённый.\n"
            "- Стресс: накопление стресса и пороговые эффекты (безнадёжность, внезапная смерть).\n"
            "- Критические удары и критические промахи с эффектами.\n"
            "- Очередь участников с перемещением между позициями.\n"
            "\n"
            "Пока — заглушка с понятным интерфейсом. Редактируй DDParticipant "
            "и DDRoundPanel для настройки механик."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        layout.addWidget(desc)

        # Позиции (заглушка)
        position_label = QLabel("Позиции участников (редактируемые):")
        position_label.setObjectName("muted")
        layout.addWidget(position_label)

        self.position_frame = QFrame()
        self.position_frame.setObjectName("panel")
        pos_layout = QHBoxLayout(self.position_frame)
        self.front_label = QLabel("ФРОНТ:")
        self.front_label.setStyleSheet("font-family: Georgia; font-weight: 700; color: #d98c4e;")
        self.front_list = QListWidget()
        self.front_list.setMaximumHeight(60)
        pos_layout.addWidget(self.front_label)
        pos_layout.addWidget(self.front_list)

        self.rear_label = QLabel("ТЫЛ:")
        self.rear_label.setStyleSheet("font-family: Georgia; font-weight: 700; color: #7a9a9a;")
        self.rear_list = QListWidget()
        self.rear_list.setMaximumHeight(60)
        pos_layout.addWidget(self.rear_label)
        pos_layout.addWidget(self.rear_list)
        layout.addWidget(self.position_frame)

        # Стресс и крит-эффекты (заглушка)
        effects_label = QLabel("Критические эффекты и стресс (редактируемые):")
        effects_label.setObjectName("muted")
        layout.addWidget(effects_label)

        self.effects_frame = QFrame()
        self.effects_frame.setObjectName("panel")
        effects_layout = QHBoxLayout(self.effects_frame)

        self.stress_spin = QSpinBox()
        self.stress_spin.setRange(0, 100)
        self.stress_spin.setValue(0)
        self.stress_spin.setSuffix(" стресса")
        effects_layout.addWidget(QLabel("Стресс:"))
        effects_layout.addWidget(self.stress_spin)

        self.crit_effects_label = QLabel("Крит. эффекты:")
        effects_layout.addWidget(self.crit_effects_label)
        self.crit_effects_edit = QLineEdit("")
        effects_layout.addWidget(self.crit_effects_edit)
        layout.addWidget(self.effects_frame)

        # Панель текущего хода
        self.round_panel = DDRoundPanel()
        layout.addWidget(self.round_panel)

        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.start_button = QPushButton("Начать раунд")
        self.start_button.setObjectName("primary")
        self.start_button.clicked.connect(self._start_round)
        self.end_button = QPushButton("Завершить раунд")
        self.end_button.clicked.connect(self._end_round)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.end_button)
        layout.addLayout(buttons_layout)

    def init_participants(self) -> None:
        """Инициализация участников. Пока заглушка — позже будет импорт из Combatant."""
        # Создаём двух участников для примера
        hero = DDParticipant(
            name="Герой",
            side="hero",
            hp=20,
            max_hp=20,
            stress=0,
            stress_level=StressLevel.CALM,
            position=Position.FRONT,
        )
        enemy = DDParticipant(
            name="Враг",
            side="enemy",
            hp=15,
            max_hp=15,
            stress=0,
            stress_level=StressLevel.CALM,
            position=Position.FRONT,
        )
        self.participants = [hero, enemy]
        self.battle.participants = self.participants
        self.battle.current_index = 0
        self._refresh_positions()

    def _refresh_positions(self) -> None:
        self.front_list.clear()
        self.rear_list.clear()
        for p in self.participants:
            if p.position == Position.FRONT or p.position == Position.FLANKED:
                self.front_list.addItem(f"{p.name} · ОЗ {p.hp}/{p.max_hp} · Стресс {p.stress}")
            else:
                self.rear_list.addItem(f"{p.name} · ОЗ {p.hp}/{p.max_hp} · Стресс {p.stress}")

    def _start_round(self) -> None:
        if not self.battle.participants:
            return
        self.battle.current_index = 0
        self.round_panel.set_participant(self.battle.current())
        self.log_list_add(f"Раунд начался! Ход: {self.battle.current().name}")

    def _end_round(self) -> None:
        self.round_panel.set_participant(None)
        self.log_list_add("Раунд завершён.")

    def _move_to_rear(self) -> None:
        """Переместить выбранного участника в тыл."""
        target = self.front_list.currentItem()
        if not target:
            return
        p = self._find_participant_by_name(target.text())
        if p:
            p.position = Position.REAR
            self._refresh_positions()
            self.log_list_add(f"{p.name} → ТЫЛ")

    def _move_to_front(self) -> None:
        """Переместить выбранного участника на фронт."""
        target = self.rear_list.currentItem()
        if not target:
            return
        p = self._find_participant_by_name(target.text())
        if p:
            p.position = Position.FRONT
            self._refresh_positions()
            self.log_list_add(f"{p.name} → ФРОНТ")

    def _swap_positions(self) -> None:
        """Обмен позициями между фронтом и тылом (один из каждого лагеря)."""
        # Для заглушки: просто переместим всех фронта в тыл (демонстрация)
        for p in self.participants:
            if p.position == Position.FRONT:
                p.position = Position.REAR
            elif p.position == Position.REAR or p.position == Position.FLANKED:
                p.position = Position.FRONT
        self._refresh_positions()
        self.log_list_add("Позиции обменялись: фронт ↔ тыл")

    def _edit_participant(self, click_list: str) -> None:
        """Открыть редактор участника из клика по списку."""
        from PySide6.QtWidgets import QListWidget

        # Найти участника по списку, из которого пришёл клик
        target_name = None
        if click_list == "front":
            item = self.front_list.currentItem()
        else:
            item = self.rear_list.currentItem()

        if item:
            p = self._find_participant_by_name(item.text())
            if p:
                editor = DDParticipantEditor(participant=p, parent=self)
                if editor.exec() == QDialog.DialogCode.Accepted:
                    self._refresh_positions()
                    self.log_list_add(f"Участник «{p.name}» отредактирован")

    def _find_participant_by_name(self, text: str) -> DDParticipant | None:
        """Найти участника по отображаемому имени в списке."""
        for p in self.participants:
            expected = f"{p.name} · ОЗ {p.hp}/{p.max_hp} · Стресс {p.stress}"
            if p.name in text or expected in text:
                return p
        return None

    def log_list_add(self, text: str) -> None:
        if hasattr(self, "round_panel") and self.round_panel.log_list:
            self.round_panel.log_list.addItem(text)
        else:
            # fallback — если round_panel ещё не инициализирован
            pass


# Заглушка: позже будет импорт чар и LSS-формата в DD-стиль
# (например, чар с критическими эффектами, стрессом и позициями)
def parse_dd_charm_from_lss(text: str) -> list[DDParticipant]:
    """Парсит LSS-экспорт чар для DD-стиля. Пока заглушка — позже будет полноценный парсер."""
    return []
