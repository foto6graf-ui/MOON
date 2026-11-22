"""Interface settings dialog."""

from __future__ import annotations

from copy import copy

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from utils.settings_store import InterfaceSettings


class InterfaceSettingsDialog(QDialog):
    """Dialog for editing Launchpad interface settings."""

    settings_applied = Signal(object)
    settings_previewed = Signal(object)

    def __init__(self, settings: InterfaceSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки MOON")
        self.setObjectName("SettingsDialog")
        self.setModal(True)
        self.setMinimumWidth(540)
        self.setStyleSheet(
            """
            QDialog#SettingsDialog { background: #0c111d; color: #f4f6fc; }
            QLabel { color: #f4f6fc; }
            QLabel#PageTitle { font-size: 23px; font-weight: 700; }
            QLabel#PageSubtitle, QLabel#SettingHint { color: #929bb0; }
            QLabel#SectionTitle { font-size: 13px; font-weight: 700; color: #b6c0d5; }
            QFrame#SettingsCard { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1c2537, stop:1 #151b29); border: 1px solid #303b52; border-radius: 16px; }
            QTabWidget::pane { border: 1px solid #293449; border-radius: 13px; background: #111826; top: -1px; }
            QTabWidget::tab-bar { alignment: right; }
            QTabBar::tab { color: #9da9be; background: #171f2e; padding: 10px 20px; margin-right: 6px; border: 1px solid #293449; border-bottom: none; border-top-left-radius: 9px; border-top-right-radius: 9px; }
            QTabBar::tab:selected { color: #ffffff; background: #282747; border-color: #6259a8; }
            QTabBar::tab:hover:!selected { color: #dfe4ef; background: #202a3c; }
            QCheckBox, QRadioButton { color: #eef1f8; spacing: 9px; min-height: 26px; }
            QCheckBox::indicator { width: 17px; height: 17px; border-radius: 5px; border: 1px solid #59647c; background: #20283a; }
            QCheckBox::indicator:checked { background: #7c6cff; border-color: #7c6cff; }
            QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px; border: 1px solid #59647c; background: #20283a; }
            QRadioButton::indicator:checked { background: #7c6cff; border: 4px solid #7c6cff; }
            QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #343d53; }
            QSlider::sub-page:horizontal { background: #7c6cff; border-radius: 2px; }
            QSlider::handle:horizontal { width: 16px; margin: -6px 0; border-radius: 8px; background: #fff; border: 2px solid #7c6cff; }
            QSlider#HueSlider::groove:horizontal { height: 13px; border-radius: 6px; border: 1px solid rgba(255,255,255,65); background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff3b30, stop:0.17 #ffd60a, stop:0.33 #32d74b, stop:0.5 #64d2ff, stop:0.67 #0a84ff, stop:0.83 #bf5af2, stop:1 #ff375f); }
            QSlider#HueSlider::sub-page:horizontal { background: transparent; }
            QSlider#HueSlider::handle:horizontal { width: 18px; margin: -5px 0; border-radius: 9px; background: #ffffff; border: 2px solid #20283b; }
            QLabel#GlassColorPreview { border: 1px solid rgba(255,255,255,120); border-radius: 7px; }
            QLabel#ValueLabel { color: #c9d0df; font-weight: 600; }
            QPushButton { min-height: 38px; padding: 0 17px; border-radius: 10px; color: #e8ebf4; background: #252d40; border: 1px solid #36415a; }
            QPushButton:hover { background: #303a52; }
            QPushButton#ApplyButton { color: white; background: #7162f5; border: 1px solid #8175ff; font-weight: 600; }
            QPushButton#ApplyButton:hover { background: #8275ff; }
            """
        )
        self._settings = copy(settings)
        self.settings_were_applied = False
        self._build_ui()
        self._load_values()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(70)
        self._preview_timer.timeout.connect(self._emit_preview)
        self.matte_effect.valueChanged.connect(self._schedule_preview)
        self.white_fill.valueChanged.connect(self._schedule_preview)
        self.glass_thickness.valueChanged.connect(self._schedule_preview)
        self.glass_hue.valueChanged.connect(self._schedule_preview)
        self.glass_classic.toggled.connect(self._schedule_preview)
        self.glass_palette.toggled.connect(self._schedule_preview)
        self.startup_with_windows.toggled.connect(self._confirm_startup_change)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(16)
        title = QLabel("Настройки")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Настройте внешний вид и поведение MOON")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        tabs = QTabWidget(self)
        tabs.setObjectName("SettingsTabs")
        general_page = QWidget(tabs)
        general_layout = QVBoxLayout(general_page)
        general_layout.setContentsMargins(12, 12, 12, 12)
        general_layout.setSpacing(14)
        tabs.addTab(general_page, "Интерфейс")
        appearance = self._card("ВНЕШНИЙ ВИД")
        appearance_layout = appearance.layout()
        matte_row = QHBoxLayout()
        matte_row.setSpacing(14)
        matte_label = QLabel("Матовая поверхность")
        self.matte_effect = QSlider(Qt.Orientation.Horizontal)
        self.matte_effect.setRange(0, 100)
        self.matte_effect.setPageStep(10)
        self.matte_effect.setToolTip("Степень матовости стекла")
        self.matte_value = QLabel("0.20")
        self.matte_value.setMinimumWidth(30)
        self.matte_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.matte_effect.valueChanged.connect(lambda value: self.matte_value.setText(f"{value / 100:.2f}"))
        matte_row.addWidget(self.matte_effect, 1)
        matte_row.addWidget(self.matte_value)
        appearance_layout.addWidget(self._setting_row(matte_label, matte_row))

        white_row = QHBoxLayout()
        self.white_fill = QSlider(Qt.Orientation.Horizontal)
        self.white_fill.setRange(0, 40)
        self.white_fill.setPageStep(4)
        self.white_fill.setToolTip("Интенсивность светлого слоя")
        self.white_fill_value = QLabel("20")
        self.white_fill_value.setMinimumWidth(34)
        self.white_fill.valueChanged.connect(lambda value: self.white_fill_value.setText(str(value)))
        white_row.addWidget(self.white_fill, 1)
        white_row.addWidget(self.white_fill_value)
        appearance_layout.addWidget(self._setting_row(QLabel("Белая заливка"), white_row))

        depth_row = QHBoxLayout()
        self.glass_thickness = QSlider(Qt.Orientation.Horizontal)
        self.glass_thickness.setRange(35, 65)
        self.glass_thickness.setPageStep(3)
        self.glass_thickness.setToolTip("Толщина преломления стекла")
        self.glass_thickness_value = QLabel("0.50")
        self.glass_thickness_value.setMinimumWidth(34)
        self.glass_thickness.valueChanged.connect(lambda value: self.glass_thickness_value.setText(f"{value / 100:.2f}"))
        depth_row.addWidget(self.glass_thickness, 1)
        depth_row.addWidget(self.glass_thickness_value)
        appearance_layout.addWidget(self._setting_row(QLabel("Глубина стекла"), depth_row))
        color_label = QLabel("Цвет стекла")
        self.glass_default = QRadioButton("Классический")
        self.glass_green = QRadioButton("Зелёный")
        self.glass_pink = QRadioButton("Розовый")
        self.glass_default.setObjectName("glassDefault")
        self.glass_green.setObjectName("glassGreen")
        self.glass_pink.setObjectName("glassPink")
        color_row = QHBoxLayout()
        color_row.setSpacing(16)
        for option in (self.glass_default, self.glass_green, self.glass_pink):
            color_row.addWidget(option)
        color_row.addStretch(1)
        legacy_color_row = self._setting_row(color_label, color_row)
        appearance_layout.addWidget(legacy_color_row)
        legacy_color_row.hide()
        color_label.hide()
        self.glass_default.hide()
        self.glass_green.hide()
        self.glass_pink.hide()
        self._build_glass_palette(appearance_layout)
        general_layout.addWidget(appearance)
        behavior = self._card("ПОВЕДЕНИЕ")
        behavior_layout = behavior.layout()
        self.show_labels = QCheckBox("Показывать подписи приложений")
        self.startup_with_windows = QCheckBox("Запускать MOON вместе с Windows")
        behavior_layout.addWidget(self._setting_row(self.show_labels))
        behavior_layout.addWidget(self._setting_row(self.startup_with_windows))
        startup_hint = QLabel("MOON будет запускаться автоматически после входа в Windows для этого пользователя.")
        startup_hint.setObjectName("SettingHint")
        startup_hint.setWordWrap(True)
        behavior_layout.addWidget(startup_hint)
        general_layout.addWidget(behavior)
        general_layout.addStretch(1)
        layout.addWidget(tabs, 1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Отмена")
        apply = QPushButton("Сохранить")
        apply.setObjectName("ApplyButton")
        cancel.clicked.connect(self.reject)
        apply.clicked.connect(self._apply)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def _confirm_startup_change(self, enabled: bool) -> None:
        if not enabled:
            return
        answer = QMessageBox.question(
            self,
            "Автозагрузка MOON",
            "Разрешить запуск MOON после входа в Windows для этого пользователя?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.startup_with_windows.setChecked(False)

    @staticmethod
    def _card(title: str) -> QFrame:
        card = QFrame()
        card.setObjectName("SettingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(12)
        heading = QLabel(title)
        heading.setObjectName("SectionTitle")
        card_layout.addWidget(heading)
        return card

    @staticmethod
    def _setting_row(label: QWidget, control: QWidget | QHBoxLayout | None = None) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        if isinstance(control, QHBoxLayout):
            row_layout.addWidget(label)
            row_layout.addLayout(control, 1)
        elif control is not None:
            row_layout.addWidget(label)
            row_layout.addWidget(control)
            row_layout.addStretch(1)
        else:
            row_layout.addWidget(label)
            row_layout.addStretch(1)
        return row

    def _build_glass_palette(self, layout: QVBoxLayout) -> None:
        mode_row = QHBoxLayout()
        self.glass_classic = QRadioButton("Классическое")
        self.glass_palette = QRadioButton("Палитра")
        mode_row.addWidget(self.glass_classic)
        mode_row.addWidget(self.glass_palette)
        mode_row.addStretch(1)
        layout.addWidget(self._setting_row(QLabel("Цвет стекла"), mode_row))

        palette_row = QHBoxLayout()
        palette_row.setSpacing(12)
        self.glass_hue = QSlider(Qt.Orientation.Horizontal)
        self.glass_hue.setObjectName("HueSlider")
        self.glass_hue.setRange(0, 359)
        self.glass_hue.setPageStep(30)
        self.glass_hue.setToolTip("Оттенок цвета стекла")
        self.glass_color_preview = QLabel()
        self.glass_color_preview.setObjectName("GlassColorPreview")
        self.glass_color_preview.setFixedSize(42, 24)
        self.glass_color_value = QLabel()
        self.glass_color_value.setObjectName("ValueLabel")
        self.glass_color_value.setMinimumWidth(68)
        self.glass_hue.valueChanged.connect(self._update_palette_preview)
        self.glass_palette.toggled.connect(self.glass_hue.setEnabled)
        palette_row.addWidget(self.glass_hue, 1)
        palette_row.addWidget(self.glass_color_preview)
        palette_row.addWidget(self.glass_color_value)
        layout.addWidget(self._setting_row(QLabel("Оттенок"), palette_row))

    def _update_palette_preview(self, hue: int) -> None:
        color = QColor.fromHsv(hue, 205, 245)
        self.glass_color_preview.setStyleSheet(
            f"background: {color.name()};"
        )
        self.glass_color_value.setText(color.name().upper())

    def _load_values(self) -> None:
        self.matte_effect.setValue(int(self._settings.matte_effect * 100))
        self.matte_value.setText(f"{self.matte_effect.value() / 100:.2f}")
        self.white_fill.setValue(self._settings.panel_opacity)
        self.glass_thickness.setValue(int(self._settings.glass_thickness * 100))
        self.glass_thickness_value.setText(f"{self.glass_thickness.value() / 100:.2f}")
        color_value = self._settings.glass_color
        legacy_colors = {"green": "#39e444", "pink": "#b90091"}
        if color_value == "default":
            self.glass_classic.setChecked(True)
            self.glass_hue.setValue(260)
        else:
            color = QColor(legacy_colors.get(color_value, color_value))
            if color.isValid():
                self.glass_palette.setChecked(True)
                self.glass_hue.setValue(max(0, color.hue()))
            else:
                self.glass_classic.setChecked(True)
                self.glass_hue.setValue(260)
        self.glass_hue.setEnabled(self.glass_palette.isChecked())
        self._update_palette_preview(self.glass_hue.value())
        self.show_labels.setChecked(self._settings.show_labels)
        self.startup_with_windows.setChecked(self._settings.startup_with_windows)

    def _apply(self) -> None:
        self._preview_timer.stop()
        self._settings = self._collect_settings()
        self.settings_were_applied = True
        self.settings_applied.emit(self._settings)
        self.accept()

    def _collect_settings(self) -> InterfaceSettings:
        settings = copy(self._settings)
        settings.matte_effect = self.matte_effect.value() / 100.0
        settings.panel_opacity = self.white_fill.value()
        settings.glass_thickness = self.glass_thickness.value() / 100.0
        if self.glass_classic.isChecked():
            settings.glass_color = "default"
        else:
            settings.glass_color = QColor.fromHsv(
                self.glass_hue.value(), 205, 245
            ).name()
        settings.show_labels = self.show_labels.isChecked()
        settings.startup_with_windows = self.startup_with_windows.isChecked()
        return settings

    def _schedule_preview(self, *_args: object) -> None:
        self._preview_timer.start()

    def _emit_preview(self) -> None:
        self.settings_previewed.emit(self._collect_settings())

    def stop_pending_preview(self) -> None:
        self._preview_timer.stop()
