"""
Визуальные калькуляторы для оптимизации расчётов на сцене.

Позволяют бросать кубы, сравнивать КД, рассчитывать спасброски и урон
с наглядной подсветкой результатов.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import bestiary
from .encounter import THEMES, assess, generate, normalize_cr
from .models import ABILITIES, ZONES
from .rules import BattleEngine, RuleError


ABILITY_NAMES = {
    "str": "СИЛ",
    "dex": "ЛОВ",
    "con": "ТЕЛ",
    "int": "ИНТ",
    "wis": "МДР",
    "cha": "ХАР",
}


class DamageCalculator(QWidget):
    """Визуальный калькулятор урона: бросок кубов, модификаторы, тип урона, результат."""

    calculated = Signal(str)  # формула → текст результата

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.engine = BattleEngine.__new__(BattleEngine)  # не нужен campaign для бросков
        self.engine.randint = self._randint
        self._results: list[str] = []
        self._dice_results: dict[str, list[int]] = {}
        self.init_ui()

    def _randint(self, low: int, high: int) -> int:
        import random
        return random.randint(low, high)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("КАЛЬКУЛЯТОР УРОНА")
        title.setObjectName("section")
        layout.addWidget(title)

        # Формула
        formula_row = QHBoxLayout()
        formula_row.addWidget(QLabel("Формула:"))
        self.formula_input = QLineEdit("1d8+3")
        self.formula_input.setObjectName("sourceEditor")
        formula_row.addWidget(self.formula_input, 1)
        self.roll_button = QPushButton("БРОСК")
        self.roll_button.setObjectName("primary")
        self.roll_button.clicked.connect(self.roll)
        formula_row.addWidget(self.roll_button)
        layout.addLayout(formula_row)

        # Контекст (кто бьёт, кто получает)
        context_row = QHBoxLayout()
        context_row.addWidget(QLabel("Атакующий:"))
        self.attacker_input = QLineEdit("")
        self.attacker_input.setPlaceholderText("Имя бьющего")
        context_row.addWidget(self.attacker_input)
        context_row.addWidget(QLabel("Цель:"))
        self.target_input = QLineEdit("")
        self.target_input.setPlaceholderText("Имя цели")
        context_row.addWidget(self.target_input)
        layout.addLayout(context_row)

        # Модификаторы
        mod_row = QHBoxLayout()
        mod_row.addWidget(QLabel("Бонус атаки:"))
        self.attack_bonus_spin = QSpinBox()
        self.attack_bonus_spin.setRange(-20, 40)
        self.attack_bonus_spin.setValue(0)
        self.attack_bonus_spin.setSuffix("+")
        mod_row.addWidget(self.attack_bonus_spin)
        mod_row.addWidget(QLabel("Оборона (КД цели):"))
        self.ac_spin = QSpinBox()
        self.ac_spin.setRange(0, 99)
        self.ac_spin.setValue(10)
        mod_row.addWidget(self.ac_spin)
        layout.addLayout(mod_row)

        # Критический бросок (настройка)
        crit_row = QHBoxLayout()
        crit_row.addWidget(QLabel("Крит c 20:"))
        self.crit_checkbox = QComboBox()
        self.crit_checkbox.addItems(["Обычный (20 = крит)", "Всегда крит", "Никогда"])
        crit_row.addWidget(self.crit_checkbox)
        layout.addLayout(crit_row)

        # Результат
        self.result_label = QLabel("Результат: —")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 15px; color: #f0e4d8; padding: 8px; background: #1a1414; border: 1px solid #3a3030;")
        layout.addWidget(self.result_label)

        # История бросков
        history_row = QHBoxLayout()
        history_row.addWidget(QLabel("История:"))
        history_row.addStretch()
        layout.addLayout(history_row)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(120)
        layout.addWidget(self.history_list, 1)

        # Кнопка очистки
        clear_row = QHBoxLayout()
        clear_row.addStretch()
        clear_button = QPushButton("Очистить историю")
        clear_button.clicked.connect(self.clear_history)
        clear_row.addWidget(clear_button)
        layout.addLayout(clear_row)

    def roll(self) -> None:
        formula = self.formula_input.text().strip()
        if not formula:
            self.result_label.setText("Ошибка: введите формулу")
            return
        try:
            result = self.engine.roll(formula)
            attack_bonus = self.attack_bonus_spin.value()
            ac = self.ac_spin.value()
            total = result.total + attack_bonus
            hit = total >= ac

            # Критический бросок
            is_crit = False
            is_fumble = False
            if self.crit_checkbox.currentIndex() == 0:
                # Обычный: проверяем по последнему кубу d20
                dice = result.parts
                if dice and len(dice) > 0:
                    last_die = dice[-1]
                    # Проверяем, является ли последний куб d20
                    if "d20" in formula.lower() or ("1d20" in formula.lower()):
                        if last_die == 20:
                            is_crit = True
                        elif last_die == 1:
                            is_fumble = True
            elif self.crit_checkbox.currentIndex() == 1:
                is_crit = True
            # Индекс 2 — никогда не крити

            # Подсветка результата
            if is_crit:
                self.result_label.setStyleSheet(
                    "font-family: Georgia; font-size: 15px; color: #ff6b6b; padding: 8px; "
                    "background: #2a1a1a; border: 1px solid #ff4444;"
                )
                result_text = f"🎲 КРИТИЧЕСКИЙ УДАР!\n{self.attacker_input.text() or 'Атакующий'} → {self.target_input.text() or 'Цель'}\n"
                result_text += f"Формула: {formula} = {result.total} + {attack_bonus:+d} = {total}\n"
                result_text += f"КД цели: {ac} → ПОПАДАНИЕ!\n"
                result_text += f"Кубы: {result.parts} (последний d20 = 20!)"
            elif hit:
                self.result_label.setStyleSheet(
                    "font-family: Georgia; font-size: 15px; color: #a8d5a2; padding: 8px; "
                    "background: #1a2a1a; border: 1px solid #4a8a4a;"
                )
                result_text = f"✅ ПОПАДАНИЕ\n{self.attacker_input.text() or 'Атакующий'} → {self.target_input.text() or 'Цель'}\n"
                result_text += f"Формула: {formula} = {result.total} + {attack_bonus:+d} = {total}\n"
                result_text += f"КД цели: {ac} → попадает!"
            else:
                # Проверяем на критический промах (1 на d20)
                is_fumble = False
                if self.crit_checkbox.currentIndex() == 0:
                    if "d20" in formula.lower() or "1d20" in formula.lower():
                        dice = result.parts
                        if dice and dice[-1] == 1:
                            is_fumble = True

                if is_fumble:
                    self.result_label.setStyleSheet(
                        "font-family: Georgia; font-size: 15px; color: #ff9999; padding: 8px; "
                        "background: #2a1a1a; border: 1px solid #cc4444;"
                    )
                    result_text = f"💥 КРИТИЧЕСКИЙ ПРОМАХ!\n{self.attacker_input.text() or 'Атакующий'} → {self.target_input.text() or 'Цель'}\n"
                    result_text += f"Формула: {formula} = {result.total} + {attack_bonus:+d} = {total}\n"
                    result_text += f"КД цели: {ac} → промах! (1 на кубе d20)"
                else:
                    self.result_label.setStyleSheet(
                        "font-family: Georgia; font-size: 15px; color: #ffb3b3; padding: 8px; "
                        "background: #2a1a1a; border: 1px solid #6a3a3a;"
                    )
                    result_text = f"❌ ПРОМАХ\n{self.attacker_input.text() or 'Атакующий'} → {self.target_input.text() or 'Цель'}\n"
                    result_text += f"Формула: {formula} = {result.total} + {attack_bonus:+d} = {total}\n"
                    result_text += f"КД цели: {ac} → не попадает (нужно {ac}, получено {total})"

            self.result_label.setText(result_text)
            self._results.insert(0, f"{formula} = {result.total} + {attack_bonus:+d} → {'ПОПАДАНИЕ' if hit else 'ПРОМАХ'}")
            self.history_list.clear()
            self.history_list.addItems(self._results[:20])
            self.calculated.emit(result_text)

        except RuleError as e:
            self.result_label.setText(f"Ошибка формулы: {e}")
            self.result_label.setStyleSheet("font-family: Georgia; color: #ff6666; padding: 8px; background: #2a1a1a; border: 1px solid #663333;")

    def clear_history(self) -> None:
        self._results.clear()
        self.history_list.clear()
        self.result_label.setText("Результат: —")
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 15px; color: #f0e4d8; padding: 8px; background: #1a1414; border: 1px solid #3a3030;")


class SaveDCcalculator(QWidget):
    """Калькулятор спасбросков: DC, характеристика, урон/лечение, половина урона."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.engine = BattleEngine.__new__(BattleEngine)
        self.engine.randint = self._randint
        self._results: list[str] = []
        self.init_ui()

    def _randint(self, low: int, high: int) -> int:
        import random
        return random.randint(low, high)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("КАЛЬКУЛЯТОР СПАСБРОСКОВ / DC")
        title.setObjectName("section")
        layout.addWidget(title)

        # DC и характеристика
        dc_row = QHBoxLayout()
        dc_row.addWidget(QLabel("Сл (DC):"))
        self.dc_spin = QSpinBox()
        self.dc_spin.setRange(0, 40)
        self.dc_spin.setValue(15)
        dc_row.addWidget(self.dc_spin)
        dc_row.addWidget(QLabel("Характеристика:"))
        self.ability_combo = QComboBox()
        for key, name in ABILITY_NAMES.items():
            self.ability_combo.addItem(name, key)
        dc_row.addWidget(self.ability_combo)
        dc_row.addWidget(QLabel("Модификатор:"))
        self.ability_mod_spin = QSpinBox()
        self.ability_mod_spin.setRange(-10, 20)
        self.ability_mod_spin.setValue(0)
        dc_row.addWidget(self.ability_mod_spin)
        layout.addLayout(dc_row)

        # Урон / лечение
        damage_row = QHBoxLayout()
        damage_row.addWidget(QLabel("Урон (формула):"))
        self.damage_formula = QLineEdit("2d6")
        damage_row.addWidget(self.damage_formula, 1)
        damage_row.addWidget(QLabel("Половина урона при успехе:"))
        self.half_checkbox = QComboBox()
        self.half_checkbox.addItems(["Нет", "Да"])
        damage_row.addWidget(self.half_checkbox)
        layout.addLayout(damage_row)

        # Роль (атакующий/защищающийся)
        role_row = QHBoxLayout()
        role_row.addWidget(QLabel("Роль:"))
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Защищающийся (спасбросок)", "Атакующий (назначает DC)"])
        role_row.addWidget(self.role_combo)
        layout.addLayout(role_row)

        # Имя участников
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Защищающийся:"))
        self.saving_name = QLineEdit("")
        name_row.addWidget(self.saving_name)
        name_row.addWidget(QLabel("Назначающий DC:"))
        self.dc_name = QLineEdit("")
        name_row.addWidget(self.dc_name)
        layout.addLayout(name_row)

        # Кнопки
        button_row = QHBoxLayout()
        self.roll_button = QPushButton("БРОСК СПАСБРОСКА")
        self.roll_button.setObjectName("primary")
        self.roll_button.clicked.connect(self.roll)
        button_row.addWidget(self.roll_button)

        self.calculate_dc_button = QPushButton("РАСЧЁТ DC")
        self.calculate_dc_button.clicked.connect(self.calculate_dc)
        button_row.addWidget(self.calculate_dc_button)

        layout.addLayout(button_row)

        # Результат
        self.result_label = QLabel("Результат: —")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 14px; padding: 8px; background: #1a1414; border: 1px solid #3a3030;")
        layout.addWidget(self.result_label)

    def roll(self) -> None:
        dc = self.dc_spin.value()
        ability = self.ability_combo.currentData()
        mod = self.ability_mod_spin.value()
        damage_formula = self.damage_formula.text().strip()
        half_on_success = self.half_checkbox.currentIndex() == 1
        role = self.role_combo.currentIndex()

        try:
            # Бросок спасброска
            total, dice, natural = self.engine.d20(mod)

            # Проверка успеха (меньше DC = успех)
            success = total < dc

            # Урон
            if damage_formula:
                damage_roll = self.engine.roll(damage_formula)
                if half_on_success and success:
                    damage = damage_roll.total // 2
                    damage_text = f"{damage_roll.total} / 2 = {damage}"
                else:
                    damage = damage_roll.total
                    damage_text = str(damage)
            else:
                damage = 0
                damage_text = "нет урона"

            # Формирование результата
            if role == 0:  # Защищающийся
                if success:
                    result_text = (
                        f"🛡️ СПАСБРОСКА УСПЕШНА\n"
                        f"{self.saving_name.text() or 'Защищающийся'} бросает {ABILITY_NAMES.get(ability, ability)}:\n"
                        f"{dice[0]} + {mod:+d} = {total} (нужно < {dc})\n"
                        f"→ Успех! Урон: {damage_text}"
                    )
                    self.result_label.setStyleSheet(
                        "font-family: Georgia; font-size: 14px; color: #a8d5a2; padding: 8px; "
                        "background: #1a2a1a; border: 1px solid #4a8a4a;"
                    )
                else:
                    result_text = (
                        f"💢 СПАСБРОСКА НЕУСПЕШНА\n"
                        f"{self.saving_name.text() or 'Защищающийся'} бросает {ABILITY_NAMES.get(ability, ability)}:\n"
                        f"{dice[0]} + {mod:+d} = {total} (нужно < {dc})\n"
                        f"→ Неудача! Урон: {damage_text}"
                    )
                    self.result_label.setStyleSheet(
                        "font-family: Georgia; font-size: 14px; color: #ffb3b3; padding: 8px; "
                        "background: #2a1a1a; border: 1px solid #6a3a3a;"
                    )
            else:  # Атакующий
                result_text = (
                    f"📊 РАСЧЁТ DC\n"
                    f"{self.dc_name.text() or 'Атакующий'} назначает DC {dc}\n"
                    f"Характеристика {ABILITY_NAMES.get(ability, ability)} цели: {mod:+d}\n"
                    f"Для успеха нужно: {dc - mod} или меньше"
                )
                self.result_label.setStyleSheet(
                    "font-family: Georgia; font-size: 14px; color: #f0e4d8; padding: 8px; "
                    "background: #1a1414; border: 1px solid #3a3030;"
                )

            self.result_label.setText(result_text)
            self._results.insert(0, result_text[:200])
            # Здесь можно добавить историю

        except RuleError as e:
            self.result_label.setText(f"Ошибка: {e}")
            self.result_label.setStyleSheet("font-family: Georgia; color: #ff6666; padding: 8px; background: #2a1a1a; border: 1px solid #663333;")

    def calculate_dc(self) -> None:
        """Расчёт DC по формуле: 8 + профик + модификатор."""
        mod = self.ability_mod_spin.value()
        dc = 8 + mod  # упрощённо, обычно 8 + профик + мод
        self.dc_spin.setValue(dc)
        self.result_label.setText(f"DC рассчитан: 8 + {mod:+d} = {dc}")
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 14px; color: #f0e4d8; padding: 8px; background: #1a1414; border: 1px solid #3a3030;")


