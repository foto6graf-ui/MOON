"""A polished, account-free welcome screen for MOON."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """Introduce MOON and let the user open it without an account."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Добро пожаловать в MOON")
        self.setObjectName("WelcomeDialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(760, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        card = QWidget(self)
        card.setObjectName("WelcomeCard")
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(32, 18, 32, 24)
        layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        close_button = QPushButton("×", card)
        close_button.setObjectName("WelcomeCloseButton")
        close_button.setFixedSize(34, 34)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setToolTip("Закрыть")
        close_button.clicked.connect(self.reject)
        top_row.addWidget(close_button)
        layout.addLayout(top_row)

        brand = QLabel(card)
        brand.setObjectName("WelcomeBrand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(92, 92)
        mark_path = Path(__file__).resolve().parent.parent / "assets" / "glass_star_transparent.png"
        pixmap = QPixmap(str(mark_path))
        if not pixmap.isNull():
            brand.setPixmap(pixmap.scaled(
                78, 78,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        layout.addWidget(brand, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(10)

        eyebrow = QLabel("ПОИСК · ПАПКИ · БЫСТРЫЙ ДОСТУП", card)
        eyebrow.setObjectName("WelcomeEyebrow")
        eyebrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(eyebrow)
        layout.addSpacing(8)

        title = QLabel("Всё нужное — под рукой", card)
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)
        layout.addSpacing(8)

        description = QLabel(
            "MOON собирает приложения в одном месте. Ниже — короткая инструкция, "
            "как искать, группировать и настраивать их.", card
        )
        description.setObjectName("WelcomeDescription")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)

        features = QHBoxLayout()
        features.setSpacing(12)
        feature_data = (
            (
                "⌕",
                "Поиск и запуск",
                "Нажмите Ctrl+F и начните вводить название. Выберите результат и нажмите Enter. "
                "В сетке приложение запускается двойным щелчком.",
            ),
            (
                "▦",
                "Стеклянные папки",
                "Зажмите приложение мышью и перетащите его на другое. MOON соберёт их в папку. "
                "Нажмите на папку, чтобы открыть; перетащите туда ещё приложения, чтобы добавить.",
            ),
            (
                "⋯",
                "Меню и настройки",
                "Щёлкните правой кнопкой по приложению: добавьте в избранное, закрепите или удалите "
                "через деинсталлятор Windows. В меню MOON настройте внешний вид и поведение.",
            ),
        )
        for symbol, heading, detail in feature_data:
            feature = QFrame(card)
            feature.setObjectName("WelcomeFeatureCard")
            feature_layout = QVBoxLayout(feature)
            feature_layout.setContentsMargins(14, 14, 14, 14)
            feature_layout.setSpacing(8)
            symbol_label = QLabel(symbol, feature)
            symbol_label.setObjectName("WelcomeFeatureIcon")
            heading_label = QLabel(heading, feature)
            heading_label.setObjectName("WelcomeFeatureTitle")
            heading_label.setWordWrap(True)
            detail_label = QLabel(detail, feature)
            detail_label.setObjectName("WelcomeFeatureDescription")
            detail_label.setWordWrap(True)
            feature_layout.addWidget(symbol_label)
            feature_layout.addWidget(heading_label)
            feature_layout.addWidget(detail_label, 1)
            features.addWidget(feature, 1)
        layout.addSpacing(18)
        layout.addLayout(features)
        layout.addSpacing(12)

        hint = QLabel(
            "Зажмите Win и Alt одновременно, чтобы открыть или скрыть MOON.\n"
            "Папки, избранное и настройки сохраняются между запусками.",
            card,
        )
        hint.setObjectName("WelcomeHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
        layout.addStretch(1)

        self.start_button = QPushButton("Открыть MOON   →", card)
        self.start_button.setObjectName("WelcomeStartButton")
        self.start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.setMinimumHeight(54)
        self.start_button.clicked.connect(self.accept)
        layout.addWidget(self.start_button)
        layout.addSpacing(15)

        footer = QLabel("ВАШИ ПРИЛОЖЕНИЯ · ВАШ РИТМ", card)
        footer.setObjectName("WelcomeFooter")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        self.setStyleSheet("""
            QDialog#WelcomeDialog { background: transparent; }
            QWidget#WelcomeCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #20233a, stop:0.55 #171a2b, stop:1 #27213e);
                border: 1px solid rgba(210, 210, 255, 48);
                border-radius: 30px;
            }
            QLabel { background: transparent; border: none; color: #f6f5ff; }
            QLabel#WelcomeBrand { background: transparent; }
            QLabel#WelcomeEyebrow {
                color: #aaa4d4; font-size: 10px; font-weight: 700; letter-spacing: 2px;
            }
            QLabel#WelcomeTitle { font-size: 30px; font-weight: 700; }
            QLabel#WelcomeDescription { color: #b7bbcc; font-size: 14px; }
            QFrame#WelcomeFeatureCard {
                background: rgba(255,255,255,8);
                border: 1px solid rgba(210,210,255,28);
                border-radius: 18px;
            }
            QLabel#WelcomeFeatureIcon { color: #a99bff; font-size: 24px; font-weight: 600; }
            QLabel#WelcomeFeatureTitle { color: #f6f5ff; font-size: 14px; font-weight: 700; }
            QLabel#WelcomeFeatureDescription { color: #b7bbcc; font-size: 12px; }
            QLabel#WelcomeHint { color: #c8cbe0; font-size: 12px; }
            QLabel#WelcomeFooter { color: #777d98; font-size: 9px; letter-spacing: 2px; }
            QPushButton#WelcomeCloseButton {
                color: #9da3ba; background: rgba(255,255,255,10);
                border: 1px solid rgba(255,255,255,18); border-radius: 17px; font-size: 21px;
            }
            QPushButton#WelcomeCloseButton:hover { color: white; background: rgba(255,255,255,24); }
            QPushButton#WelcomeStartButton {
                color: white; font-size: 15px; font-weight: 600;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7868f4, stop:1 #9a69e8);
                border: 1px solid rgba(224,215,255,90); border-radius: 16px;
            }
            QPushButton#WelcomeStartButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #897bff, stop:1 #aa78f3);
            }
            QPushButton#WelcomeStartButton:pressed { background: #6b5bdc; }
        """)
