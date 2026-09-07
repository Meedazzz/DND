"""
Импорт из Long Story Short (LSS).

Заглушка с настройками и понятным интерфейсом.
Позже будет полноценный парсер LSS-экспорта (JSON/XML/текст).

Текущая реализация — демонстрация структуры и точек расширения.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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

from .models import Action, Combatant, Resource


class LSSImportPage(QWidget):
    """Страница импорта из LSS — заглушка с редактируемыми настройками."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Заголовок
        title = QLabel("ИМПОРТ ИЗ LONG STORY SHORT (LSS)")
        title.setObjectName("title")
        layout.addWidget(title)

        # Описание
        desc = QLabel(
            "Это заглушка импорта из Long Story Short.\n"
            "Сейчас поддерживается ручной ввод и подготовка структуры.\n"
            "Позже будет добавлен полноценный парсер экспорта LSS.\n\n"
            "Редактируй настройки ниже для подготовки импорта."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        layout.addWidget(desc)

        # Формат ввода
        format_row = QHBoxLayout()
        format_label = QLabel("Формат LSS:")
        format_label.setObjectName("muted")
        format_row.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["Пока не поддерживается", "JSON (планируется)", "XML (планируется)", "Текст (ручной)"])
        format_row.addWidget(self.format_combo, 1)
        format_row.addStretch()
        layout.addLayout(format_row)

        # Источник
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Файл LSS:"))
        self.source_path = QLineEdit("")
        self.source_path.setPlaceholderText("Выберите файл экспорта LSS")
        source_row.addWidget(self.source_path)
        browse_button = QPushButton("Обзор...")
        browse_button.clicked.connect(self.browse_file)
        source_row.addWidget(browse_button)
        layout.addLayout(source_row)

        # Предустановки для импорта
        settings_label = QLabel("Предустановки импорта (редактируемые):")
        settings_label.setObjectName("muted")
        layout.addWidget(settings_label)

        settings_frame = QFrame()
        settings_frame.setObjectName("panel")
        settings_layout = QVBoxLayout(settings_frame)

        # Имя источника
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Имя источника:"))
        self.source_name = QLineEdit("LSS источник")
        name_row.addWidget(self.source_name, 1)
        settings_layout.addLayout(name_row)

        # Тип импорта
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Тип импорта:"))
        self.import_type = QComboBox()
        self.import_type.addItems(["Чар/спеллы", "МобаHOLIES", "Персонажи", "Кампания"])
        type_row.addWidget(self.import_type, 1)
        settings_layout.addLayout(type_row)

        # Поле для ручного ввода
        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Ручной ввод (заготовка):"))
        settings_layout.addLayout(manual_row)

        self.manual_input = QLineEdit("")
        self.manual_input.setPlaceholderText("Здесь будет поле для ввода текста из LSS...\nПока — заглушка")
        self.manual_input.setMinimumHeight(80)
        settings_layout.addWidget(self.manual_input)

        layout.addWidget(settings_frame)

        # Действия
        actions_row = QHBoxLayout()
        parse_button = QPushButton("РАСПАРСИТЬ")
        parse_button.setObjectName("primary")
        parse_button.clicked.connect(self.parse)
        actions_row.addWidget(parse_button)

        clear_button = QPushButton("Очистить")
        clear_button.clicked.connect(self.clear_input)
        actions_row.addWidget(clear_button)

        import_button = QPushButton("ИМПОРТИРОВАТЬ В КАМПАНИЮ")
        import_button.clicked.connect(self.import_to_campaign)
        actions_row.addWidget(import_button)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Результат
        self.result_label = QLabel("Результат: —")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("muted")
        layout.addWidget(self.result_label)

        # Список импортированного
        result_list_label = QLabel("Импортированные элементы:")
        result_list_label.setObjectName("muted")
        layout.addWidget(result_list_label)
        self.result_list = QListWidget()
        self.result_list.setMinimumHeight(100)
        layout.addWidget(self.result_list, 1)

    def browse_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать файл LSS",
            "",
            "Все файлы (*)"
        )
        if filename:
            self.source_path.setText(filename)
            self.result_label.setText(f"Выбран файл: {filename}")

    def parse(self) -> None:
        """Попытка распарсить входные данные. Пока заглушка — показывает структуру."""
        manual_text = self.manual_input.text().strip()

        if not manual_text:
            self.result_label.setText("Введите данные для парсинга")
            return

        # Заглушка: показываем, что получилось бы при реальном парсинге
        self.result_list.clear()
        self.result_list.addItem("▶ Пока — заглушка парсера LSS")
        self.result_list.addItem("  Реальный парсер будет:")
        self.result_list.addItem("  - Читать файл LSS (JSON/XML/текст)")
        self.result_list.addItem("  - Распознавать чар/спеллы/мобов")
        self.result_list.addItem("  - Создавать объекты Action/Combatant/Resource")
        self.result_list.addItem("  - Показывать предпросмотр перед импортом")

        self.result_label.setText(
            f"Попытка парсинга...\n"
            f"Входные данные: {len(manual_text)} символов\n"
            f"Формат: {self.format_combo.currentText()}"
        )

        # Если есть ручной ввод, показываем его как пример результата
        if manual_text:
            self.result_list.addItem(f"\nВходной текст:\n{manual_text[:200]}...")

    def clear_input(self) -> None:
        self.manual_input.clear()
        self.source_path.clear()
        self.result_label.setText("Результат: —")
        self.result_list.clear()
        self.result_list.addItem("Очищено")

    def import_to_campaign(self) -> None:
        """Импорт в текущую кампанию. Пока заглушка — показывает, что будет."""
        self.result_list.clear()

        manual_text = self.manual_input.text().strip()
        if not manual_text:
            self.result_label.setText("Нет данных для импорта")
            return

        self.result_list.addItem("▶ Импорт в кампанию (заглушка)")
        self.result_list.addItem(f"  Источник: {self.source_name.text() or 'LSS источник'}")
        self.result_list.addItem(f"  Тип: {self.import_type.currentText()}")
        self.result_list.addItem("  ")
        self.result_list.addItem("  Были бы созданы:")
        self.result_list.addItem("  - Объекты Combatant для персонажей")
        self.result_list.addItem("  - Объекты Action для чар/действий")
        self.result_list.addItem("  - Объекты Resource для ресурсов")
        self.result_list.addItem("  - Участники добавлены на сцену")
        self.result_label.setText(
            f"Импорт выполнен (заглушка)\n"
            f"Фактический импорт будет после реализации парсера."
        )