class ACComparison(QWidget):
    """Сравнение КД: кто имеет преимущество, насколько сложно попасть."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("СРАВНЕНИЕ КД")
        title.setObjectName("section")
        layout.addWidget(title)

        # Два КД для сравнения
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("КД защищающегося:"))
        self.ac_defender = QSpinBox()
        self.ac_defender.setRange(0, 99)
        self.ac_defender.setValue(10)
        row1.addWidget(self.ac_defender)

        row1.addWidget(QLabel("КД нападающего:"))
        self.ac_attacker = QSpinBox()
        self.ac_attacker.setRange(0, 99)
        self.ac_attacker.setValue(0)
        row1.addWidget(self.ac_attacker)
        layout.addLayout(row1)

        # Преимущества/недостатки
        adv_row = QHBoxLayout()
        adv_row.addWidget(QLabel("Преим. нападающего:"))
        self.attacker_adv = QComboBox()
        self.attacker_adv.addItems(["Нет", "Преимущество (+)", "Недостаток (-)"])
        adv_row.addWidget(self.attacker_adv)

        adv_row.addWidget(QLabel("Преим. защищающегося:"))
        self.defender_adv = QComboBox()
        self.defender_adv.addItems(["Нет", "Преимущество (+)", "Недостаток (-)"])
        adv_row.addWidget(self.defender_adv)
        layout.addLayout(adv_row)

        # Бонусы/пенальти
        bonus_row = QHBoxLayout()
        bonus_row.addWidget(QLabel("Бонус нападающего:"))
        self.attacker_bonus = QSpinBox()
        self.attacker_bonus.setRange(-10, 20)
        self.attacker_bonus.setValue(0)
        bonus_row.addWidget(self.attacker_bonus)

        bonus_row.addWidget(QLabel("Пенальти защит.:"))
        self.defender_penalty = QSpinBox()
        self.defender_penalty.setRange(-10, 10)
        self.defender_penalty.setValue(0)
        bonus_row.addWidget(self.defender_penalty)
        layout.addLayout(bonus_row)

        # Результат
        self.result_label = QLabel("Результат: —")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 14px; padding: 8px; background: #1a1414; border: 1px solid #3a3030;")
        layout.addWidget(self.result_label)

        # Вероятность попадания (примерная)
        prob_row = QHBoxLayout()
        prob_row.addWidget(QLabel("Примерная вероятность попадания (d20):"))
        self.probability_label = QLabel("—")
        self.probability_label.setStyleSheet("font-family: Georgia; font-size: 14px; color: #d98c4e;")
        prob_row.addWidget(self.probability_label, 1)
        layout.addLayout(prob_row)

        # Кнопка расчёта
        calc_button = QPushButton("РАССЧИТАТЬ")
        calc_button.setObjectName("primary")
        calc_button.clicked.connect(self.calculate)
        layout.addWidget(calc_button)

    def calculate(self) -> None:
        ac_def = self.ac_defender.value()
        ac_att = self.ac_attacker.value()
        att_adv = self.attacker_adv.currentIndex()  # 0=нет, 1=преим, 2=недост
        def_adv = self.defender_adv.currentIndex()
        att_bonus = self.attacker_bonus.value()
        def_penalty = self.defender_penalty.value()

        effective_ac = ac_def + def_penalty
        effective_attack = ac_att + att_bonus

        # Учёт преимуществ
        if att_adv == 1:
            effective_attack += 2  # упрощённо: преимущество = +2 к эффективному КД
        elif att_adv == 2:
            effective_attack -= 2

        if def_adv == 1:
            effective_ac += 2
        elif def_adv == 2:
            effective_ac -= 2

        # Сравнение
        diff = effective_attack - effective_ac

        if diff > 0:
            result_text = (
                f"✅ Нападающий имеет преимущество на {diff} пункк(ов)\n"
                f"Эффективное КД нападающего: {effective_attack}\n"
                f"Эффективное КД защит.: {effective_ac}\n"
                f"Разница: +{diff}"
            )
            self.result_label.setStyleSheet(
                "font-family: Georgia; font-size: 14px; color: #a8d5a2; padding: 8px; "
                "background: #1a2a1a; border: 1px solid #4a8a4a;"
            )
        elif diff < 0:
            result_text = (
                f"❌ Защит. имеет преимущество на {-diff} пункк(ов)\n"
                f"Эффективное КД нападающего: {effective_attack}\n"
                f"Эффективное КД защит.: {effective_ac}\n"
                f"Разница: {diff}"
            )
            self.result_label.setStyleSheet(
                "font-family: Georgia; font-size: 14px; color: #ffb3b3; padding: 8px; "
                "background: #2a1a1a; border: 1px solid #6a3a3a;"
            )
        else:
            result_text = (
                f"⚖️  КД равны!\n"
                f"Эффективное КД нападающего: {effective_attack}\n"
                f"Эффективное КД защит.: {effective_ac}\n"
                f"Ничья — 50/50"
            )
            self.result_label.setStyleSheet(
                "font-family: Georgia; font-size: 14px; color: #d98c4e; padding: 8px; "
                "background: #2a2520; border: 1px solid #8a6a3a;"
            )

        self.result_label.setText(result_text)

        # Примерная вероятность (упрощённо: (21 - |diff|) / 20 * 100%)
        if diff > 0:
            prob = (21 - diff) / 20 * 100
        elif diff < 0:
            prob = (21 + diff) / 20 * 100  # diff negative, so 21 + diff = 21 - |diff|
        else:
            prob = 50

        self.probability_label.setText(f"{max(0, min(100, prob)):.0f}%")


class InitiativeTracker(QWidget):
    """Отслеживание инициативы: очередь участников, бросок, текущий ход."""

    turn_changed = Signal(str)  # id участника

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.engine = BattleEngine.__new__(BattleEngine)
        self.engine.randint = self._randint
        self.participants: list[dict] = []
        self.current_index = -1
        self.init_ui()

    def _randint(self, low: int, high: int) -> int:
        import random
        return random.randint(low, high)

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("ОЧЕРЕДЬ ИНИЦИАТИВЫ")
        title.setObjectName("section")
        layout.addWidget(title)

        # Список участников
        self.list_label = QLabel("Участники (выберите и бросьте инициативу):")
        self.list_label.setObjectName("muted")
        layout.addWidget(self.list_label)

        self.participant_list = QListWidget()
        self.participant_list.setMinimumHeight(150)
        self.participant_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.participant_list, 1)

        # Кнопки
        button_row = QHBoxLayout()
        add_button = QPushButton("＋ Добавить")
        add_button.clicked.connect(self.add_participant)
        button_row.addWidget(add_button)

        remove_button = QPushButton("✕ Удалить")
        remove_button.clicked.connect(self.remove_participant)
        button_row.addWidget(remove_button)

        roll_button = QPushButton("🎲 БРОСОК ИНИЦИАТИВЫ")
        roll_button.setObjectName("primary")
        roll_button.clicked.connect(self.roll_initiative)
        button_row.addWidget(roll_button)

        next_button = QPushButton("Следующий ход ▶")
        next_button.clicked.connect(self.next_turn)
        button_row.addWidget(next_button)

        reset_button = QPushButton("Сброс")
        reset_button.clicked.connect(self.reset)
        button_row.addWidget(reset_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        # Текущий ход
        current_row = QHBoxLayout()
        current_row.addWidget(QLabel("Текущий ход:"))
        self.current_turn_label = QLabel("—")
        self.current_turn_label.setStyleSheet("font-family: Georgia; font-size: 16px; font-weight: 700; color: #d98c4e;")
        current_row.addWidget(self.current_turn_label, 1)
        layout.addLayout(current_row)

        # Список очереди
        queue_label = QLabel("Очередь (по порядку):")
        queue_label.setObjectName("muted")
        layout.addWidget(queue_label)

        self.queue_list = QListWidget()
        self.queue_list.setMinimumHeight(100)
        layout.addWidget(self.queue_list, 1)

    def add_participant(self) -> None:
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Новый участник", "Имя участника:")
        if ok and name.strip():
            bonus, ok2 = QInputDialog.getInt(self, "Бонус инициативы", "Бонус инициативы:", 0, -10, 20)
            if ok2:
                self.participants.append({
                    "id": f"p-{len(self.participants)}",
                    "name": name.strip(),
                    "bonus": bonus,
                    "initiative": None,
                })
                self.refresh_list()
                self.refresh_queue()

    def remove_participant(self) -> None:
        row = self.participant_list.currentRow()
        if row >= 0 and row < len(self.participants):
            self.participants.pop(row)
            if self.current_index >= len(self.participants):
                self.current_index = -1
            self.refresh_list()
            self.refresh_queue()
            self.current_turn_label.setText("—")

    def refresh_list(self) -> None:
        self.participant_list.clear()
        for p in self.participants:
            bonus_text = f" (+{p['bonus']})" if p['bonus'] > 0 else f" ({p['bonus']})" if p['bonus'] < 0 else ""
            init_text = f" [{p['initiative']}]" if p['initiative'] is not None else ""
            self.participant_list.addItem(f"{p['name']}{bonus_text}{init_text}")

    def refresh_queue(self) -> None:
        self.queue_list.clear()
        if not self.participants:
            return
        sorted_parts = sorted(self.participants, key=lambda p: (p['initiative'] or 0, p['bonus']), reverse=True)
        current_name = None
        if self.current_index >= 0 and self.current_index < len(sorted_parts):
            current_name = sorted_parts[self.current_index]['name']
        for i, p in enumerate(sorted_parts):
            marker = " ▶ " if p['name'] == current_name else "   "
            self.queue_list.addItem(f"{marker}{i+1}. {p['name']} — иниц. {p['initiative']} (бонус {p['bonus']:+d})")

    def roll_initiative(self) -> None:
        if not self.participants:
            return
        current = self.participant_list.currentRow()
        if current >= 0:
            # Бросок для выбранного
            p = self.participants[current]
            total, dice, natural = self.engine.d20(p['bonus'])
            p['initiative'] = total
            self.participant_list.clear()
            for pp in self.participants:
                bonus_text = f" (+{pp['bonus']})" if pp['bonus'] > 0 else f" ({pp['bonus']})" if pp['bonus'] < 0 else ""
                init_text = f" [{pp['initiative']}]" if pp['initiative'] is not None else ""
                is_current = pp['id'] == p['id']
                marker = " ▶ " if is_current else "   "
                self.participant_list.addItem(f"{marker}{pp['name']}{bonus_text}{init_text}")
            self.refresh_queue()
            # Устанавливаем текущий ход
            self.current_index = current
            self.current_turn_label.setText(f"▶ {p['name']} (иниц. {total})")
            self.turn_changed.emit(p['id'])
        else:
            # Бросок для всех
            for p in self.participants:
                total, dice, natural = self.engine.d20(p['bonus'])
                p['initiative'] = total
            self.refresh_list()
            self.refresh_queue()
            # Сортируем и устанавливаем первого
            sorted_parts = sorted(self.participants, key=lambda p: (p['initiative'] or 0, p['bonus']), reverse=True)
            if sorted_parts:
                self.current_index = 0
                self.current_turn_label.setText(f"▶ {sorted_parts[0]['name']} (иниц. {sorted_parts[0]['initiative']})")
                self.turn_changed.emit(sorted_parts[0]['id'])

    def next_turn(self) -> None:
        if not self.participants or self.current_index < 0:
            return
        sorted_parts = sorted(self.participants, key=lambda p: (p['initiative'] or 0, p['bonus']), reverse=True)
        self.current_index = (self.current_index + 1) % len(sorted_parts)
        current = sorted_parts[self.current_index]
        self.current_turn_label.setText(f"▶ {current['name']} (иниц. {current['initiative']})")
        self.refresh_queue()
        self.turn_changed.emit(current['id'])

    def reset(self) -> None:
        for p in self.participants:
            p['initiative'] = None
        self.current_index = -1
        self.current_turn_label.setText("—")
        self.refresh_list()
        self.refresh_queue()


class EncounterCalculator(QWidget):
    """Конструктор встреч: XP-бюджет партии против списка CR (таблицы 2014)."""

    def __init__(self, window=None, parent: QWidget | None = None):
        super().__init__(parent)
        self.window = window
        self._last_generated = None
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("КОНСТРУКТОР ВСТРЕЧ")
        title.setObjectName("section")
        layout.addWidget(title)

        party_row = QHBoxLayout()
        party_row.addWidget(QLabel("Уровни партии:"))
        self.party_input = QLineEdit("3, 3, 3, 4")
        self.party_input.setPlaceholderText("Например: 3, 3, 3, 4")
        party_row.addWidget(self.party_input, 1)
        layout.addLayout(party_row)

        enemy_row = QHBoxLayout()
        enemy_row.addWidget(QLabel("CR противников:"))
        self.enemy_input = QLineEdit("1/4, 1/4, 1/4, 2")
        self.enemy_input.setPlaceholderText("Например: 1/4, 1/4, 2")
        enemy_row.addWidget(self.enemy_input, 1)
        layout.addLayout(enemy_row)

        buttons = QHBoxLayout()
        calculate = QPushButton("РАССЧИТАТЬ")
        calculate.setObjectName("primary")
        calculate.clicked.connect(self.calculate)
        buttons.addWidget(calculate)
        from_scene = QPushButton("Взять со сцены")
        from_scene.setToolTip("Уровни героев и CR выставленных противников текущей кампании")
        from_scene.setEnabled(self.window is not None)
        from_scene.clicked.connect(self.fill_from_scene)
        buttons.addWidget(from_scene)
        buttons.addStretch()
        layout.addLayout(buttons)

        generator = QFrame()
        generator.setObjectName("panel")
        gen_layout = QVBoxLayout(generator)
        gen_title = QLabel("ГЕНЕРАТОР ВСТРЕЧ · подбор состава из бестиария")
        gen_title.setObjectName("section")
        gen_layout.addWidget(gen_title)

        gen_row = QHBoxLayout()
        gen_row.addWidget(QLabel("Сложность:"))
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(["лёгкая", "средняя", "тяжёлая", "смертельная"])
        self.difficulty_combo.setCurrentText("средняя")
        gen_row.addWidget(self.difficulty_combo)
        gen_row.addWidget(QLabel("Тема:"))
        self.theme_combo = QComboBox()
        for theme_id, (label, _ids) in THEMES.items():
            self.theme_combo.addItem(label, theme_id)
        gen_row.addWidget(self.theme_combo)
        gen_row.addWidget(QLabel("Макс. врагов:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(1, 12)
        self.max_spin.setValue(8)
        gen_row.addWidget(self.max_spin)
        gen_layout.addLayout(gen_row)

        seed_row = QHBoxLayout()
        seed_row.addWidget(QLabel("Сид:"))
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999)
        self.seed_spin.setValue(42)
        self.seed_spin.setToolTip("Один и тот же сид всегда даёт один и тот же состав")
        seed_row.addWidget(self.seed_spin)
        dice_seed = QPushButton("🎲 Случайный сид")
        dice_seed.clicked.connect(self.randomize_seed)
        seed_row.addWidget(dice_seed)
        seed_row.addStretch()
        gen_layout.addLayout(seed_row)

        gen_buttons = QHBoxLayout()
        roll_encounter = QPushButton("СГЕНЕРИРОВАТЬ")
        roll_encounter.setObjectName("primary")
        roll_encounter.clicked.connect(self.generate_encounter)
        gen_buttons.addWidget(roll_encounter)
        self.deploy_button = QPushButton("⚔ Вывести на сцену")
        self.deploy_button.setToolTip("Создать подобранных существ и расставить их в ряды А2/Т2")
        self.deploy_button.setEnabled(False)
        self.deploy_button.clicked.connect(self.deploy_generated)
        gen_buttons.addWidget(self.deploy_button)
        gen_buttons.addStretch()
        gen_layout.addLayout(gen_buttons)

        self.generator_label = QLabel("Задайте уровни партии слева вверху и нажмите «Сгенерировать».")
        self.generator_label.setWordWrap(True)
        self.generator_label.setObjectName("muted")
        gen_layout.addWidget(self.generator_label)
        layout.addWidget(generator)

        self.result_label = QLabel("Введите уровни героев и CR противников.")
        self.result_label.setWordWrap(True)
        self.result_label.setStyleSheet("font-family: Georgia; font-size: 15px; color: #f0e4d8; padding: 10px; background: #1a1414; border: 1px solid #3a3030;")
        layout.addWidget(self.result_label)

        self.thresholds_label = QLabel("")
        self.thresholds_label.setWordWrap(True)
        self.thresholds_label.setStyleSheet("color: #9a8e86; padding: 6px 10px; font-size: 12px;")
        layout.addWidget(self.thresholds_label, 1)

        hint = QLabel(
            "Скорректированный опыт = сырой XP × множитель численности (2 врага ×1.5, 3–6 ×2, 7–10 ×2.5).\n"
            "Сравнение идёт с порогами партии: пустяковая → лёгкая → средняя → тяжёлая → смертельная."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)

    def randomize_seed(self) -> None:
        import random as _random
        self.seed_spin.setValue(_random.randint(0, 999999))

    def generate_encounter(self) -> None:
        try:
            levels = [int(x.strip()) for x in self.party_input.text().split(",") if x.strip()]
            result = generate(
                levels,
                self.difficulty_combo.currentText(),
                theme=self.theme_combo.currentData(),
                max_monsters=self.max_spin.value(),
                seed=self.seed_spin.value(),
            )
        except (ValueError, KeyError) as exc:
            self.generator_label.setText(f"Проверьте ввод: {exc}")
            return
        self._last_generated = result
        self.enemy_input.setText(", ".join(result.monster_crs))
        self.calculate()
        composition = "; ".join(
            f"{bestiary.entry(entry_id).name} ×{count}" if count > 1 else bestiary.entry(entry_id).name
            for entry_id, count in result.picks
        )
        self.generator_label.setText(
            f"🎲 Сид {result.seed} · {composition}\n{result.report.summary}\n{result.note}"
        )
        self.deploy_button.setEnabled(self.window is not None)

    def deploy_generated(self) -> None:
        if self.window is None or self._last_generated is None:
            return
        if not self.window.is_gm():
            self.window.error("Выводить существ на сцену может только мастер")
            return
        try:
            added: list[str] = []
            for entry_id, count in self._last_generated.picks:
                for index in range(1, count + 1):
                    actor = bestiary.create(entry_id, number=index)
                    self.window.campaign.characters.append(actor)
                    zone = next((z for z in ("A2", "T2") if len(self.window.campaign.positioned(z)) < 2), "reserve")
                    self.window.campaign.battle.positions[actor.id] = zone
                    added.append(f"{actor.name} → {zone if zone != 'reserve' else 'резерв'}")
            self.window.commit(f"Сгенерированная встреча: {', '.join(added)}")
        except (KeyError, ValueError) as exc:
            self.window.error(str(exc))

    def fill_from_scene(self) -> None:
        if self.window is None:
            return
        campaign = self.window.campaign
        levels = [str(max(1, c.level)) for c in campaign.characters if c.side == "hero"]
        crs = []
        skipped = 0
        for c in campaign.characters:
            if c.side == "hero" or campaign.battle.positions.get(c.id) not in ZONES:
                continue
            if c.challenge_rating:
                crs.append(normalize_cr(c.challenge_rating))
            else:
                skipped += 1
        if levels:
            self.party_input.setText(", ".join(levels))
        if crs:
            self.enemy_input.setText(", ".join(crs))
        elif skipped:
            self.result_label.setText("На сцене нет противников с указанным CR — задайте вручную.")
        self.calculate()

    def calculate(self) -> None:
        try:
            levels = [int(x.strip()) for x in self.party_input.text().split(",") if x.strip()]
            crs = [x.strip() for x in self.enemy_input.text().split(",") if x.strip()]
            report = assess(levels, crs)
        except (ValueError, KeyError) as exc:
            self.result_label.setStyleSheet("font-family: Georgia; font-size: 14px; color: #ff9999; padding: 10px; background: #2a1a1a; border: 1px solid #cc4444;")
            self.result_label.setText(f"Проверьте ввод: {exc}")
            return
        colors = {
            "пустяковая": ("#a8b0a2", "#1a1c1a", "#4a524a"),
            "лёгкая": ("#a8d5a2", "#1a2a1a", "#4a8a4a"),
            "средняя": ("#e5c97a", "#2a2414", "#8a743a"),
            "тяжёлая": ("#e5a06a", "#2a1d14", "#8a5a3a"),
            "смертельная": ("#ff8b7b", "#2a1414", "#cc4434"),
        }
        text, background, border = colors[report.difficulty]
        self.result_label.setStyleSheet(f"font-family: Georgia; font-size: 15px; color: {text}; padding: 10px; background: {background}; border: 1px solid {border};")
        self.result_label.setText(
            f"⚔ {report.difficulty.upper()}\n"
            f"Сырой опыт: {report.raw_xp} XP  ·  скорректированный: {report.adjusted_xp} (×{report.multiplier:g} за {report.monsters})\n"
            f"Награда: {report.per_character_xp} XP на героя"
        )
        t = report.thresholds
        self.thresholds_label.setText(
            f"Пороги партии: лёгкий {t['лёгкий']} · средний {t['средний']} · тяжёлый {t['тяжёлый']} · смертельный {t['смертельный']} XP"
        )
