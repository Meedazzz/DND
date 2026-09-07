from __future__ import annotations

import json
import os
import shutil
import threading
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt, QTimer, Signal, QSize, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMainWindow,
    QInputDialog, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QSplitter,
    QStackedWidget, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from . import assets, bestiary, conditions
from .models import ABILITIES, Action, Campaign, Combatant, ZONES, starter_campaign, Resource
from .network import NetworkClient, NetworkError
from .parser import parse_stat_block, _parse_lss_charm_format
from .rules import BattleEngine, RuleError
from .server import create_server
from .storage import DEFAULT_SAVE, load_campaign, save_campaign
from .strategic import StrategicStage, UnitToken
from .dd_stress import DDBattleStage, DDParticipant, StressLevel, Position
from .lss_import import LSSImportPage
from .calculators import DamageCalculator, SaveDCcalculator, ACComparison, InitiativeTracker, EncounterCalculator


_PIXMAP_CACHE: dict[tuple[str, int, int], QPixmap] = {}


def load_pixmap(path: str, width: int, height: int, expand: bool = False) -> QPixmap | None:
    """Загрузить и масштабировать изображение с кэшем (интерфейс пересобирается часто)."""
    key = (path, width, height)
    if key in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[key]
    if len(_PIXMAP_CACHE) > 160:
        _PIXMAP_CACHE.clear()
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding if expand else Qt.AspectRatioMode.KeepAspectRatio
    scaled = pixmap.scaled(width, height, mode, Qt.TransformationMode.SmoothTransformation)
    _PIXMAP_CACHE[key] = scaled
    return scaled


APP_ICON_SVG = b'''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512"><rect width="512" height="512" rx="96" fill="#172023"/><path d="M95 377L190 104l66 116 66-116 95 273-98-82-63 113-63-113z" fill="#758b7e" stroke="#d2ad6d" stroke-width="18" stroke-linejoin="round"/><circle cx="256" cy="260" r="30" fill="#d2ad6d"/></svg>'''

APP_STYLE = """
* { font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: 12px; color: #ded5cb; }
QMainWindow, QWidget#root, QStackedWidget { background: #0b090a; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #171314,stop:1 #0e0c0d); border-right: 1px solid #342b2b; }
QLabel#brand { font-family: Georgia; font-size: 20px; font-weight: 700; letter-spacing: 3px; color: #eee0d0; padding: 18px 8px 2px; }
QLabel#brandAccent { color: #bc493b; font-size: 10px; font-weight: 700; letter-spacing: 4px; padding: 0 9px 18px; border-bottom: 1px solid #342b2b; }
QLabel#muted, QLabel.muted { color: #807874; }
QLabel#eyebrow { color: #c64f40; font-size: 9px; font-weight: 700; letter-spacing: 3px; }
QLabel#title { font-family: Georgia; font-size: 27px; font-weight: 700; color: #eee5d9; }
QLabel#section { font-family: Georgia; font-size: 16px; font-weight: 700; color: #decfc0; }
QFrame#topbar { background: #110f10; border-bottom: 1px solid #342d2d; }
QPushButton { background: #181516; border: 1px solid #403536; border-radius: 0px; padding: 9px 13px; color: #ada39c; }
QPushButton:hover { background: #251d1e; border-color: #705047; color: #f0e4da; }
QPushButton:pressed { background: #100e0f; }
QPushButton:disabled { color: #514a47; border-color: #2a2526; background: #121011; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #ad493c,stop:1 #742921); border-color: #c25a48; color: #fff2e9; font-weight: 700; }
QPushButton#primary:hover { background: #b84e40; }
QPushButton#danger { background: #3a1d1c; border-color: #6f3530; color: #d79d92; }
QPushButton#nav { text-align: left; border: 1px solid transparent; background: transparent; padding: 13px 12px; font-family: Georgia; font-size: 15px; color: #918681; }
QPushButton#nav:hover { background: #181415; color: #e9ddd3; }
QPushButton#nav:checked { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #39201e,stop:1 #151112); color: #f2e7dd; border-left: 3px solid #c34d3e; border-top-color: #3f2a29; border-bottom-color: #3f2a29; }
QFrame#panel { background: #151213; border: 1px solid #3a3030; }
QFrame#battlefield { background: #100c0e; border-top: 1px solid #4a3432; border-bottom: 1px solid #4a3432; }
QFrame#zone { background: transparent; border: none; }
QFrame#zone[front="true"] { background: rgba(44,26,26,40); }
QFrame#actor { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(36,29,29,230),stop:1 rgba(12,10,11,245)); border: 1px solid #57443e; }
QFrame#actor[active="true"] { border: 2px solid #b9834f; background: #2b2020; }
QFrame#actor[target="true"] { border: 2px solid #c44c3d; background: #321b1b; }
QFrame#stageConsole { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1c1617,stop:1 #0c0a0b); border-top: 1px solid #5a3834; }
QFrame#abilityCard, QPushButton#abilityCard { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2a2020,stop:1 #141011); border: 1px solid #59413b; color:#eadfd6; font-family:Georgia; font-weight:700; text-align:left; padding:9px; }
QFrame#abilityCard:hover, QPushButton#abilityCard:hover { border-color: #a84c3e; background: #38201e; }
QLabel#banner { background: #351b1a; color: #f3d5c8; border: 1px solid #704038; padding: 8px 14px; font-weight: 700; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QListWidget { background: #0d0b0c; border: 1px solid #443839; border-radius: 0px; padding: 8px; selection-background-color: #74372e; color: #e2d9d0; }
QTextEdit#sourceEditor { font-family: "Consolas", "DejaVu Sans Mono", monospace; font-size: 12px; background: #0a090a; border: 1px solid #55413e; padding: 14px; }
QTextEdit#preview { background: #151112; border: 1px solid #453535; padding: 12px; }
QScrollArea { border: none; background: transparent; }
QSplitter::handle { background: #2e2728; width: 1px; }
QListWidget::item { padding: 10px; border-bottom: 1px solid #30292a; }
QListWidget::item:selected { background: #38211f; color: #f2dfd4; border-left: 2px solid #bd4a3c; }
QMenu { background: #171415; border: 1px solid #57423e; padding: 4px; }
QMenu::item { padding: 8px 20px; }
QMenu::item:selected { background: #5f2d27; }
QDialog { background: #121011; }
QDialogButtonBox QPushButton { min-width: 100px; }
QToolTip { background: #0b090a; color: #eadcd1; border: 1px solid #654840; }
QScrollBar:vertical { background: #0d0b0c; width: 9px; }
QScrollBar::handle:vertical { background: #3b3031; min-height: 24px; }
"""