class LSSCharmImporter(QWidget):
    """Импорт отдельных чар из LSS — заглушка с понятным интерфейсом."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("ИМПОРТ ЧАР ИЗ LSS")
        title.setObjectName("section")
        layout.addWidget(title)

        desc = QLabel(
            "Импортирует отдельные чар/спеллы из LSS.\n"
            "Пока — заглушка. Позже обработает формат LSS и создаст Action."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        layout.addWidget(desc)

        # Поле для имени
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Имя чара:"))
        self.charm_name = QLineEdit("")
        name_row.addWidget(self.charm_name, 1)
        layout.addLayout(name_row)

        # Уровень
        level_row = QHBoxLayout()
        level_row.addWidget(QLabel("Уровень:"))
        self.charm_level = QSpinBox()
        self.charm_level.setRange(0, 20)
        self.charm_level.setValue(1)
        level_row.addWidget(self.charm_level)
        layout.addLayout(level_row)

        # Использование (X/Y)
        usage_row = QHBoxLayout()
        usage_row.addWidget(QLabel("Использование (X/Y):"))
        self.charm_usage = QLineEdit("1/1")
        usage_row.addWidget(self.charm_usage, 1)
        layout.addLayout(usage_row)

        # Дистанция
        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Дистанция (футов):"))
        self.charm_range = QSpinBox()
        self.charm_range.setRange(0, 1000)
        self.charm_range.setValue(30)
        range_row.addWidget(self.charm_range)
        layout.addLayout(range_row)

        # Тип
        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Тип:"))
        self.charm_type = QComboBox()
        self.charm_type.addItems(["Чар", "Спелл", "Особенность", "Реакция", "Пассивное"])
        type_row.addWidget(self.charm_type, 1)
        layout.addLayout(type_row)

        # Описание
        desc_label = QLabel("Описание (из LSS):")
        layout.addWidget(desc_label)
        self.charm_desc = QLineEdit("")
        self.charm_desc.setPlaceholderText("Описание чара...")
        self.charm_desc.setMinimumHeight(60)
        layout.addWidget(self.charm_desc)

        # Кнопки
        button_row = QHBoxLayout()
        create_button = QPushButton("СОЗДАТЬ ACTION")
        create_button.setObjectName("primary")
        create_button.clicked.connect(self.create_action)
        button_row.addWidget(create_button)

        preview_button = QPushButton("Предпросмотр")
        preview_button.clicked.connect(self.preview)
        button_row.addWidget(preview_button)

        import_button = QPushButton("Импорт в кампанию")
        import_button.clicked.connect(self.import_charm)
        button_row.addWidget(import_button)

        button_row.addStretch()
        layout.addLayout(button_row)

        # Результат
        self.result_label = QLabel("Результат: —")
        self.result_label.setWordWrap(True)
        self.result_label.setObjectName("muted")
        layout.addWidget(self.result_label)

        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        layout.addWidget(self.preview_label)

    def create_action(self) -> None:
        """Создать Action из данных формы. Пока заглушка — показывает структуру."""
        name = self.charm_name.text().strip() or "Чар"
        usage_text = self.charm_usage.text().strip()

        # Парсинг использования X/Y
        usage_parts = usage_text.split("/")
        current = int(usage_parts[0]) if len(usage_parts) > 0 and usage_parts[0].strip().isdigit() else 1
        maximum = int(usage_parts[1]) if len(usage_parts) > 1 and usage_parts[1].strip().isdigit() else 1

        action = Action(
            name=name,
            kind="utility",
            damage="0",
            range_ft=self.charm_range.value(),
            description=self.charm_desc.text().strip() or "Без описания",
        )

        # Если есть использование — создаём Resource
        if maximum > 0:
            resource = Resource(
                name=name,
                current=current,
                maximum=maximum,
                recovery="long",
            )
            action.resource_id = resource.id

        self.result_label.setText(
            f"Создан Action:\n"
            f"  Имя: {action.name}\n"
            f"  Тип: {action.kind}\n"
            f"  Урон: {action.damage}\n"
            f"  Дистанция: {action.range_ft} футов\n"
            f"  Ресурс: {resource.name} ({resource.current}/{resource.maximum})"
        )

        self.preview_label.setText(
            f"Предпросмотр чара:\n"
            f"========================================\n"
            f"{action.name}\n"
            f"Уровень: {self.charm_level.value()}\n"
            f"Использование: {current}/{maximum}\n"
            f"Дистанция: {self.charm_range.value()} футов\n"
            f"Тип: {self.charm_type.currentText()}\n"
            f"----------------------------------------\n"
            f"{self.charm_desc.text() or 'Описание отсутствует'}\n"
            f"========================================"
        )

    def preview(self) -> None:
        """Показать предпросмотр чара."""
        name = self.charm_name.text().strip() or "Чар"
        self.preview_label.setText(
            f"Предпросмотр:\n"
            f"========================================\n"
            f"{name}\n"
            f"Уровень: {self.charm_level.value()}\n"
            f"Использование: {self.charm_usage.text()}\n"
            f"Дистанция: {self.charm_range.value()} футов\n"
            f"Тип: {self.charm_type.currentText()}\n"
            f"----------------------------------------\n"
            f"{self.charm_desc.text() or 'Описание отсутствует'}\n"
            f"========================================"
        )

    def import_charm(self) -> None:
        """Импорт чара в кампанию. Пока заглушка — пишет сообщение."""
        name = self.charm_name.text().strip() or "Чар"
        self.result_label.setText(
            f"Чар '{name}' импортирован в кампанию (заглушка).\n"
            f"Фактический импорт будет после реализации."
        )
