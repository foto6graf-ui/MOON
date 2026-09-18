"""Interface settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
)
from PySide6.QtCore import Qt

from utils.settings_store import InterfaceSettings


class InterfaceSettingsDialog(QDialog):
    """Dialog for editing Launchpad interface settings."""

    settings_applied = Signal(object)

    def __init__(self, settings: InterfaceSettings, parent: object | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки интерфейса")
        self.setModal(True)
        self.setStyleSheet(
            """
            QDialog {
                background: rgba(24, 28, 42, 235);
                color: #f5f5f5;
                border: 1px solid rgba(255, 255, 255, 35);
            }
            
            QLabel {
                color: #f5f5f5;
            }
            
            QCheckBox {
                color: #f5f5f5;
                spacing: 8px;
            }
            
            QPushButton {
                background: rgba(255, 255, 255, 24);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 10px;
                color: #f5f5f5;
                min-height: 34px;
                padding: 0 16px;
            }
            
            QPushButton:hover {
                background: rgba(77, 163, 255, 100);
                border: 1px solid rgba(120, 190, 255, 120);
            }
            
            QPushButton:pressed {
                background: rgba(77, 163, 255, 140);
            }
            
            /* ---------------- RADIO BUTTONS ---------------- */
            
            QRadioButton {
                spacing: 8px;
                color: #f5f5f5;
                min-height: 28px;
            }
            
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
                border-radius: 9px;
            }
            
            /* Стандартный */
            
            QRadioButton::indicator:unchecked {
                background: rgba(255, 255, 255, 12);
                border: 2px solid rgba(255, 255, 255, 80);
            }
            
            QRadioButton::indicator:checked {
                background: #4da3ff;
                border: 2px solid #4da3ff;
            }
            
            /* Зелёный */
            
            QRadioButton#glassGreen::indicator:unchecked {
                background: rgba(57, 228, 68, 15);
                border: 2px solid rgba(57, 228, 68, 100);
            }
            
            QRadioButton#glassGreen::indicator:checked {
                background: #39E444;
                border: 2px solid #39E444;
            }
            
            /* Розовый */
            
            QRadioButton#glassPink::indicator:unchecked {
                background: rgba(185, 0, 145, 15);
                border: 2px solid rgba(185, 0, 145, 100);
            }
            
            QRadioButton#glassPink::indicator:checked {
                background: #B90091;
                border: 2px solid #B90091;
            }
            
            /* ---------------- SLIDER ---------------- */
            
            QSlider::groove:horizontal {
                height: 6px;
                border-radius: 3px;
                background: rgba(255, 255, 255, 35);
            }
            
            QSlider::sub-page:horizontal {
                height: 6px;
                border-radius: 3px;
                background: rgba(77, 163, 255, 170);
            }
            
            QSlider::handle:horizontal {
                width: 17px;
                height: 17px;
                margin: -6px 0;
                border-radius: 9px;
                background: #f5f5f5;
                border: 2px solid #4da3ff;
            }
            
            QSlider::handle:horizontal:hover {
                background: #ffffff;
                border: 2px solid #69b4ff;
            }
            
            /* ---------------- INPUTS ---------------- */
            
            QSpinBox,
            QComboBox {
                background: rgba(255, 255, 255, 20);
                border: 1px solid rgba(255, 255, 255, 40);
                border-radius: 8px;
                color: #f5f5f5;
                min-height: 30px;
                padding: 2px 8px;
            }
            
            QSpinBox:hover,
            QComboBox:hover {
                background: rgba(255, 255, 255, 28);
                border: 1px solid rgba(255, 255, 255, 65);
            }
            """
        )
        self._settings = settings
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        form = QFormLayout()
        form.setVerticalSpacing(16)
        form.setHorizontalSpacing(16)
        self.matte_effect = QSlider(Qt.Orientation.Horizontal)
        self.matte_effect.setRange(0, 100)
        self.matte_effect.setValue(40)

        self.matte_value = QLabel("0.4")
        self.matte_effect.valueChanged.connect(
            lambda value: self.matte_value.setText(f"{value / 100:.1f}")
        )

        matte_row = QHBoxLayout()
        matte_row.addWidget(self.matte_effect)
        matte_row.addWidget(self.matte_value)

        form.addRow("Матовый эффект", matte_row)
        self.show_labels = QCheckBox("Показывать подписи")
        self.startup_with_windows = QCheckBox("Запускать с Windows")
        self.glass_default = QRadioButton("Стандартный")
        self.glass_green = QRadioButton("Зелёный")
        self.glass_pink = QRadioButton("Розовый")
        self.glass_green.setObjectName("glassGreen")
        self.glass_pink.setObjectName("glassPink")

        self.glass_default.setChecked(True)

        glass_row = QHBoxLayout()
        glass_row.addWidget(self.glass_default)
        glass_row.addWidget(self.glass_green)
        glass_row.addWidget(self.glass_pink)

        form.addRow("Цвет стекла", glass_row)





        form.addRow("", self.show_labels)
        form.addRow("", self.startup_with_windows)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        cancel = QPushButton("Отмена")
        apply = QPushButton("Применить")
        cancel.clicked.connect(self.reject)
        apply.clicked.connect(self._apply)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(apply)
        layout.addLayout(buttons)

    def _load_values(self) -> None:
        matte = int(self._settings.matte_effect * 100)

        self.matte_effect.setValue(matte)
        self.matte_value.setText(
            f"{self._settings.matte_effect:.1f}"
        )

        glass_color = self._settings.glass_color

        self.glass_default.setChecked(glass_color == "default")
        self.glass_green.setChecked(glass_color == "green")
        self.glass_pink.setChecked(glass_color == "pink")

        self.show_labels.setChecked(self._settings.show_labels)
        self.startup_with_windows.setChecked(
            self._settings.startup_with_windows
        )

    def _apply(self) -> None:
        self._settings.matte_effect = (
                self.matte_effect.value() / 100.0
        )

        if self.glass_green.isChecked():
            self._settings.glass_color = "green"
        elif self.glass_pink.isChecked():
            self._settings.glass_color = "pink"
        else:
            self._settings.glass_color = "default"

        self._settings.show_labels = self.show_labels.isChecked()

        self._settings.startup_with_windows = (
            self.startup_with_windows.isChecked()
        )

        self.settings_applied.emit(self._settings)
        self.accept()