class Portrait(QWidget):
    clicked = Signal()

    def __init__(self, combatant: Combatant, parent: QWidget | None = None):
        super().__init__(parent)
        self.combatant = combatant
        self.setMinimumHeight(175)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):  # type: ignore[override]
        self.clicked.emit(); super().mousePressEvent(event)

    def paintEvent(self, event):  # type: ignore[override]
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(3, 3, -3, -3)
        # A narrow pointed arch and red/blue haze recreate the original theatrical portrait slots.
        background = QLinearGradient(0, rect.top(), 0, rect.bottom())
        if self.combatant.side == "hero":
            background.setColorAt(0, QColor("#29272b")); background.setColorAt(.55, QColor("#17171b")); background.setColorAt(1, QColor("#0a0a0c"))
        else:
            background.setColorAt(0, QColor("#38201f")); background.setColorAt(.55, QColor("#1d1112")); background.setColorAt(1, QColor("#0b090a"))
        painter.fillRect(rect, background)
        glow = QRadialGradient(rect.center().x(), int(rect.height() * .70), max(30, rect.width() * .75))
        glow.setColorAt(0, QColor(170, 64, 49, 68) if self.combatant.side != "hero" else QColor(110, 99, 91, 48)); glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)
        painter.setPen(QPen(QColor("#5c4841"), 1)); painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.top() + 30); painter.drawLine(rect.right(), rect.bottom(), rect.right(), rect.top() + 30)
        arch = QPainterPath(); arch.moveTo(rect.left(), rect.top() + 30); arch.quadTo(rect.center().x(), rect.top() - 11, rect.right(), rect.top() + 30)
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.drawPath(arch)
        drawn = False
        if self.combatant.image_path and Path(self.combatant.image_path).is_file():
            scaled = load_pixmap(self.combatant.image_path, max(1, rect.width()), max(1, rect.height()))
            if scaled and not scaled.isNull():
                painter.drawPixmap(rect.center().x() - scaled.width() // 2, rect.bottom() - scaled.height(), scaled)
                drawn = True
        if not drawn:
            placeholder = assets.portrait_path_for(self.combatant)
            if placeholder is not None:
                scaled = load_pixmap(str(placeholder), max(1, rect.width()), max(1, rect.height()), expand=True)
                if scaled and not scaled.isNull():
                    # Центральный кадр: арт заполняет слот целиком, стык скрыт под рамкой арки.
                    source = scaled if scaled.width() <= rect.width() and scaled.height() <= rect.height() else scaled.copy(
                        max(0, (scaled.width() - rect.width()) // 2), max(0, (scaled.height() - rect.height()) // 3),
                        min(scaled.width(), rect.width()), min(scaled.height(), rect.height()))
                    painter.drawPixmap(rect, source, source.rect())
                    drawn = True
        if not drawn:
            center_x = rect.center().x(); bottom = rect.bottom() - 3
            scale = min(rect.width() / 105, rect.height() / 175) * self.combatant.model_scale / 100
            silhouette = QColor("#5f5b5b" if self.combatant.side == "hero" else "#6d4b49")
            # Floor shadow.
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(0, 0, 0, 145)); painter.drawEllipse(int(center_x - 38*scale), int(bottom - 9*scale), int(76*scale), int(15*scale))
            body = QPainterPath(); body.moveTo(center_x, bottom - 119 * scale); body.quadTo(center_x - 27*scale, bottom - 98*scale, center_x - 38*scale, bottom - 18*scale); body.quadTo(center_x, bottom + 2*scale, center_x + 38*scale, bottom - 18*scale); body.quadTo(center_x + 26*scale, bottom - 98*scale, center_x, bottom - 119*scale); body.closeSubpath()
            painter.setBrush(silhouette.darker(145)); painter.setPen(QPen(silhouette.lighter(112), max(1, int(scale)))); painter.drawPath(body)
            painter.drawEllipse(int(center_x - 15*scale), int(bottom - 149*scale), int(30*scale), int(34*scale))
            # Weapon and optional boss horns are deliberately abstract rather than borrowed artwork.
            painter.setPen(QPen(QColor("#8e7b66"), max(1, int(2*scale)))); painter.drawLine(int(center_x + 25*scale), int(bottom - 91*scale), int(center_x + 47*scale), int(bottom - 158*scale))
            if self.combatant.is_boss:
                painter.setPen(QPen(QColor("#8f574c"), max(1, int(2*scale)))); painter.drawLine(int(center_x - 9*scale), int(bottom - 145*scale), int(center_x - 22*scale), int(bottom - 169*scale)); painter.drawLine(int(center_x + 9*scale), int(bottom - 145*scale), int(center_x + 22*scale), int(bottom - 169*scale))
        painter.setBrush(Qt.BrushStyle.NoBrush); painter.setPen(QPen(QColor("#9e7a61"), 1)); painter.drawRect(rect)
        if self.combatant.model_path:
            painter.setPen(QColor("#c5a170")); painter.setFont(QFont("Segoe UI", 8)); painter.drawText(rect.adjusted(5, 4, -5, -4), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop, "3D")
        painter.end()


class ImportDialog(QDialog):
    """Large, audit-first stat-block import — the primary creature workflow."""
    def __init__(self, side: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Новый участник · импорт полного статблока")
        self.resize(1120, 720)
        self._last_result = None
        root = QVBoxLayout(self); root.setContentsMargins(18, 16, 18, 16); root.setSpacing(10)
        eyebrow = QLabel("БЫСТРЫЙ СБОР ЛИСТА"); eyebrow.setObjectName("eyebrow"); root.addWidget(eyebrow)
        heading = QHBoxLayout()
        title_block = QVBoxLayout(); title = QLabel("Вставьте описание целиком"); title.setObjectName("title"); title_block.addWidget(title)
        hint = QLabel("Русский или English · можно одним непрерывным абзацем. Исходник сохраняется дословно; неуказанные данные не выдумываются.")
        hint.setObjectName("muted"); hint.setWordWrap(True); title_block.addWidget(hint); heading.addLayout(title_block, 1)
        self.side = QComboBox(); self.side.setMinimumWidth(190)
        self.side.addItem("Герой", "hero"); self.side.addItem("Моб", "enemy"); self.side.addItem("Элита", "enemy"); self.side.addItem("Босс", "enemy")
        self.side.setCurrentIndex(0 if side == "hero" else (3 if side == "boss" else 1))
        self.side.currentIndexChanged.connect(self._schedule_preview)
        heading.addWidget(QLabel("РОЛЬ")); heading.addWidget(self.side); root.addLayout(heading)

        split = QSplitter(); split.setChildrenCollapsible(False)
        source_panel = QFrame(); source_panel.setObjectName("panel"); source_layout = QVBoxLayout(source_panel)
        source_title = QLabel("01  ИСХОДНЫЙ ТЕКСТ"); source_title.setObjectName("section"); source_layout.addWidget(source_title)
        self.text = QTextEdit(); self.text.setObjectName("sourceEditor")
        self.text.setPlaceholderText("Вставьте сюда полный статблок из книги или свой текст: имя, размер/тип, КД, ОЗ, скорость, характеристики, защиты, ресурсы, действия, реакции и легендарные действия…")
        self.text.textChanged.connect(self._schedule_preview); source_layout.addWidget(self.text, 1)
        preservation = QLabel("Знак дословности  ✓  Текст будет сохранён без нормализации и доступен в листе.")
        preservation.setObjectName("muted"); preservation.setWordWrap(True); source_layout.addWidget(preservation)
        split.addWidget(source_panel)

        preview_panel = QFrame(); preview_panel.setObjectName("panel"); preview_layout = QVBoxLayout(preview_panel)
        preview_header = QHBoxLayout(); preview_title = QLabel("02  ПРЕДПРОСМОТР И АУДИТ"); preview_title.setObjectName("section"); preview_header.addWidget(preview_title, 1)
        parse_button = QPushButton("Разобрать текст"); parse_button.clicked.connect(self.update_preview); preview_header.addWidget(parse_button)
        preview_layout.addLayout(preview_header)
        self.preview = QTextEdit(); self.preview.setObjectName("preview"); self.preview.setReadOnly(True)
        self.preview.setHtml("<h3>Предпросмотр появится здесь</h3><p>Распознанные поля будут отделены от допущений и предупреждений.</p>")
        preview_layout.addWidget(self.preview, 1); split.addWidget(preview_panel)
        split.setSizes([550, 550]); root.addWidget(split, 1)

        bottom = QHBoxLayout()
        audit_note = QLabel("Импорт создаёт редактируемый боевой лист. Любую ошибку можно исправить после добавления.")
        audit_note.setObjectName("muted"); audit_note.setWordWrap(True); bottom.addWidget(audit_note, 1)
        cancel = QPushButton("Отмена"); cancel.clicked.connect(self.reject); bottom.addWidget(cancel)
        accept = QPushButton("Добавить на сцену"); accept.setObjectName("primary"); accept.clicked.connect(self._accept_if_valid); bottom.addWidget(accept)
        root.addLayout(bottom)
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(450); self._timer.timeout.connect(self.update_preview)

    @property
    def boss_selected(self) -> bool:
        return self.side.currentIndex() == 3

    def _schedule_preview(self) -> None:
        self._timer.start()

    def _accept_if_valid(self) -> None:
        self.update_preview()
        if self._last_result is not None:
            self.accept()

    def update_preview(self) -> None:
        import html
        source = self.text.toPlainText()
        if not source.strip():
            self._last_result = None
            self.preview.setHtml("<h3>Вставьте статблок</h3><p>Поддерживается непрерывный русский и английский текст.</p>")
            return
        try:
            result = parse_stat_block(source, self.side.currentData())
        except ValueError as exc:
            self._last_result = None
            self.preview.setHtml(f"<h3 style='color:#cf6657'>Не удалось разобрать</h3><p>{html.escape(str(exc))}</p>")
            return
        self._last_result = result; c = result.combatant
        if self.boss_selected: c.is_boss = True
        role = self.side.currentText().upper()
        ability = " &nbsp; ".join(f"<b>{key.upper()}</b> {c.stats[key]}" for key in ABILITIES)
        resource_lines = "".join(f"<li>{html.escape(r.name)}: <b>{r.current}/{r.maximum}</b> · {html.escape(r.recovery)}</li>" for r in c.resources) or "<li>Не найдены</li>"
        section_ru = {"actions": "действие", "bonus": "бонусное", "reactions": "реакция", "legendary": "легендарное"}
        kind_ru = {"attack": "атака", "save": "спасбросок", "damage": "урон", "heal": "лечение", "utility": "особое"}
        action_lines = "".join(
            f"<li><b>{html.escape(a.name)}</b> · {section_ru.get(a.section, html.escape(a.section))} · {kind_ru.get(a.kind, html.escape(a.kind))} · "
            f"{html.escape(a.damage)}{(' · перезарядка '+html.escape(a.recharge)) if a.recharge else ''}</li>" for a in c.actions
        ) or "<li>Не найдены — сохранённый исходник позволит добавить их вручную</li>"
        found = " · ".join(html.escape(x) for x in result.found) or "нет"
        warnings = "".join(f"<li>{html.escape(x)}</li>" for x in result.warnings) or "<li>Нет предупреждений</li>"
        identity = " · ".join(x for x in (c.creature_size, c.creature_type, c.alignment) if x)
        self.preview.setHtml(f"""
        <div style='color:#d9cec4'>
          <p style='color:#b94d3f;letter-spacing:2px'><b>{role}</b></p>
          <h1 style='font-family:Georgia;color:#f0e4d8'>{html.escape(c.name)}</h1>
          <p style='color:#91847f'>{html.escape(identity or c.class_name or 'тип не указан')}</p>
          <table cellspacing='8'><tr><td><b>КД</b><br>{c.armor_class}</td><td><b>ОЗ</b><br>{c.hp}/{c.max_hp}</td><td><b>Скорость</b><br>{c.speed} фт</td><td><b>CR</b><br>{html.escape(c.challenge_rating or '—')}</td></tr></table>
          <p>{ability}</p><hr>
          <h3>Ресурсы</h3><ul>{resource_lines}</ul>
          <h3>Боевые действия</h3><ul>{action_lines}</ul>
          <h3 style='color:#c5a16f'>Распознано</h3><p>{found}</p>
          <h3 style='color:#c56c5e'>Проверить</h3><ul>{warnings}</ul>
        </div>""")


class CharacterDialog(QDialog):
    def __init__(self, combatant: Combatant, parent: QWidget | None = None):
        super().__init__(parent)
        self.character = combatant
        self.setWindowTitle("Редактирование персонажа")
        self.resize(600, 620)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(combatant.name)
        self.side = QComboBox(); self.side.addItem("Герой", "hero"); self.side.addItem("Противник", "enemy"); self.side.setCurrentIndex(0 if combatant.side == "hero" else 1)
        self.class_name = QLineEdit(combatant.class_name)
        self.ac = QSpinBox(); self.ac.setRange(0, 99); self.ac.setValue(combatant.armor_class)
        self.hp = QSpinBox(); self.hp.setRange(0, 99999); self.hp.setValue(combatant.hp)
        self.max_hp = QSpinBox(); self.max_hp.setRange(1, 99999); self.max_hp.setValue(combatant.max_hp)
        self.speed = QSpinBox(); self.speed.setRange(0, 500); self.speed.setSingleStep(5); self.speed.setValue(combatant.speed)
        self.conditions = QLineEdit(", ".join(combatant.conditions))
        self.scale = QSpinBox(); self.scale.setRange(25, 250); self.scale.setValue(combatant.model_scale); self.scale.setSuffix(" %")
        self.image = QLineEdit(combatant.image_path)
        self.model = QLineEdit(combatant.model_path)
        self.boss = QComboBox(); self.boss.addItem("Нет", False); self.boss.addItem("Да", True); self.boss.setCurrentIndex(1 if combatant.is_boss else 0)
        for label, widget in (("Имя", self.name), ("Сторона", self.side), ("Класс / тип", self.class_name), ("КД", self.ac), ("Текущие ОЗ", self.hp), ("Максимум ОЗ", self.max_hp), ("Скорость", self.speed), ("Состояния через запятую", self.conditions), ("Масштаб фигуры", self.scale), ("PNG/JPG/WebP", self.image), ("GLB/GLTF (сохраняется как вложение)", self.model), ("Босс", self.boss)):
            form.addRow(label, widget)
        root.addLayout(form)
        media_row = QHBoxLayout()
        choose_image = QPushButton("Выбрать изображение")
        choose_image.clicked.connect(lambda: self._choose(self.image, "Изображения (*.png *.jpg *.jpeg *.webp)"))
        choose_model = QPushButton("Выбрать модель")
        choose_model.clicked.connect(lambda: self._choose(self.model, "3D-модели (*.glb *.gltf)"))
        media_row.addWidget(choose_image); media_row.addWidget(choose_model)
        root.addLayout(media_row)
        action_hint = QLabel("Действия и ресурсы редактируются в листе персонажа. Ручные изменения не переписывают сохранённый исходный текст импорта.")
        action_hint.setWordWrap(True); action_hint.setObjectName("muted")
        root.addWidget(action_hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _choose(self, field: QLineEdit, file_filter: str) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", file_filter)
        if filename:
            field.setText(filename)

    def apply(self) -> Combatant:
        c = self.character
        c.name = self.name.text().strip() or "Безымянный"
        c.side = self.side.currentData()
        c.class_name = self.class_name.text().strip()
        c.armor_class = self.ac.value(); c.max_hp = self.max_hp.value(); c.hp = min(self.hp.value(), c.max_hp)
        c.speed = self.speed.value(); c.conditions = [x.strip() for x in self.conditions.text().split(",") if x.strip()]
        c.model_scale = self.scale.value(); c.image_path = self.image.text().strip(); c.model_path = self.model.text().strip(); c.is_boss = bool(self.boss.currentData())
        return c


class ActionDialog(QDialog):
    def __init__(self, actor: Combatant, action: Action | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self.actor = actor
        self.action = action or Action(name="Новое действие")
        self.setWindowTitle("Действие персонажа")
        self.resize(560, 690)
        root = QVBoxLayout(self); form = QFormLayout()
        self.name = QLineEdit(self.action.name)
        self.kind = QComboBox()
        for label, value in (("Атака против КД", "attack"), ("Спасбросок", "save"), ("Прямой урон", "damage"), ("Лечение", "heal"), ("Особое действие", "utility")):
            self.kind.addItem(label, value)
        self.kind.setCurrentIndex(max(0, self.kind.findData(self.action.kind)))
        self.attack = QSpinBox(); self.attack.setRange(-20, 40); self.attack.setValue(self.action.attack_bonus or 0); self.attack.setPrefix("+")
        self.damage = QLineEdit(self.action.damage)
        self.damage_type = QLineEdit(self.action.damage_type)
        self.section = QComboBox()
        for label, value in (("Действие", "actions"), ("Бонусное действие", "bonus"), ("Реакция", "reactions"), ("Легендарное действие", "legendary")):
            self.section.addItem(label, value)
        self.section.setCurrentIndex(max(0, self.section.findData(self.action.section)))
        self.recharge = QLineEdit(self.action.recharge); self.recharge.setPlaceholderText("Например: 5-6")
        self.range = QSpinBox(); self.range.setRange(5, 1000); self.range.setSingleStep(5); self.range.setValue(self.action.range_ft); self.range.setSuffix(" фт")
        self.save_ability = QComboBox()
        for key, label in (("str", "СИЛ"), ("dex", "ЛОВ"), ("con", "ТЕЛ"), ("int", "ИНТ"), ("wis", "МДР"), ("cha", "ХАР")):
            self.save_ability.addItem(label, key)
        self.save_ability.setCurrentIndex(max(0, self.save_ability.findData(self.action.save_ability or "dex")))
        self.save_dc = QSpinBox(); self.save_dc.setRange(1, 40); self.save_dc.setValue(self.action.save_dc or 10)
        self.half = QCheckBox("Половина урона при успешном спасброске"); self.half.setChecked(self.action.half_on_save)
        self.resource = QComboBox(); self.resource.addItem("Без расхода", "")
        for item in actor.resources:
            self.resource.addItem(f"{item.name} · {item.current}/{item.maximum}", item.id)
        self.resource.setCurrentIndex(max(0, self.resource.findData(self.action.resource_id)))
        self.description = QTextEdit(self.action.description); self.description.setMaximumHeight(100)
        for label, widget in (("Название", self.name), ("Тип", self.kind), ("Раздел / экономика", self.section), ("Бонус атаки", self.attack), ("Урон / лечение", self.damage), ("Тип урона", self.damage_type), ("Перезарядка", self.recharge), ("Дистанция", self.range), ("Характеристика спасброска", self.save_ability), ("Сл", self.save_dc), ("При успехе", self.half), ("Ресурс", self.resource), ("Описание", self.description)):
            form.addRow(label, widget)
        root.addLayout(form)
        hint = QLabel("Формулы: 1d8+3, 2d6, 3d10-2. Для особого действия формула не бросается автоматически.")
        hint.setWordWrap(True); hint.setObjectName("muted"); root.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def apply(self) -> Action:
        action = self.action
        action.name = self.name.text().strip() or "Действие"
        action.kind = self.kind.currentData(); action.damage = self.damage.text().strip() or "0"
        action.damage_type = self.damage_type.text().strip(); action.section = self.section.currentData(); action.recharge = self.recharge.text().strip()
        action.range_ft = self.range.value(); action.resource_id = self.resource.currentData() or ""
        action.description = self.description.toPlainText()
        action.attack_bonus = self.attack.value() if action.kind == "attack" else None
        action.save_ability = self.save_ability.currentData() if action.kind == "save" else ""
        action.save_dc = self.save_dc.value() if action.kind == "save" else None
        action.half_on_save = self.half.isChecked() if action.kind == "save" else False
        return action


class ResourceDialog(QDialog):
    def __init__(self, resource=None, parent: QWidget | None = None):
        from .models import Resource
        super().__init__(parent)
        self.resource = resource or Resource(name="Новый ресурс")
        self.setWindowTitle("Ограниченный ресурс")
        root = QVBoxLayout(self); form = QFormLayout()
        self.name = QLineEdit(self.resource.name)
        self.current = QSpinBox(); self.current.setRange(0, 999); self.current.setValue(self.resource.current)
        self.maximum = QSpinBox(); self.maximum.setRange(1, 999); self.maximum.setValue(self.resource.maximum)
        self.recovery = QComboBox(); self.recovery.addItem("Короткий отдых", "short"); self.recovery.addItem("Долгий отдых", "long"); self.recovery.setCurrentIndex(max(0, self.recovery.findData(self.resource.recovery)))
        form.addRow("Название", self.name); form.addRow("Сейчас", self.current); form.addRow("Максимум", self.maximum); form.addRow("Восстановление", self.recovery); root.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def apply(self):
        self.resource.name = self.name.text().strip() or "Ресурс"
        self.resource.maximum = self.maximum.value(); self.resource.current = min(self.current.value(), self.resource.maximum); self.resource.recovery = self.recovery.currentData()
        return self.resource


class ConditionsDialog(QDialog):
    """Выбор состояний по каталогу D&D 5e с поиском, описаниями и своими отметками."""

    def __init__(self, actor: Combatant, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"Состояния · {actor.name}")
        self.resize(680, 560)
        root = QVBoxLayout(self); root.setContentsMargins(16, 14, 16, 14); root.setSpacing(8)
        heading = QLabel("Каталог состояний"); heading.setObjectName("title"); root.addWidget(heading)
        hint = QLabel("Отметьте состояния из правил 2014/2024 или добавьте свои через запятую. Трактовка спорных случаев остаётся за мастером.")
        hint.setWordWrap(True); hint.setObjectName("muted"); root.addWidget(hint)
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск: испуг, prone, ослеп…")
        self.search.textChanged.connect(self._rebuild); root.addWidget(self.search)
        known, custom = conditions.split_known(actor.conditions)
        self._boxes: dict[str, QCheckBox] = {}
        self._rows: dict[str, QFrame] = {}
        self.scroll_area = QScrollArea(); self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget(); self.scroll_layout = QVBoxLayout(self.scroll_content); self.scroll_layout.setSpacing(2)
        self.scroll_area.setWidget(self.scroll_content); root.addWidget(self.scroll_area, 1)
        for condition in conditions.all():
            box = QCheckBox(condition.name_ru); box.setChecked(condition.name_ru in known)
            row = QFrame(); row.setObjectName("panel"); row_layout = QVBoxLayout(row); row_layout.setContentsMargins(10, 6, 10, 6); row_layout.setSpacing(1)
            title_row = QHBoxLayout(); title_row.addWidget(box)
            eng = QLabel(condition.name_en + (" · служебная" if condition.special else "")); eng.setObjectName("muted"); title_row.addWidget(eng); title_row.addStretch()
            row_layout.addLayout(title_row)
            summary = QLabel(condition.summary); summary.setWordWrap(True); summary.setStyleSheet("color:#9a8e86;font-size:11px"); row_layout.addWidget(summary)
            self.scroll_layout.addWidget(row)
            self._boxes[condition.name_ru] = box; self._rows[condition.name_ru] = row
        self.scroll_layout.addStretch()
        custom_row = QHBoxLayout(); custom_row.addWidget(QLabel("Свои отметки:"))
        self.custom = QLineEdit(", ".join(custom)); self.custom.setPlaceholderText("Например: Горение 1d6, Метка охотника")
        custom_row.addWidget(self.custom, 1); root.addLayout(custom_row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._rebuild()

    def _rebuild(self) -> None:
        visible = {c.name_ru for c in conditions.search(self.search.text())}
        for name, row in self._rows.items():
            row.setVisible(name in visible)

    def selected(self) -> list[str]:
        chosen = [name for name, box in self._boxes.items() if box.isChecked()]
        chosen.extend(x.strip() for x in self.custom.text().split(",") if x.strip())
        return chosen


class BestiaryDialog(QDialog):
    """Встроенный бестиарий: готовые существа с предпросмотром и выводом на сцену."""

    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.window = window
        self.chosen_id = ""
        self.setWindowTitle("Бестиарий «Драконьей Саги»")
        self.resize(1000, 640)
        root = QVBoxLayout(self); root.setContentsMargins(18, 16, 18, 16); root.setSpacing(10)
        eyebrow = QLabel("ГОТОВЫЕ СУЩЕСТВА · МОБЫ / ЭЛИТА / БОССЫ"); eyebrow.setObjectName("eyebrow"); root.addWidget(eyebrow)
        head = QHBoxLayout()
        title = QLabel("Бестиарий"); title.setObjectName("title"); head.addWidget(title, 1)
        self.filter = QComboBox(); self.filter.addItem("Все ранги", ""); self.filter.addItem("Мобы", "mob"); self.filter.addItem("Элита", "elite"); self.filter.addItem("Боссы", "boss")
        self.filter.currentIndexChanged.connect(self._rebuild); head.addWidget(self.filter)
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск по имени…"); self.search.setMinimumWidth(200)
        self.search.textChanged.connect(self._rebuild); head.addWidget(self.search); root.addLayout(head)
        split = QSplitter(); split.setChildrenCollapsible(False)
        self.listing = QListWidget(); self.listing.currentRowChanged.connect(self._preview); split.addWidget(self.listing)
        self.preview = QTextEdit(); self.preview.setObjectName("preview"); self.preview.setReadOnly(True); split.addWidget(self.preview)
        split.setSizes([360, 560]); root.addWidget(split, 1)
        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("Количество:"))
        self.count = QSpinBox(); self.count.setRange(1, 6); self.count.setValue(1); bottom.addWidget(self.count)
        note = QLabel("Портретная заглушка и позиция подбираются по рангу; при группе существа нумеруются римскими цифрами.")
        note.setWordWrap(True); note.setObjectName("muted"); bottom.addWidget(note, 1)
        cancel = QPushButton("Отмена"); cancel.clicked.connect(self.reject); bottom.addWidget(cancel)
        accept = QPushButton("Вывести на сцену"); accept.setObjectName("primary"); accept.clicked.connect(self._accept); bottom.addWidget(accept)
        root.addLayout(bottom)
        self._rebuild()

    def _rank_label(self, rank: str) -> str:
        return {"mob": "моб", "elite": "элита", "boss": "босс"}[rank]

    def _rebuild(self) -> None:
        self.listing.clear()
        rank = self.filter.currentData()
        needle = self.search.text().strip().lower()
        for entry in bestiary.entries():
            if rank and entry.rank != rank:
                continue
            if needle and needle not in entry.name.lower() and needle not in entry.blurb.lower():
                continue
            self.listing.addItem(f"{entry.name}\n{self._rank_label(entry.rank)} · CR {entry.cr}")
            self.listing.item(self.listing.count() - 1).setData(Qt.ItemDataRole.UserRole, entry.id)
        if self.listing.count():
            self.listing.setCurrentRow(0)
        else:
            self.preview.setHtml("<h3>Ничего не найдено</h3><p>Смягчите фильтр или запрос.</p>")

    def _preview(self, row: int) -> None:
        item = self.listing.item(row)
        if not item:
            return
        entry_id = item.data(Qt.ItemDataRole.UserRole)
        self.preview.setHtml(bestiary.preview_html(entry_id))

    def _accept(self) -> None:
        item = self.listing.currentItem()
        if not item:
            return
        self.chosen_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class BattleStage(QFrame):
    """Procedural gothic battle stage; no bundled or external artwork is required."""
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent); self.setObjectName("battlefield"); self.setMinimumHeight(390)

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        backdrop = assets.backdrop_path()
        backdrop_drawn = False
        if backdrop is not None:
            scaled = load_pixmap(str(backdrop), max(1, rect.width()), max(1, rect.height()), expand=True)
            if scaled and not scaled.isNull():
                source = scaled if scaled.width() <= rect.width() and scaled.height() <= rect.height() else scaled.copy(
                    max(0, (scaled.width() - rect.width()) // 2), max(0, (scaled.height() - rect.height()) // 2),
                    min(scaled.width(), rect.width()), min(scaled.height(), rect.height()))
                painter.drawPixmap(rect, source, source.rect())
                backdrop_drawn = True
        if backdrop_drawn:
            # Театральная вуаль: сцена затемняется, чтобы карточки и ряды оставались читаемыми.
            veil = QLinearGradient(0, rect.top(), 0, rect.bottom())
            veil.setColorAt(0, QColor(9, 7, 8, 165)); veil.setColorAt(.55, QColor(12, 9, 10, 120)); veil.setColorAt(1, QColor(9, 7, 8, 205))
            painter.fillRect(rect, veil)
            seam = QRadialGradient(rect.center().x(), int(rect.height() * .54), rect.width() * .30)
            seam.setColorAt(0, QColor(156, 48, 38, 40)); seam.setColorAt(1, QColor(0, 0, 0, 0)); painter.fillRect(rect, seam)
            painter.setPen(QPen(QColor(177, 73, 57, 110), 2)); painter.drawLine(rect.center().x(), rect.top() + 60, rect.center().x(), rect.bottom() - 8)
            painter.setPen(QPen(QColor("#513a36"), 1)); painter.drawRect(rect); painter.end()
            return
        sky = QLinearGradient(0, rect.top(), 0, rect.bottom())
        sky.setColorAt(0, QColor("#080708")); sky.setColorAt(.42, QColor("#1a1012")); sky.setColorAt(.72, QColor("#231517")); sky.setColorAt(1, QColor("#080708")); painter.fillRect(rect, sky)
        # A dim blood-red light sits behind the opposing front lines.
        glow = QRadialGradient(rect.center().x(), int(rect.height() * .54), rect.width() * .34)
        glow.setColorAt(0, QColor(156, 48, 38, 62)); glow.setColorAt(.55, QColor(93, 30, 29, 28)); glow.setColorAt(1, QColor(0, 0, 0, 0)); painter.fillRect(rect, glow)
        horizon = rect.top() + int(rect.height() * .62)
        # Ruined pillars, arches, and hanging iron lines create an original gothic set.
        painter.setPen(Qt.PenStyle.NoPen)
        for x in (rect.left() + int(rect.width()*.06), rect.left() + int(rect.width()*.19), rect.left() + int(rect.width()*.81), rect.left() + int(rect.width()*.94)):
            width = max(10, int(rect.width()*.025)); painter.setBrush(QColor(31, 25, 26, 225)); painter.drawRect(x-width//2, rect.top()+34, width, horizon-rect.top()-18)
            painter.setBrush(QColor(54, 39, 39, 190)); painter.drawRect(x-width, rect.top()+29, width*2, 8)
        painter.setPen(QPen(QColor(72, 50, 49, 125), max(2, int(rect.width()*.004))))
        for left, right in ((.06,.19),(.81,.94)):
            path=QPainterPath(); path.moveTo(rect.left()+int(rect.width()*left), rect.top()+115); path.quadTo(rect.left()+int(rect.width()*(left+right)/2), rect.top()+36, rect.left()+int(rect.width()*right), rect.top()+115); painter.drawPath(path)
        painter.setPen(QPen(QColor(70, 47, 45, 90), 1))
        for index in range(9):
            x=rect.left()+int((index+.5)*rect.width()/9); painter.drawLine(x, rect.top(), x, rect.top()+20+(index%3)*13)
        # Stone floor with perspective guides and a central confrontation seam.
        floor = QLinearGradient(0, horizon, 0, rect.bottom()); floor.setColorAt(0, QColor("#241a1b")); floor.setColorAt(1, QColor("#0b090a")); painter.fillRect(rect.left(), horizon, rect.width(), rect.bottom()-horizon, floor)
        painter.setPen(QPen(QColor(107, 73, 65, 56), 1))
        for index in range(1, 8):
            y=horizon+int((rect.bottom()-horizon)*(index/8)**1.6); painter.drawLine(rect.left(), y, rect.right(), y)
        for index in range(-5,6):
            painter.drawLine(rect.center().x(), horizon, rect.center().x()+index*int(rect.width()*.12), rect.bottom())
        painter.setPen(QPen(QColor(177, 73, 57, 100), 2)); painter.drawLine(rect.center().x(), rect.top()+60, rect.center().x(), rect.bottom()-8)
        painter.setPen(QPen(QColor("#513a36"), 1)); painter.drawRect(rect); painter.end()


class DiceSidebar(QFrame):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        self.window = window
        self.setObjectName("panel")
        self.setFixedWidth(280)
        root = QVBoxLayout(self)
        title = QLabel("КУБЫ И РЕЗУЛЬТАТЫ"); title.setObjectName("section")
        root.addWidget(title)
        grid = QGridLayout()
        for index, die in enumerate((4, 6, 8, 10, 12, 20, 100)):
            button = QPushButton(f"d{die}")
            button.clicked.connect(lambda _=False, d=die: self.roll(f"1d{d}"))
            grid.addWidget(button, index // 3, index % 3)
        root.addLayout(grid)
        row = QHBoxLayout()
        self.formula = QLineEdit("1d20+5")
        roll = QPushButton("Бросить"); roll.setObjectName("primary"); roll.clicked.connect(lambda: self.roll(self.formula.text()))
        row.addWidget(self.formula, 1); row.addWidget(roll)
        root.addLayout(row)
        self.results = QListWidget()
        root.addWidget(self.results, 1)
        self.refresh()

    def roll(self, formula: str) -> None:
        try:
            value = self.window.engine.roll(formula)
            self.window.campaign.recent_rolls.insert(0, str(value))
            self.window.campaign.recent_rolls = self.window.campaign.recent_rolls[:30]
            self.window.commit("Бросок выполнен")
        except RuleError as exc:
            self.window.error(str(exc))

    def refresh(self) -> None:
        self.results.clear()
        self.results.addItems(self.window.campaign.recent_rolls or ["Здесь появятся броски и результаты действий."])


class ActorCard(QFrame):
    def __init__(self, window: "MainWindow", actor: Combatant):
        super().__init__(); self.window, self.actor = window, actor
        self.setObjectName("actor"); self.setMinimumWidth(118); self.setMaximumWidth(205)
        active = window.engine.active_actor(); self.setProperty("active", bool(active and active.id == actor.id)); self.setProperty("target", window.campaign.battle.target_id == actor.id)
        root = QVBoxLayout(self); root.setContentsMargins(5, 5, 5, 6); root.setSpacing(4)
        if actor.is_boss or actor.rank == "boss":
            rank_label = "◆ БОСС"
        elif actor.side == "hero":
            rank_label = "ГЕРОЙ"
        elif actor.rank == "elite":
            rank_label = "✦ ЭЛИТА"
        else:
            rank_label = "ПРОТИВНИК"
        marker = QLabel(rank_label)
        marker.setAlignment(Qt.AlignmentFlag.AlignCenter); marker.setStyleSheet("color:#b87562;font-size:8px;font-weight:700;letter-spacing:2px")
        root.addWidget(marker)
        portrait = Portrait(actor); portrait.clicked.connect(lambda: window.select_actor(actor.id)); root.addWidget(portrait, 1)
        # Zero-width break opportunities keep long Russian/German-style names readable on 1120 px desktops.
        display_name = " ".join("\u200b".join(word[index:index + 9] for index in range(0, len(word), 9)) for word in actor.name.upper().split())
        name = QLabel(display_name); name.setAlignment(Qt.AlignmentFlag.AlignCenter); name.setWordWrap(True); name.setStyleSheet("font-family:Georgia;font-weight:700;color:#eee0d0;font-size:12px")
        root.addWidget(name)
        hp = QLabel(f"{actor.hp} / {actor.max_hp} ОЗ     КД {actor.armor_class}"); hp.setAlignment(Qt.AlignmentFlag.AlignCenter); hp.setStyleSheet("font-size:10px;color:#b4a7a0"); root.addWidget(hp)
        ratio = max(0, min(1, actor.hp / max(1, actor.max_hp)))
        meter = QFrame(); meter.setFixedHeight(5); meter.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #a53f32,stop:{ratio:.3f} #a53f32,stop:{ratio:.3f} #302526,stop:1 #302526);border:1px solid #1a1516")
        root.addWidget(meter)
        if actor.telegraph:
            warning = QLabel(f"⚠ {actor.telegraph} · Сл {actor.telegraph_dc}"); warning.setWordWrap(True); warning.setAlignment(Qt.AlignmentFlag.AlignCenter); warning.setStyleSheet("color:#d5a365;font-size:9px;font-weight:700"); root.addWidget(warning)
        if actor.hp == 0 and "Мёртв" not in actor.conditions and "Стабилизирован" not in actor.conditions:
            successes, failures = window.engine.death_status(actor.id)
            dying = QLabel(f"☠ ПРИ СМЕРТИ  ✓{successes}  ✗{failures}"); dying.setAlignment(Qt.AlignmentFlag.AlignCenter); dying.setStyleSheet("color:#c94f41;font-size:9px;font-weight:700;letter-spacing:1px"); root.addWidget(dying)
        if actor.conditions:
            condition = QLabel(" · ".join(actor.conditions[:2])); condition.setAlignment(Qt.AlignmentFlag.AlignCenter); condition.setWordWrap(True); condition.setStyleSheet("color:#b86a5e;font-size:9px"); root.addWidget(condition)
        controls = QHBoxLayout(); controls.setSpacing(2)
        minus = QPushButton("−"); minus.setFixedSize(27, 25); minus.setStyleSheet("padding:1px;font-size:12px"); minus.setToolTip("Уменьшить ОЗ на 1"); minus.setEnabled(window.can_control(actor)); minus.clicked.connect(lambda: window.change_hp(actor.id, -1)); controls.addWidget(minus)
        action = QPushButton("ХОД"); action.setStyleSheet("padding:1px 2px;font-size:9px;font-weight:700"); action.setToolTip("Выбрать и выполнить действие в один клик"); action.setEnabled(window.can_control(actor)); action.clicked.connect(lambda: window.use_primary_action(actor.id)); controls.addWidget(action, 1)
        more = QPushButton("•••"); more.setFixedSize(29, 25); more.setStyleSheet("padding:1px;font-size:8px"); more.setEnabled(window.can_control(actor)); more.clicked.connect(lambda: window.actor_menu(actor, more)); controls.addWidget(more)
        root.addLayout(controls)


class ZoneFrame(QFrame):
    def __init__(self, window: "MainWindow", zone: str, title: str, subtitle: str):
        super().__init__(); self.zone = zone; self.setObjectName("zone"); self.setProperty("front", zone in ("A1", "A2"))
        root = QVBoxLayout(self); root.setContentsMargins(5, 6, 5, 8); root.setSpacing(4)
        label = QLabel(f"{zone}  {title.upper()}"); label.setAlignment(Qt.AlignmentFlag.AlignCenter); label.setStyleSheet("font-family:Georgia;font-weight:700;color:#9b8880;font-size:10px;letter-spacing:1px")
        root.addWidget(label)
        occupants = window.campaign.positioned(zone)
        actor_row = QHBoxLayout(); actor_row.setSpacing(5); actor_row.setContentsMargins(0, 0, 0, 0)
        if occupants:
            for actor in occupants[:2]: actor_row.addWidget(ActorCard(window, actor), 1)
            if len(occupants) == 1: actor_row.addStretch(1)
        else:
            empty = QLabel(f"{subtitle.upper()}\n\nСВОБОДНО")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter); empty.setStyleSheet("color:#675956;font-family:Georgia;font-size:9px;letter-spacing:2px;border-bottom:1px solid #49302e;padding:20px")
            actor_row.addWidget(empty, 1)
        root.addLayout(actor_row, 1)


class BattlePage(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__(); root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        header_widget = QWidget(); header = QHBoxLayout(header_widget); header.setContentsMargins(16, 10, 16, 10)
        block = QVBoxLayout(); eyebrow = QLabel("ТЕАТР БОЯ"); eyebrow.setObjectName("eyebrow"); block.addWidget(eyebrow)
        title = QLabel("Боевая сцена"); title.setObjectName("title"); block.addWidget(title)
        active = window.engine.active_actor(); state_text = f"РАУНД {window.campaign.battle.round_number}  ·  ХОД: {active.name.upper()}" if active else "ПОДГОТОВКА  ·  ВЫСТАВЬТЕ УЧАСТНИКОВ"
        sub = QLabel(state_text); sub.setObjectName("muted"); block.addWidget(sub); header.addLayout(block, 1)
        initiative = QPushButton("БРОСИТЬ ИНИЦИАТИВУ"); initiative.setObjectName("primary"); initiative.setEnabled(window.is_gm()); initiative.clicked.connect(window.roll_initiative); header.addWidget(initiative)
        next_turn = QPushButton("СЛЕДУЮЩИЙ ХОД"); next_turn.setEnabled(window.is_gm() and window.campaign.battle.active); next_turn.clicked.connect(window.next_turn); header.addWidget(next_turn)
        if window.is_gm() and window.campaign.battle.active:
            finish = QPushButton("ЗАВЕРШИТЬ"); finish.clicked.connect(window.end_combat); header.addWidget(finish)
        root.addWidget(header_widget)
        if window.last_banner:
            banner = QLabel(window.last_banner); banner.setObjectName("banner"); banner.setWordWrap(True); root.addWidget(banner)
        battlefield = BattleStage(); battle_layout = QHBoxLayout(battlefield); battle_layout.setContentsMargins(8, 8, 8, 8); battle_layout.setSpacing(2)
        labels = (("T1", "Тыл", "герои · укрытие"), ("A1", "Авангард", "герои · контакт"), ("A2", "Авангард", "враги · контакт"), ("T2", "Тыл", "враги · поддержка"))
        for index, (zone, title_text, subtitle) in enumerate(labels):
            battle_layout.addWidget(ZoneFrame(window, zone, title_text, subtitle), 1)
            if index == 1:
                clash = QLabel("VS"); clash.setFixedWidth(26); clash.setAlignment(Qt.AlignmentFlag.AlignCenter); clash.setStyleSheet("font-family:Georgia;font-size:15px;font-weight:700;color:#b64b3d;background:#160e10;border-left:1px solid #6a302c;border-right:1px solid #6a302c"); battle_layout.addWidget(clash)
        root.addWidget(battlefield, 1)
        root.addWidget(self._action_console(window))

    def _action_console(self, window: "MainWindow") -> QWidget:
        console = QFrame(); console.setObjectName("stageConsole"); console.setFixedHeight(158)
        layout = QHBoxLayout(console); layout.setContentsMargins(14, 9, 14, 10); layout.setSpacing(10)
        actor = window.engine.active_actor() or window.campaign.character(window.selected_character_id)
        if not actor and window.campaign.characters: actor = window.campaign.characters[0]
        identity = QFrame(); identity.setObjectName("panel"); identity.setFixedWidth(210); identity_layout = QVBoxLayout(identity); identity_layout.setContentsMargins(10, 8, 10, 8)
        label = QLabel("АКТИВНЫЙ БОЕЦ"); label.setObjectName("eyebrow"); identity_layout.addWidget(label)
        if actor:
            name = QLabel(actor.name); name.setWordWrap(True); name.setStyleSheet("font-family:Georgia;font-size:17px;font-weight:700;color:#efe0d2"); identity_layout.addWidget(name)
            identity_layout.addWidget(QLabel(f"ОЗ {actor.hp}/{actor.max_hp}  ·  КД {actor.armor_class}  ·  {window.campaign.battle.positions.get(actor.id, 'резерв')}"))
            resources = " · ".join(f"{r.name} {r.current}/{r.maximum}" for r in actor.resources[:2]) or "Ресурсы не ограничены"
            res = QLabel(resources); res.setWordWrap(True); res.setObjectName("muted"); identity_layout.addWidget(res)
            tactics = QPushButton("ТАКТИКА И СОСТОЯНИЯ"); tactics.setEnabled(window.can_control(actor)); tactics.clicked.connect(lambda: window.actor_menu(actor, tactics)); identity_layout.addWidget(tactics)
        else:
            identity_layout.addWidget(QLabel("На сцене пока никого нет.")); identity_layout.addStretch()
        layout.addWidget(identity)
        actions_box = QVBoxLayout(); action_title = QHBoxLayout(); title = QLabel("ДЕЙСТВИЯ В ОДИН КЛИК"); title.setObjectName("section"); action_title.addWidget(title); action_title.addStretch()
        if actor: action_title.addWidget(QLabel("выберите цель на сцене →"))
        actions_box.addLayout(action_title)
        action_row = QHBoxLayout(); action_row.setSpacing(6)
        if actor and actor.actions:
            for index, action in enumerate(actor.actions[:5]):
                resource = next((x for x in actor.resources if x.id == action.resource_id), None)
                detail = f"{action.damage}" if action.kind != "utility" else "особое"
                if action.save_dc: detail = f"Сл {action.save_dc} · {action.damage}"
                if action.recharge: detail += f" · {action.recharge}"
                if resource: detail += f" · {resource.current}/{resource.maximum}"
                button = QPushButton(f"{'✦' if index == 0 else '◇'}  {action.name.upper()}\n{detail}"); button.setObjectName("abilityCard"); button.setMinimumWidth(120); button.setEnabled(window.can_control(actor)); button.clicked.connect(lambda _=False, aid=action.id, actor_id=actor.id: window.use_specific_action(actor_id, aid)); action_row.addWidget(button, 1)
        else:
            empty = QLabel("Действия не распознаны. Импортируйте полный статблок или добавьте действие в листе."); empty.setWordWrap(True); empty.setObjectName("muted"); action_row.addWidget(empty, 1)
        actions_box.addLayout(action_row, 1); layout.addLayout(actions_box, 1)
        dice = QFrame(); dice.setObjectName("panel"); dice.setFixedWidth(170); dice_layout = QVBoxLayout(dice); dice_layout.setContentsMargins(8, 8, 8, 8)
        dice_title = QLabel("БЫСТРЫЕ КУБЫ"); dice_title.setObjectName("eyebrow"); dice_layout.addWidget(dice_title)
        grid = QGridLayout(); grid.setSpacing(3)
        for index, die in enumerate((4, 6, 8, 10, 12, 20)):
            button = QPushButton(f"d{die}"); button.setFixedHeight(27); button.clicked.connect(lambda _=False, d=die: window.quick_roll(f"1d{d}")); grid.addWidget(button, index//3, index%3)
        dice_layout.addLayout(grid)
        latest = window.campaign.recent_rolls[0] if window.campaign.recent_rolls else "—"
        result = QLabel(f"ПОСЛЕДНИЙ  {latest}"); result.setAlignment(Qt.AlignmentFlag.AlignCenter); result.setStyleSheet("font-family:Georgia;font-size:12px;font-weight:700;color:#d6b27d"); dice_layout.addWidget(result)
        layout.addWidget(dice); return console


class CharactersPage(QWidget):
    def __init__(self, window: "MainWindow"):
        super().__init__()
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout(); title = QLabel("Персонажи" if window.is_gm() else "Мой персонаж"); title.setObjectName("title"); header.addWidget(title, 1)
        if window.is_gm():
            creature = QPushButton("＋ Импорт моба / босса"); creature.setObjectName("primary"); creature.clicked.connect(lambda: window.import_character("enemy")); header.addWidget(creature)
            bestiary_button = QPushButton("📕 Бестиарий"); bestiary_button.clicked.connect(window.import_from_bestiary); header.addWidget(bestiary_button)
            add = QPushButton("Импорт героя"); add.clicked.connect(lambda: window.import_character("hero")); header.addWidget(add)
            create = QPushButton("Новый вручную"); create.clicked.connect(window.create_character); header.addWidget(create)
        root.addLayout(header)
        splitter = QSplitter()
        listing = QListWidget(); listing.setMinimumWidth(230); listing.setMaximumWidth(330)
        characters = window.visible_characters()
        for actor in characters:
            listing.addItem(f"{'ГЕРОЙ' if actor.side == 'hero' else 'ВРАГ'}  ·  {actor.name}\nОЗ {actor.hp}/{actor.max_hp} · КД {actor.armor_class}")
        selected = window.selected_character_id
        index = next((i for i, x in enumerate(characters) if x.id == selected), 0)
        if characters:
            listing.setCurrentRow(index)
            window.selected_character_id = characters[index].id
        listing.currentRowChanged.connect(lambda row: window.select_sheet(characters[row].id) if 0 <= row < len(characters) else None)
        splitter.addWidget(listing)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        sheet = self._sheet(window, window.campaign.character(window.selected_character_id) if characters else None)
        scroll.setWidget(sheet); splitter.addWidget(scroll); splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

    def _sheet(self, window: "MainWindow", actor: Combatant | None) -> QWidget:
        container = QWidget(); container.setObjectName("root"); root = QVBoxLayout(container)
        if not actor:
            empty = QLabel("Мастер ещё не назначил вам персонажа."); empty.setAlignment(Qt.AlignmentFlag.AlignCenter); root.addWidget(empty); return container
        name = QLabel(actor.name); name.setObjectName("title"); root.addWidget(name)
        meta = QLabel(" · ".join(x for x in (actor.race, actor.class_name, f"{actor.level} уровень") if x) or "Нейтральный лист")
        meta.setObjectName("muted"); root.addWidget(meta)
        stats = QFrame(); stats.setObjectName("panel"); grid = QGridLayout(stats)
        values = (("КД", actor.armor_class), ("ОЗ", f"{actor.hp}/{actor.max_hp}"), ("СКОРОСТЬ", f"{actor.speed} фт"), ("ИНИЦИАТИВА", f"{actor.initiative_bonus:+d}"))
        for i, (label, value) in enumerate(values):
            box = QLabel(f"{label}\n{value}"); box.setAlignment(Qt.AlignmentFlag.AlignCenter); box.setStyleSheet("font-size:15px;font-weight:700;padding:10px"); grid.addWidget(box, 0, i)
        for i, key in enumerate(ABILITIES):
            score = actor.stats[key]; mod = (score - 10) // 2
            box = QLabel(f"{key.upper()}\n{score} ({mod:+d})"); box.setAlignment(Qt.AlignmentFlag.AlignCenter); box.setStyleSheet("padding:8px"); grid.addWidget(box, 1, i)
        root.addWidget(stats)
        creature_lines = []
        identity = " · ".join(x for x in (actor.creature_size, actor.creature_type, actor.alignment, (f"CR {actor.challenge_rating}" if actor.challenge_rating else "")) if x)
        if identity: creature_lines.append(identity)
        if actor.saves: creature_lines.append("Спасброски: " + ", ".join(f"{k.upper()} {v:+d}" for k, v in actor.saves.items()))
        if actor.skills: creature_lines.append("Навыки: " + ", ".join(f"{k} {v:+d}" for k, v in actor.skills.items()))
        for label, values in (("Сопротивления", actor.resistances), ("Иммунитеты", actor.immunities), ("Уязвимости", actor.vulnerabilities), ("Иммунитеты к состояниям", actor.condition_immunities)):
            if values: creature_lines.append(f"{label}: " + ", ".join(values))
        if actor.senses: creature_lines.append("Чувства: " + actor.senses)
        if actor.languages: creature_lines.append("Языки: " + actor.languages)
        if actor.traits: creature_lines.append("Особенности: " + " · ".join(actor.traits))
        if creature_lines:
            creature = QFrame(); creature.setObjectName("panel"); creature_layout = QVBoxLayout(creature)
            heading = QLabel("Лист существа"); heading.setObjectName("section"); creature_layout.addWidget(heading)
            text = QLabel("\n".join(creature_lines)); text.setWordWrap(True); text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); creature_layout.addWidget(text)
            root.addWidget(creature)
        actions = QFrame(); actions.setObjectName("panel"); actions_layout = QVBoxLayout(actions)
        section_row = QHBoxLayout(); section = QLabel("Действия и ресурсы"); section.setObjectName("section"); section_row.addWidget(section); section_row.addStretch()
        if window.can_edit_sheet(actor):
            add_resource = QPushButton("＋ ресурс"); add_resource.clicked.connect(lambda: window.edit_resource(actor.id)); section_row.addWidget(add_resource)
            add_action = QPushButton("＋ действие"); add_action.clicked.connect(lambda: window.edit_action(actor.id)); section_row.addWidget(add_action)
        actions_layout.addLayout(section_row)
        if actor.actions:
            for action in actor.actions:
                resource = next((x for x in actor.resources if x.id == action.resource_id), None)
                mode = f"{action.attack_bonus:+d} к атаке" if action.attack_bonus is not None else (f"Сл {action.save_dc} {action.save_ability.upper()}" if action.save_dc is not None else action.kind)
                detail = f"{action.name} · {mode} · {action.damage} · {action.range_ft} фт"
                if resource: detail += f" · {resource.current}/{resource.maximum}"
                row = QHBoxLayout(); label = QLabel(detail); label.setWordWrap(True); row.addWidget(label, 1)
                if window.can_edit_sheet(actor):
                    edit_action = QPushButton("Изм."); edit_action.clicked.connect(lambda _=False, aid=action.id: window.edit_action(actor.id, aid)); row.addWidget(edit_action)
                actions_layout.addLayout(row)
        else:
            actions_layout.addWidget(QLabel("Действия пока не распознаны. Исходный текст сохранён ниже."))
        for resource in actor.resources:
            row = QHBoxLayout(); label = QLabel(f"◇ {resource.name}: {resource.current}/{resource.maximum} · {'короткий' if resource.recovery == 'short' else 'долгий'} отдых"); row.addWidget(label, 1)
            if window.can_control(actor):
                minus = QPushButton("−"); minus.setFixedWidth(30); minus.clicked.connect(lambda _=False, rid=resource.id: window.change_resource(actor.id, rid, -1)); row.addWidget(minus)
                plus = QPushButton("+"); plus.setFixedWidth(30); plus.clicked.connect(lambda _=False, rid=resource.id: window.change_resource(actor.id, rid, 1)); row.addWidget(plus)
            if window.can_edit_sheet(actor):
                edit_resource = QPushButton("Изм."); edit_resource.clicked.connect(lambda _=False, rid=resource.id: window.edit_resource(actor.id, rid)); row.addWidget(edit_resource)
            actions_layout.addLayout(row)
        root.addWidget(actions)
        source = QTextEdit(); source.setReadOnly(True); source.setPlainText(actor.source_text or "Исходный текст не задан."); source.setMinimumHeight(130)
        root.addWidget(QLabel("Исходник без изменений")); root.addWidget(source)
        audit = QLabel("\n".join(actor.audit) if actor.audit else "Аудит отсутствует"); audit.setWordWrap(True); audit.setObjectName("muted"); root.addWidget(audit)
        buttons = QHBoxLayout()
        if window.can_edit_sheet(actor):
            edit = QPushButton("Редактировать лист"); edit.clicked.connect(lambda: window.edit_character(actor.id)); buttons.addWidget(edit)
        if window.can_control(actor):
            rest = QPushButton("Отдых"); rest.clicked.connect(lambda: window.take_rest(actor.id)); buttons.addWidget(rest)
        if window.is_gm():
            zone = window.campaign.battle.positions.get(actor.id, "reserve")
            place = QPushButton(f"Расположение: {zone if zone != 'reserve' else 'резерв'}")
            place.clicked.connect(lambda: window.choose_placement(actor.id)); buttons.addWidget(place)
            delete = QPushButton("Удалить"); delete.setObjectName("danger"); delete.clicked.connect(lambda: window.delete_character(actor.id)); buttons.addWidget(delete)
        buttons.addStretch(); root.addLayout(buttons); root.addStretch()
        return container


class MaterialsDialog(QDialog):
    def __init__(self, window: "MainWindow"):
        super().__init__(window); self.window = window
        self.setWindowTitle("Материалы кампании"); self.resize(700, 500)
        root = QVBoxLayout(self)
        hint = QLabel("PNG/JPG/WebP, GLB/GLTF, музыка, PDF и текст копируются в локальное хранилище без уменьшения. Материалы не загромождают боевую сцену.")
        hint.setWordWrap(True); hint.setObjectName("muted"); root.addWidget(hint)
        self.listing = QListWidget(); self.listing.itemDoubleClicked.connect(lambda _item: self._open()); root.addWidget(self.listing, 1)
        row = QHBoxLayout(); add = QPushButton("＋ Добавить файлы"); add.setObjectName("primary"); add.clicked.connect(self._add); row.addWidget(add)
        open_button = QPushButton("Открыть"); open_button.clicked.connect(self._open); row.addWidget(open_button)
        remove = QPushButton("Удалить"); remove.setObjectName("danger"); remove.clicked.connect(self._remove); row.addWidget(remove); row.addStretch(); root.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.listing.clear()
        for asset in self.window.campaign.assets:
            path = Path(asset.get("path", "")); size = f"{path.stat().st_size / 1024 / 1024:.1f} МБ" if path.is_file() else "файл недоступен"
            self.listing.addItem(f"{asset.get('name') or path.name}\n{asset.get('kind', 'файл')} · {size}")

    def _add(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "Добавить материалы", "", "Материалы (*.png *.jpg *.jpeg *.webp *.glb *.gltf *.mp3 *.ogg *.wav *.flac *.pdf *.txt *.md);;Все файлы (*)")
        if not files: return
        target_dir = DEFAULT_SAVE.parent / "assets"; target_dir.mkdir(parents=True, exist_ok=True)
        for filename in files:
            source = Path(filename)
            suffix = source.suffix.lower(); token = os.urandom(6).hex(); destination = target_dir / f"{token}-{source.name}"
            try:
                shutil.copy2(source, destination)
                kind = "изображение" if suffix in {".png", ".jpg", ".jpeg", ".webp"} else "3D-модель" if suffix in {".glb", ".gltf"} else "музыка" if suffix in {".mp3", ".ogg", ".wav", ".flac"} else "документ"
                self.window.campaign.assets.append({"id": token, "name": source.name, "kind": kind, "path": str(destination)})
            except OSError as exc:
                self.window.error(f"Не удалось добавить {source.name}: {exc}")
        self.window.commit("Материалы добавлены"); self._refresh()

    def _selected(self) -> dict[str, str] | None:
        row = self.listing.currentRow()
        return self.window.campaign.assets[row] if 0 <= row < len(self.window.campaign.assets) else None

    def _open(self) -> None:
        asset = self._selected()
        if not asset: return
        path = Path(asset.get("path", ""))
        if not path.is_file(): return self.window.error("Файл больше недоступен")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _remove(self) -> None:
        asset = self._selected()
        if not asset or QMessageBox.question(self, "Удалить материал", f"Удалить «{asset.get('name')}» из локального хранилища?") != QMessageBox.StandardButton.Yes: return
        path = Path(asset.get("path", "")); managed = DEFAULT_SAVE.parent / "assets"
        try:
            if path.is_file() and managed in path.parents: path.unlink()
        except OSError as exc:
            return self.window.error(str(exc))
        self.window.campaign.assets = [item for item in self.window.campaign.assets if item.get("id") != asset.get("id")]
        self.window.commit("Материал удалён"); self._refresh()


class NetworkDialog(QDialog):
    def __init__(self, window: "MainWindow"):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Общий сетевой стол")
        self.resize(600, 520)
        root = QVBoxLayout(self); form = QFormLayout()
        self.address = QLineEdit(window.network.base_url if window.network else "http://127.0.0.1:4173")
        self.room = QLineEdit(window.network.room_code if window.network else "DRAGON")
        self.name = QLineEdit(window.network.name if window.network else "Мастер")
        self.role = QComboBox(); self.role.addItem("Мастер", "gm"); self.role.addItem("Игрок", "player"); self.role.setCurrentIndex(0 if window.is_gm() else 1)
        self.hero = QComboBox(); self.hero.addItem("Не назначен", "")
        for actor in window.campaign.characters:
            if actor.side == "hero": self.hero.addItem(actor.name, actor.id)
        form.addRow("Адрес сервера", self.address); form.addRow("Код комнаты", self.room); form.addRow("Имя", self.name); form.addRow("Роль", self.role); form.addRow("Герой игрока", self.hero)
        root.addLayout(form)
        row = QHBoxLayout(); host = QPushButton("Запустить сервер здесь"); host.clicked.connect(self._host); connect = QPushButton("Подключиться"); connect.setObjectName("primary"); connect.clicked.connect(self._connect); row.addWidget(host); row.addWidget(connect); root.addLayout(row)
        self.status = QLabel("LAN/Hamachi: передайте участникам IP компьютера мастера и код. Для интернета разместите сервер за HTTPS reverse proxy."); self.status.setWordWrap(True); root.addWidget(self.status)
        members = QLabel("Участники и назначения"); members.setObjectName("section"); root.addWidget(members)
        self.member_list = QListWidget(); root.addWidget(self.member_list, 1)
        if window.network:
            for item in window.network.members: self.member_list.addItem(f"{item.get('name')} · {item.get('role')} · {item.get('character_id') or 'без героя'}")
        self.assign_member = QComboBox(); self.assign_hero = QComboBox(); self.assign_hero.addItem("Снять назначение", "")
        if window.network and window.is_gm():
            for item in window.network.members:
                if item.get("role") == "player": self.assign_member.addItem(item.get("name") or "Игрок", item.get("client_id"))
            for actor in window.campaign.characters:
                if actor.side == "hero": self.assign_hero.addItem(actor.name, actor.id)
            assignment = QHBoxLayout(); assignment.addWidget(self.assign_member, 1); assignment.addWidget(self.assign_hero, 1)
            assign = QPushButton("Назначить героя"); assign.clicked.connect(self._assign); assignment.addWidget(assign); root.addLayout(assignment)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def _assign(self) -> None:
        if not self.window.network or not self.assign_member.currentData(): return
        try:
            self.window.network.assign(self.assign_member.currentData(), self.assign_hero.currentData())
            self.window.poll_network(); self.accept()
        except NetworkError as exc:
            self.status.setText(str(exc))

    def _host(self) -> None:
        try:
            self.window.start_server()
            self.status.setText("Сервер запущен на 0.0.0.0:4173. Теперь подключитесь как мастер.")
        except OSError as exc:
            self.status.setText(f"Не удалось запустить сервер: {exc}")

    def _connect(self) -> None:
        try:
            self.window.connect_network(self.address.text().strip(), self.room.text().strip(), self.name.text().strip(), self.role.currentData(), self.hero.currentData())
            self.accept()
        except (NetworkError, ValueError) as exc:
            self.status.setText(str(exc))


class MainWindow(QMainWindow):
    def __init__(self, campaign: Campaign | None = None):
        super().__init__()
        self.campaign = campaign or load_campaign()
        self.engine = BattleEngine(self.campaign)
        self.selected_character_id = self.campaign.assigned_character_id or (self.campaign.characters[0].id if self.campaign.characters else "")
        self.last_banner = ""
        self.current_page = 0
        self.network: NetworkClient | None = None
        self.embedded_server = None
        self.network_syncing = False
        self.setWindowTitle("Драконья Сага · Боевой стол")
        self.resize(1540, 920)
        self.setMinimumSize(1120, 700)
        self.setStyleSheet(APP_STYLE)
        self._build_shell()
        self.poll_timer = QTimer(self); self.poll_timer.setInterval(2200); self.poll_timer.timeout.connect(self.poll_network)
        self.refresh()

    def _build_shell(self) -> None:
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        outer = QHBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(0)
        sidebar = QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(220); side = QVBoxLayout(sidebar); side.setContentsMargins(10, 0, 10, 12); side.setSpacing(4)
        brand = QLabel("GRIMDICE"); brand.setObjectName("brand"); side.addWidget(brand)
        subtitle = QLabel("DRAGON SAGA"); subtitle.setObjectName("brandAccent"); side.addWidget(subtitle)
        banner = assets.banner_path()
        if banner is not None:
            banner_label = QLabel(); banner_label.setToolTip("Сага 5.0 «Гримуар» — оригинальная гербовая заглушка")
            banner_pixmap = load_pixmap(str(banner), 190, 190)
            if banner_pixmap and not banner_pixmap.isNull():
                banner_label.setPixmap(banner_pixmap); banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                side.addWidget(banner_label)
        section = QLabel("БОЕВОЙ СТОЛ"); section.setObjectName("eyebrow"); section.setStyleSheet("padding:18px 10px 5px"); side.addWidget(section)
        self.battle_nav = QPushButton("⚔   Боевая сцена"); self.battle_nav.setObjectName("nav"); self.battle_nav.setCheckable(True); self.battle_nav.clicked.connect(lambda: self.set_page(0)); side.addWidget(self.battle_nav)
        self.characters_nav = QPushButton("♙   Листы участников"); self.characters_nav.setObjectName("nav"); self.characters_nav.setCheckable(True); self.characters_nav.clicked.connect(lambda: self.set_page(1)); side.addWidget(self.characters_nav)
        self.strategic_nav = QPushButton("🗺   Стратегический узел"); self.strategic_nav.setObjectName("nav"); self.strategic_nav.setCheckable(True); self.strategic_nav.clicked.connect(lambda: self.set_page(2)); side.addWidget(self.strategic_nav)
        self.dd_nav = QPushButton("🩸   Бой в стиле Darkest Dungeon"); self.dd_nav.setObjectName("nav"); self.dd_nav.setCheckable(True); self.dd_nav.clicked.connect(lambda: self.set_page(3)); side.addWidget(self.dd_nav)
        self.lss_nav = QPushButton("📥   Импорт из LSS"); self.lss_nav.setObjectName("nav"); self.lss_nav.setCheckable(True); self.lss_nav.clicked.connect(lambda: self.set_page(4)); side.addWidget(self.lss_nav)
        self.lss_charm_nav = QPushButton("📖   Чарники LSS"); self.lss_charm_nav.setObjectName("nav"); self.lss_charm_nav.setCheckable(True); self.lss_charm_nav.clicked.connect(lambda: self.set_page(5)); side.addWidget(self.lss_charm_nav)
        self.calculators_nav = QPushButton("🧮   Калькуляторы"); self.calculators_nav.setObjectName("nav"); self.calculators_nav.setCheckable(True); self.calculators_nav.clicked.connect(lambda: self.set_page(6)); side.addWidget(self.calculators_nav)
        self.journal_nav = QPushButton("📜   Хроника боя"); self.journal_nav.setObjectName("nav"); self.journal_nav.setCheckable(True); self.journal_nav.clicked.connect(lambda: self.set_page(7)); side.addWidget(self.journal_nav)
        if self.is_gm():
            import_creature = QPushButton("＋   ИМПОРТ МОБА / БОССА"); import_creature.setObjectName("primary"); import_creature.clicked.connect(lambda: self.import_character("enemy")); side.addWidget(import_creature)
            bestiary_button = QPushButton("📕   БЕСТИАРИЙ"); bestiary_button.clicked.connect(self.import_from_bestiary); side.addWidget(bestiary_button)
        side.addStretch()
        line = QFrame(); line.setFixedHeight(1); line.setStyleSheet("background:#342b2b"); side.addWidget(line)
        self.materials_button = QPushButton("Материалы и модели"); self.materials_button.setEnabled(self.is_gm()); self.materials_button.clicked.connect(lambda: MaterialsDialog(self).exec()); side.addWidget(self.materials_button)
        network = QPushButton("Общий сетевой стол"); network.clicked.connect(lambda: NetworkDialog(self).exec()); side.addWidget(network)
        save = QPushButton("Сохранить стол"); save.clicked.connect(self.save_as); side.addWidget(save)
        help_button = QPushButton("Правила сцены"); help_button.clicked.connect(self.show_rules); side.addWidget(help_button)
        self.role_label = QLabel(); self.role_label.setWordWrap(True); self.role_label.setStyleSheet("color:#847874;padding:10px;font-size:10px;letter-spacing:1px"); side.addWidget(self.role_label)
        outer.addWidget(sidebar)

        center = QWidget(); center_layout = QVBoxLayout(center); center_layout.setContentsMargins(0, 0, 0, 0); center_layout.setSpacing(0)
        topbar = QFrame(); topbar.setObjectName("topbar"); topbar.setFixedHeight(66); top = QHBoxLayout(topbar); top.setContentsMargins(18, 8, 16, 8)
        campaign = QVBoxLayout(); eyebrow = QLabel("КАМПАНИЯ"); eyebrow.setObjectName("eyebrow"); campaign.addWidget(eyebrow)
        campaign_name = QLabel("Драконья Сага"); campaign_name.setStyleSheet("font-family:Georgia;font-size:18px;font-weight:700;color:#e9ddd2"); campaign.addWidget(campaign_name); top.addLayout(campaign)
        top.addStretch()
        self.edition = QComboBox(); self.edition.addItems(["2014", "2024"]); self.edition.setCurrentText(self.campaign.edition); self.edition.currentTextChanged.connect(self.change_edition); top.addWidget(QLabel("D&D 5e")); top.addWidget(self.edition)
        self.open_button = QPushButton("ОТКРЫТЬ"); self.open_button.setEnabled(self.is_gm()); self.open_button.clicked.connect(self.open_file); top.addWidget(self.open_button)
        self.reset_button = QPushButton("СТАРТОВАЯ СЦЕНА"); self.reset_button.setEnabled(self.is_gm()); self.reset_button.clicked.connect(self.reset_campaign); top.addWidget(self.reset_button)
        if self.is_gm():
            import_button = QPushButton("＋  НОВЫЙ ПРОТИВНИК"); import_button.setObjectName("primary"); import_button.clicked.connect(lambda: self.import_character("enemy")); top.addWidget(import_button)
        center_layout.addWidget(topbar)
        self.stack = QStackedWidget(); center_layout.addWidget(self.stack, 1); outer.addWidget(center, 1)
        self.dice = None

    def refresh(self) -> None:
        self.engine = BattleEngine(self.campaign)
        while self.stack.count():
            widget = self.stack.widget(0); self.stack.removeWidget(widget); widget.deleteLater()
        self.stack.addWidget(BattlePage(self)); self.stack.addWidget(CharactersPage(self))
        self.stack.addWidget(StrategicStage(self)); self.stack.addWidget(DDBattleStage(self))
        self.stack.addWidget(LSSImportPage(self)); self.stack.addWidget(self._lss_charm_page(self))
        self.stack.addWidget(self._calculators_page(self))
        self.stack.addWidget(self._journal_page(self))
        self.stack.setCurrentIndex(self.current_page)
        self._sync_nav_checks()
        self.characters_nav.setText("♙   Персонажи" if self.is_gm() else "♙   Мой персонаж")
        self.role_label.setText(("МАСТЕР" if self.is_gm() else "ИГРОК") + (f"\nКомната {self.network.room_code}" if self.network else "\nЛокальный режим"))
        self.edition.blockSignals(True); self.edition.setCurrentText(self.campaign.edition); self.edition.blockSignals(False)
        self.edition.setEnabled(self.is_gm()); self.open_button.setEnabled(self.is_gm()); self.reset_button.setEnabled(self.is_gm()); self.materials_button.setEnabled(self.is_gm())
        if self.dice is not None: self.dice.refresh()

    def set_page(self, index: int) -> None:
        self.current_page = index; self.refresh()

    def _sync_nav_checks(self) -> None:
        self.battle_nav.setChecked(self.current_page == 0)
        self.characters_nav.setChecked(self.current_page == 1)
        self.strategic_nav.setChecked(self.current_page == 2)
        self.dd_nav.setChecked(self.current_page == 3)
        self.lss_nav.setChecked(self.current_page == 4)
        self.lss_charm_nav.setChecked(self.current_page == 5)
        self.calculators_nav.setChecked(self.current_page == 6)
        self.journal_nav.setChecked(self.current_page == 7)

    def is_gm(self) -> bool:
        return self.campaign.role == "gm"

    def can_control(self, actor: Combatant) -> bool:
        return self.is_gm() or (actor.id == self.campaign.assigned_character_id and actor.side == "hero")

    def can_edit_sheet(self, actor: Combatant) -> bool:
        return self.is_gm()

    def visible_characters(self) -> list[Combatant]:
        if self.is_gm():
            return self.campaign.characters
        own = self.campaign.character(self.campaign.assigned_character_id)
        return [own] if own else []

    def commit(self, banner: str = "") -> None:
        self.last_banner = banner
        if not self.network or self.is_gm():
            save_campaign(self.campaign)
        if self.network and not self.network_syncing:
            try:
                result = self.network.push(self.campaign.to_dict())
                if result.get("state"):
                    self.campaign = Campaign.from_dict(result["state"])
            except NetworkError as exc:
                if getattr(exc, "status", 0) == 409:
                    self.poll_network()
                else:
                    self.last_banner = f"Сетевое сохранение: {exc}"
        self.refresh()

    def error(self, text: str) -> None:
        QMessageBox.warning(self, "Драконья Сага", text)

    def select_actor(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        active = self.engine.active_actor()
        if actor and active and actor.id != active.id and self.can_control(active):
            self.campaign.battle.target_id = actor_id
            self.commit(f"Цель: {actor.name}")
            return
        self.selected_character_id = actor_id
        self.refresh()

    def change_hp(self, actor_id: str, delta: int) -> None:
        actor = self.campaign.character(actor_id)
        if actor and self.can_control(actor):
            before = actor.hp
            actor.hp = max(0, min(actor.max_hp, actor.hp + delta))
            if before == 0 and actor.hp > 0:
                actor.conditions = [c for c in actor.conditions if c not in {"Без сознания", "Стабилизирован"}]
                self.engine.stabilize_reset(actor.id)
            self.commit(f"{actor.name}: ОЗ {actor.hp}/{actor.max_hp}")

    def quick_roll(self, formula: str) -> None:
        try:
            value = self.engine.roll(formula)
            self.campaign.recent_rolls.insert(0, f"{formula} = {value.total}")
            self.campaign.recent_rolls = self.campaign.recent_rolls[:30]
            self.commit(f"БРОСОК · {formula} = {value.total}")
        except RuleError as exc:
            self.error(str(exc))

    def use_primary_action(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not actor.actions: return self.error("У персонажа нет распознанных действий")
        action = actor.actions[0]
        if len(actor.actions) > 1:
            labels = [f"{item.name} · {item.damage}" for item in actor.actions]
            selected, ok = QInputDialog.getItem(self, "Выберите действие", actor.name, labels, 0, False)
            if not ok: return
            action = actor.actions[labels.index(selected)]
        self.use_specific_action(actor_id, action.id)

    def use_specific_action(self, actor_id: str, action_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_control(actor): return
        action = next((item for item in actor.actions if item.id == action_id), None)
        if not action: return self.error("Действие больше не доступно")
        target = self.campaign.character(self.campaign.battle.target_id)
        if action.kind == "heal":
            if not target or target.side != actor.side: target = actor
        elif action.kind == "utility":
            target = actor
        elif not target or target.side == actor.side:
            target = next((x for x in self.campaign.characters if x.side != actor.side and self.campaign.battle.positions.get(x.id) in ZONES and x.alive), None)
        if not target: return self.error("Выберите подходящую цель на сцене")
        try:
            if self.network and not self.is_gm():
                response = self.network.resolve_action(actor.id, target.id, action.id)
                outcome = response.get("result", {})
                if response.get("state"): self.campaign = Campaign.from_dict(response["state"])
                hit = outcome.get("hit")
                prefix = "ПОПАДАНИЕ · " if hit is True else "ПРОМАХ · " if hit is False else "РЕЗУЛЬТАТ · "
                self.last_banner = prefix + outcome.get("detail", action.name); self.refresh(); return
            result = self.engine.resolve_action(actor.id, target.id, action.id)
            prefix = "ПОПАДАНИЕ · " if result.hit is True else "ПРОМАХ · " if result.hit is False else "РЕЗУЛЬТАТ · "
            self.commit(prefix + result.detail)
        except (RuleError, NetworkError) as exc:
            if isinstance(exc, NetworkError) and getattr(exc, "status", 0) == 409: self.poll_network()
            self.error(str(exc))

    def network_tactic(self, actor_id: str, operation: str, **parameters) -> bool:
        if not self.network or self.is_gm(): return False
        try:
            response = self.network.tactic(actor_id, operation, **parameters)
            if response.get("state"): self.campaign = Campaign.from_dict(response["state"])
            self.last_banner = response.get("result", {}).get("detail", "Приём выполнен")
            self.refresh(); return True
        except NetworkError as exc:
            if getattr(exc, "status", 0) == 409: self.poll_network()
            self.error(str(exc)); return True

    def actor_menu(self, actor: Combatant, anchor: QWidget) -> None:
        menu = QMenu(self)
        left = menu.addAction("Шаг влево"); right = menu.addAction("Шаг вправо")
        disengage = menu.addAction("Отход и шаг")
        charge = menu.addAction("Натиск"); flank = menu.addAction("Фланг"); breather = menu.addAction("Тактическая передышка")
        target = self.campaign.character(self.campaign.battle.target_id)
        analyze = menu.addAction("Анализ подготовки босса") if target and target.side != actor.side and target.is_boss and target.telegraph else None
        dying = None
        if actor.hp == 0 and "Мёртв" not in actor.conditions and "Стабилизирован" not in actor.conditions:
            successes, failures = self.engine.death_status(actor.id)
            dying = menu.addAction(f"🩸 Спасбросок от смерти · ✓{successes} ✗{failures} · d20")
        menu.addSeparator(); conditions = menu.addAction("Изменить состояния"); edit = menu.addAction("Редактировать лист"); edit.setEnabled(self.can_edit_sheet(actor))
        if actor.is_boss: telegraph = menu.addAction("Подготовка босса")
        else: telegraph = None
        picked = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
        if not picked: return
        try:
            current = self.campaign.battle.positions.get(actor.id, "reserve")
            if picked in (left, right, disengage, charge):
                if current not in ZONES: raise RuleError("Сначала выставьте участника из резерва через лист")
                if picked == disengage:
                    direction = -1 if actor.side == "hero" else 1
                    mode = "disengage"
                else:
                    direction = -1 if picked == left else 1
                    mode = "charge" if picked == charge else "normal"
                index = ZONES.index(current) + direction
                if not 0 <= index < len(ZONES): raise RuleError("Край поля")
                if self.network_tactic(actor.id, "move", destination=ZONES[index], mode=mode): return
                self.engine.move(actor.id, ZONES[index], mode); self.commit("Перемещение выполнено")
            elif picked == flank:
                destination = "T2" if actor.side == "hero" else "T1"
                if self.network_tactic(actor.id, "move", destination=destination, mode="flank"): return
                self.engine.move(actor.id, destination, "flank"); self.commit("Фланг выполнен")
            elif picked == breather:
                if self.network_tactic(actor.id, "breather"): return
                healed = self.engine.tactical_breather(actor.id); self.commit(f"Передышка: +{healed} ОЗ")
            elif analyze and picked == analyze and target:
                if self.network_tactic(actor.id, "investigate", target_id=target.id, ability="wis"): return
                result = self.engine.investigate_telegraph(actor.id, target.id, "wis"); self.commit(result.detail)
            elif dying and picked == dying:
                if self.network_tactic(actor.id, "death_save"): return
                result = self.engine.death_save(actor.id); self.commit(result.detail)
            elif picked == conditions:
                dialog = ConditionsDialog(actor, self)
                if dialog.exec() == QDialog.DialogCode.Accepted:
                    actor.conditions = dialog.selected(); self.commit("Состояния обновлены")
            elif picked == edit: self.edit_character(actor.id)
            elif telegraph and picked == telegraph:
                text, ok = self._text_prompt("Подготовка босса", "Действие | Сл | контрмера", f"{actor.telegraph or 'Сокрушающий удар'} | {actor.telegraph_dc} | {actor.telegraph_counter or 'Отойти в тыл'}")
                if ok:
                    parts = [x.strip() for x in text.split("|")]; self.engine.telegraph(actor.id, parts[0], int(parts[1]) if len(parts)>1 and parts[1].isdigit() else 14, parts[2] if len(parts)>2 else ""); self.commit("Подготовка босса объявлена")
        except RuleError as exc: self.error(str(exc))

    def _text_prompt(self, title: str, label: str, value: str) -> tuple[str, bool]:
        dialog = QDialog(self); dialog.setWindowTitle(title); layout = QVBoxLayout(dialog); layout.addWidget(QLabel(label)); field = QLineEdit(value); layout.addWidget(field); buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons); ok = dialog.exec() == QDialog.DialogCode.Accepted; return field.text(), ok

    def roll_initiative(self) -> None:
        try: self.engine.roll_initiative(); self.commit("Инициатива определена")
        except RuleError as exc: self.error(str(exc))

    def next_turn(self) -> None:
        try: self.engine.next_turn(); self.commit("Следующий ход")
        except RuleError as exc: self.error(str(exc))

    def end_combat(self) -> None:
        if not self.is_gm(): return
        if QMessageBox.question(self, "Завершить бой", "Сбросить инициативу и перейти к отдыху?") == QMessageBox.StandardButton.Yes:
            self.engine.end_combat(); self.commit("Бой завершён")

    def import_character(self, side: str) -> None:
        dialog = ImportDialog(side, self)
        if dialog.exec() != QDialog.DialogCode.Accepted: return
        try:
            parsed = dialog._last_result or parse_stat_block(dialog.text.toPlainText(), dialog.side.currentData()); actor = parsed.combatant
            actor.side = dialog.side.currentData(); actor.is_boss = actor.is_boss or dialog.boss_selected
            actor.rank = ("hero", "mob", "elite", "boss")[min(3, dialog.side.currentIndex())]
            actor.audit.append(f"Роль выбрана перед импортом: {dialog.side.currentText()} (ранг {actor.rank}).")
            self.campaign.characters.append(actor)
            preferred = ("T1", "A1") if actor.side == "hero" else ("A2", "T2")
            zone = next((z for z in preferred if len(self.campaign.positioned(z)) < 2), "reserve")
            self.campaign.battle.positions[actor.id] = zone
            self.selected_character_id = actor.id; self.commit(f"{actor.name} добавлен · {zone if zone != 'reserve' else 'резерв'}")
        except ValueError as exc: self.error(str(exc))

    def create_character(self) -> None:
        actor = Combatant(name="Новый герой", rank="hero")
        dialog = CharacterDialog(actor, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            actor = dialog.apply(); self.campaign.characters.append(actor); self.campaign.battle.positions[actor.id] = "reserve"; self.selected_character_id = actor.id; self.commit("Персонаж создан")

    def import_from_bestiary(self) -> None:
        """Вывести на сцену существо из встроенного бестиария (с нумерацией групп)."""
        if not self.is_gm(): return
        dialog = BestiaryDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.chosen_id: return
        try:
            meta = bestiary.entry(dialog.chosen_id)
            added: list[str] = []
            for index in range(1, dialog.count.value() + 1):
                actor = bestiary.create(dialog.chosen_id, number=index)
                self.campaign.characters.append(actor)
                preferred = ("A2", "T2")
                zone = next((z for z in preferred if len(self.campaign.positioned(z)) < 2), "reserve")
                self.campaign.battle.positions[actor.id] = zone
                added.append(f"{actor.name} → {zone if zone != 'reserve' else 'резерв'}")
            last = self.campaign.characters[-1]
            self.selected_character_id = last.id
            self.commit(f"Бестиарий: {', '.join(added)}")
        except (KeyError, ValueError) as exc:
            self.error(str(exc))

    def edit_character(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_edit_sheet(actor): return
        dialog = CharacterDialog(actor, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: dialog.apply(); self.commit("Лист обновлён")

    def edit_action(self, actor_id: str, action_id: str = "") -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_edit_sheet(actor): return
        action = next((item for item in actor.actions if item.id == action_id), None)
        dialog = ActionDialog(actor, action, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            edited = dialog.apply()
            if action is None: actor.actions.append(edited)
            self.commit(f"Действие «{edited.name}» сохранено")

    def edit_resource(self, actor_id: str, resource_id: str = "") -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_edit_sheet(actor): return
        resource = next((item for item in actor.resources if item.id == resource_id), None)
        dialog = ResourceDialog(resource, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            edited = dialog.apply()
            if resource is None: actor.resources.append(edited)
            self.commit(f"Ресурс «{edited.name}» сохранён")

    def change_resource(self, actor_id: str, resource_id: str, delta: int) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_control(actor): return
        resource = next((item for item in actor.resources if item.id == resource_id), None)
        if resource:
            resource.current = max(0, min(resource.maximum, resource.current + delta))
            self.commit(f"{resource.name}: {resource.current}/{resource.maximum}")

    def take_rest(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.can_control(actor): return
        options = ["Короткий отдых", "Короткий отдых + 1 Кость Хитов", "Долгий отдых"]
        selected, ok = QInputDialog.getItem(self, "Отдых", actor.name, options, 0, False)
        if not ok: return
        try:
            kind = "long" if selected == options[2] else "short"
            spent = 1 if selected == options[1] else 0
            if self.network_tactic(actor.id, "rest", kind=kind, spend_hit_dice=spent): return
            healed = self.engine.rest(actor.id, kind, spent)
            self.commit(f"{selected}: +{healed} ОЗ")
        except RuleError as exc: self.error(str(exc))

    def choose_placement(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.is_gm(): return
        current = self.campaign.battle.positions.get(actor.id, "reserve")
        values = ["reserve", *ZONES]
        labels = ["Резерв", "Т1 · тыл героев", "А1 · авангард героев", "А2 · авангард врагов", "Т2 · тыл врагов"]
        selected, ok = QInputDialog.getItem(self, "Расположение", actor.name, labels, values.index(current) if current in values else 0, False)
        if not ok: return
        try:
            destination = values[labels.index(selected)]
            self.engine.place(actor.id, destination)
            self.commit(f"{actor.name}: {destination if destination != 'reserve' else 'в резерве'}")
        except RuleError as exc: self.error(str(exc))

    def toggle_reserve(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or not self.is_gm():
            return
        current = self.campaign.battle.positions.get(actor.id, "reserve")
        if current != "reserve":
            self.campaign.battle.positions[actor.id] = "reserve"
            self.commit(f"{actor.name}: в резерве")
            return
        preferred = ("T1", "A1") if actor.side == "hero" else ("A2", "T2")
        zone = next((item for item in preferred if len(self.campaign.positioned(item)) < 2), "")
        if not zone:
            return self.error("На стороне участника нет свободного места: максимум два в ряду")
        self.campaign.battle.positions[actor.id] = zone
        self.commit(f"{actor.name}: выставлен в {zone}")

    def delete_character(self, actor_id: str) -> None:
        actor = self.campaign.character(actor_id)
        if not actor or QMessageBox.question(self, "Удаление", f"Удалить {actor.name}?") != QMessageBox.StandardButton.Yes: return
        self.campaign.characters = [x for x in self.campaign.characters if x.id != actor_id]; self.campaign.battle.positions.pop(actor_id, None); self.campaign.battle.initiative = [x for x in self.campaign.battle.initiative if x.get("id") != actor_id]; self.selected_character_id = self.campaign.characters[0].id if self.campaign.characters else ""; self.commit("Персонаж удалён")

    def select_sheet(self, actor_id: str) -> None:
        if actor_id == self.selected_character_id: return
        self.selected_character_id = actor_id; self.refresh()

    def change_edition(self, edition: str) -> None:
        self.campaign.edition = edition; self.commit(f"Правила D&D 5e {edition}")

    def save_as(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Сохранить кампанию", "dragon-saga-campaign.json", "JSON (*.json)")
        if filename:
            save_campaign(self.campaign, filename); self.last_banner = f"Сохранено: {filename}"; self.refresh()

    def open_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Открыть кампанию", "", "JSON (*.json)")
        if not filename: return
        try:
            with open(filename, "r", encoding="utf-8") as handle: self.campaign = Campaign.from_dict(json.load(handle))
            self.selected_character_id = self.campaign.characters[0].id if self.campaign.characters else ""; self.commit("Кампания открыта")
        except (OSError, ValueError, json.JSONDecodeError) as exc: self.error(str(exc))

    def reset_campaign(self) -> None:
        if QMessageBox.question(self, "Стартовая сцена", "Заменить текущий локальный стол стартовой сценой с пятью заполнителями?") == QMessageBox.StandardButton.Yes:
            self.campaign = starter_campaign(); self.selected_character_id = self.campaign.characters[0].id; self.commit("Стартовая сцена восстановлена")

    def show_rules(self) -> None:
        text = """<h2>Домашняя боевая линия «Драконьей Саги»</h2>
<p><b>Т1 → А1 → А2 → Т2</b>: четыре ряда по 10 футов, не более двух участников в каждом.</p>
<ul><li><b>Движение:</b> соседний ряд стоит 10 футов.</li><li><b>Провоцированная атака:</b> выход из авангарда без Отхода тратит реакцию соседнего врага.</li><li><b>Фланг:</b> из своего тыла во вражеский тыл при скорости 40+; тратится всё движение.</li><li><b>Натиск:</b> тыл → свой авангард; первая ближняя атака с преимуществом, но следующая атака по вам тоже.</li><li><b>Тактическая передышка:</b> бонусное действие и Кость Хитов в безопасном своём тылу.</li><li><b>Укрытие тыла:</b> при союзнике в авангарде +2 КД и помеха прямой дальней атаке.</li><li><b>Босс:</b> открыто объявляет подготовку; Восприятие/Анализ против Сл раскрывает контрмеру.</li></ul>
<p>Броски попадания, критический урон, спасброски и расходы 2/2 выполняются одной кнопкой. Редакция 2014/2024 выбирается сверху; спорные трактовки остаются за мастером.</p>"""
        QMessageBox.information(self, "Наши правила", text)

    def start_server(self) -> None:
        if self.embedded_server: return
        self.embedded_server = create_server("0.0.0.0", 4173, quiet=True)
        threading.Thread(target=self.embedded_server.serve_forever, name="dragon-saga-server", daemon=True).start()

    def connect_network(self, address: str, room: str, name: str, role: str, character_id: str) -> None:
        same_room = self.network and self.network.base_url == address.rstrip("/") and self.network.room_code.upper() == room.upper()
        client = NetworkClient(
            address, room, name or "Участник", role, character_id,
            owner_key=self.network.owner_key if same_room and self.network else "",
            client_id=self.network.client_id if same_room and self.network else os.urandom(8).hex(),
        )
        result = client.connect(); self.network = client
        if result.get("state"):
            self.campaign = Campaign.from_dict(result["state"])
        else:
            if client.role != "gm": raise NetworkError("Комната ещё не создана мастером")
            self.campaign.role = "gm"; client.push(self.campaign.to_dict())
        self.campaign.role = client.role; self.campaign.assigned_character_id = client.character_id
        self.poll_timer.start(); self.last_banner = f"Подключено: {room} · {client.role}"; self.refresh()

    def poll_network(self) -> None:
        if not self.network or self.network_syncing: return
        self.network_syncing = True
        try:
            result = self.network.pull()
            if result.get("state"):
                current_page = self.current_page; self.campaign = Campaign.from_dict(result["state"]); self.current_page = current_page; self.refresh()
        except NetworkError as exc:
            self.last_banner = f"Сеть: {exc}"
        finally: self.network_syncing = False

    def _lss_charm_page(self, window: "MainWindow") -> QWidget:
        """Страница чарников LSS: список импортированных чарников и быстрый просмотр."""
        container = QWidget(); container.setObjectName("root")
        root = QVBoxLayout(container); root.setContentsMargins(0, 0, 0, 0)

        header = QHBoxLayout()
        title = QLabel("ЧАРНИКИ LSS"); title.setObjectName("title"); header.addWidget(title, 1)
        header.addStretch()
        root.addLayout(header)

        desc = QLabel(
            "Чарники из Long Story Short — готовые действия, спасброски, урон и дистанции.\\n"
            "Перетаскивайте или импортируйте отдельные чары. Любой чар можно отредактировать в листе участника."
        )
        desc.setWordWrap(True); desc.setStyleSheet("color: #807874; font-size: 11px; padding: 8px 16px;")
        root.addWidget(desc)

        list_frame = QFrame(); list_frame.setObjectName("panel")
        list_layout = QVBoxLayout(list_frame)
        list_title = QLabel("ИМПОРТИРОВАННЫЕ ЧАРНИКИ"); list_title.setObjectName("section")
        list_layout.addWidget(list_title)
        self._lss_charm_list = QListWidget()
        self._lss_charm_list.setMinimumHeight(180)
        self._lss_charm_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        list_layout.addWidget(self._lss_charm_list, 1)

        buttons = QHBoxLayout()
        refresh_charms = QPushButton("Обновить из LSS")
        refresh_charms.clicked.connect(self._refresh_lss_charms)
        buttons.addWidget(refresh_charms)
        export_charm = QPushButton("Экспорт выделенного")
        export_charm.clicked.connect(self._export_selected_charm)
        buttons.addWidget(export_charm)
        buttons.addStretch()
        list_layout.addLayout(buttons)

        root.addWidget(list_frame, 1)

        preview_frame = QFrame(); preview_frame.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_frame)
        preview_title = QLabel("ПРЕДПРОСМОТР ЧАРА"); preview_title.setObjectName("section")
        preview_layout.addWidget(preview_title)
        self._lss_charm_preview = QLabel("Выделите чарник для предпросмотра.")
        self._lss_charm_preview.setWordWrap(True)
        self._lss_charm_preview.setStyleSheet("color: #c6c0b8; font-size: 13px; padding: 10px 14px; background:#0d0b0c; border:1px solid #3a3030;")
        preview_layout.addWidget(self._lss_charm_preview, 1)
        root.addWidget(preview_frame, 1)

        empty_note = QLabel(
            "Пусто: импортируйте чарники через страницу «Импорт из LSS» или вставьте текст чара вручную.\\n"
            "Каждый чарник сохраняется как редактируемое действие на листе участника."
        )
        empty_note.setWordWrap(True); empty_note.setObjectName("muted")
        root.addWidget(empty_note)

        return container

    def _refresh_lss_charms(self) -> None:
        """Заполнить список чарников последней LSS-сессии (заглушка)."""
        sample = [
            "Пример: Удар мечом · 1d8+3 урона · дальн. 5 фт · спасбросок ЛОВ · 1d20+3 — ПРОМАХ",
            "Пример: Магическая вспышка · 2d6 урона · дистанция 30 фт · нет спасброска",
        ]
        self._lss_charm_list.clear()
        self._lss_charm_list.addItems(sample)

    def _export_selected_charm(self) -> None:
        """Создать действие из выделенного чарника (заглушка)."""
        row = self._lss_charm_list.currentRow()
        if row < 0:
            return self._lss_charm_preview.setText("Выделите чарник перед экспортом.")
        self._lss_charm_preview.setText(
            "Экспорт пока не реализован: свяжите чарник с участником через лист (правка действия)."
        )

    def _calculators_page(self, window: "MainWindow") -> QWidget:
        """Страница калькуляторов для визуализации боевых расчётов."""
        container = QWidget(); container.setObjectName("root")
        root = QVBoxLayout(container); root.setContentsMargins(0, 0, 0, 0)
        
        header = QHBoxLayout()
        title = QLabel("КАЛЬКУЛЯТОРЫ БОЯ"); title.setObjectName("title"); header.addWidget(title, 1)
        header.addStretch()
        root.addLayout(header)
        
        desc = QLabel(
            "Визуальные расчёты для подготовки боя.\n"
            "Бросайте кубы, сравнивайте КД, рассчитывайте спасброски и инициативу.\n"
            "Все параметры редактируются — подгоните расчёт под свою ситуацию."
        )
        desc.setWordWrap(True); desc.setStyleSheet("color: #807874; font-size: 11px; padding: 8px 16px;")
        root.addWidget(desc)
        
        # Вкладки калькуляторов
        tabs = QTabWidget()
        tabs.addTab(DamageCalculator(), "Урон и попадания")
        tabs.addTab(SaveDCcalculator(), "Спасброски и DC")
        tabs.addTab(ACComparison(), "Сравнение КД")
        tabs.addTab(InitiativeTracker(), "Инициатива")
        tabs.addTab(EncounterCalculator(self), "Встреча и XP")
        
        # Подсказки для каждой вкладки
        tips = QFrame(); tips.setObjectName("panel")
        tips_layout = QVBoxLayout(tips)
        tip_title = QLabel("РЕДАКТИРУЕМЫЕ ПАРАМЕТРЫ"); tip_title.setObjectName("section"); tips_layout.addWidget(tip_title)
        
        tip_data = QLabel(
            "Урон и попадания: формула броска, бонус атаки, КД цели, режим крита\n"
            "Спасброски: DC, характеристика, модификатор, урон/лечение, половина урона\n"
            "Сравнение КД: КД защищающегося/нападающего, преимущества, бонусы/пенальти\n"
            "Инициатива: список участников, бонусы, броски, очередь ходов\n"
            "Встреча и XP: уровни партии, CR противников, множитель численности, пороги сложности"
        )
        tip_data.setWordWrap(True); tip_data.setObjectName("muted"); tips_layout.addWidget(tip_data)
        root.addWidget(tips, 1)
        
        root.addWidget(tabs, 1)
        return container

    def _journal_page(self, window: "MainWindow") -> QWidget:
        """Хроника боя: полный журнал с фильтром и экспортом в Markdown."""
        container = QWidget(); container.setObjectName("root")
        root = QVBoxLayout(container); root.setContentsMargins(0, 0, 0, 0)
        header = QHBoxLayout()
        block = QVBoxLayout(); eyebrow = QLabel("ЛЕТОПИСЬ СТОЛА"); eyebrow.setObjectName("eyebrow"); block.addWidget(eyebrow)
        title = QLabel("Хроника боя"); title.setObjectName("title"); block.addWidget(title); header.addLayout(block, 1)
        export = QPushButton("Экспорт в Markdown"); export.clicked.connect(self.export_journal); header.addWidget(export)
        clear = QPushButton("Очистить"); clear.setObjectName("danger"); clear.setEnabled(self.is_gm()); clear.clicked.connect(self.clear_journal); header.addWidget(clear)
        root.addLayout(header)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Фильтр:"))
        journal_filter = QLineEdit(); journal_filter.setPlaceholderText("инициатива, имя, урон, спасбросок…")
        journal_filter.setObjectName("journalFilter"); filter_row.addWidget(journal_filter, 1)
        root.addLayout(filter_row)
        panel = QFrame(); panel.setObjectName("panel"); panel_layout = QVBoxLayout(panel)
        entries = list(reversed(self.campaign.battle.log))
        needle = ""
        if entries:
            shown = 0
            for number, line in enumerate(entries, start=1):
                if needle and needle not in line.lower():
                    continue
                row = QLabel(f"<span style='color:#6f625c'>#{len(entries) - number + 1:03d}</span>  {line}")
                row.setWordWrap(True); row.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                row.setStyleSheet("padding:7px 10px;border-bottom:1px solid #2a2324;font-size:12px")
                panel_layout.addWidget(row); shown += 1
            if not shown:
                panel_layout.addWidget(QLabel("По фильтру ничего не найдено."))
        else:
            empty = QLabel("Журнал пуст: инициатива, удары, передышки и спасброски появятся здесь автоматически.")
            empty.setObjectName("muted"); empty.setWordWrap(True); panel_layout.addWidget(empty)
        panel_layout.addStretch()
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(panel)
        root.addWidget(scroll, 1)
        stats = QLabel(f"Записей: {len(entries)} · хранится до 200 последних · раунд {self.campaign.battle.round_number or '—'}")
        stats.setObjectName("muted"); root.addWidget(stats)
        return container

    def export_journal(self) -> None:
        if not self.campaign.battle.log:
            return self.error("Хроника пока пуста")
        filename, _ = QFileDialog.getSaveFileName(self, "Экспорт хроники", "dragon-saga-journal.md", "Markdown (*.md *.txt)")
        if not filename:
            return
        try:
            lines = ["# Хроника «Драконьей Саги»", "", f"Кампания: {self.campaign.title} · редакция {self.campaign.edition}", ""]
            lines.extend(f"{index}. {entry}" for index, entry in enumerate(self.campaign.battle.log, start=1))
            Path(filename).write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.last_banner = f"Хроника экспортирована: {filename}"; self.refresh()
        except OSError as exc:
            self.error(str(exc))

    def clear_journal(self) -> None:
        if not self.is_gm():
            return
        if QMessageBox.question(self, "Очистить хронику", "Удалить все записи журнала боя?") == QMessageBox.StandardButton.Yes:
            self.campaign.battle.log = []
            self.commit("Хроника очищена")

    def closeEvent(self, event):  # type: ignore[override]
        if not self.network or self.is_gm(): save_campaign(self.campaign)
        if self.embedded_server:
            self.embedded_server.shutdown(); self.embedded_server.server_close()
        event.accept()


def run() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Драконья Сага")
    app.setOrganizationName("Meedazzz")
    icon_pixmap = QPixmap(); icon_pixmap.loadFromData(APP_ICON_SVG, "SVG"); app.setWindowIcon(QIcon(icon_pixmap))
    window = MainWindow(); window.show()
    return app.exec()
