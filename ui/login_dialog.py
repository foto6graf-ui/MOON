"""Glass-styled login screen shown before opening MOON."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.auth_client import authenticate_session, register_account, reset_password


class LoginWorker(QThread):
    finished_with_result = Signal(str, bool, str, str, float)

    def __init__(
        self,
        operation: str,
        login: str,
        password: str,
        pairing_code: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.operation = operation
        self.login = login
        self.password = password
        self.pairing_code = pairing_code

    def run(self) -> None:
        if self.operation == "register":
            success, message = register_account(self.login, self.password, self.pairing_code)
            token, expires_at = "", 0.0
        elif self.operation == "reset":
            success, message = reset_password(self.pairing_code, self.password)
            token, expires_at = "", 0.0
        else:
            success, message, token, expires_at = authenticate_session(self.login, self.password)
        self.password = ""
        self.finished_with_result.emit(self.operation, success, message, token, expires_at)


class LoginDialog(QDialog):
    """Require a successful server-side login before the app can start."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Вход в MOON")
        self.setObjectName("LoginDialog")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(470, 620)
        self._worker: LoginWorker | None = None
        self._register_mode = False
        self._reset_mode = False
        self.session_token = ""
        self.session_expires_at = 0.0
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)

        card = GlassCard(self)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(34, 26, 34, 24)
        layout.setSpacing(10)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.close_button = QPushButton("×", card)
        self.close_button.setObjectName("CloseButton")
        self.close_button.setFixedSize(32, 32)
        self.close_button.clicked.connect(self.reject)
        close_row.addWidget(self.close_button)
        layout.addLayout(close_row)

        brand = QLabel(card)
        brand.setObjectName("BrandMark")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedHeight(50)
        mark_path = Path(__file__).resolve().parent.parent / "assets" / "glass_star.png"
        pixmap = QPixmap(str(mark_path))
        if not pixmap.isNull():
            brand.setPixmap(
                pixmap.scaled(
                    brand.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self.title = QLabel("С возвращением", card)
        self.title.setObjectName("LoginTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle = QLabel("Войдите в аккаунт, чтобы продолжить")
        self.subtitle.setObjectName("LoginSubtitle")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addSpacing(12)

        self.login_label = QLabel("Логин", card)
        self.login_edit = QLineEdit(card)
        self.login_edit.setPlaceholderText("Введите логин")
        self.login_edit.setClearButtonEnabled(True)
        self.password_label = QLabel("Пароль", card)
        self.password_edit = PasswordEdit(card)
        self.password_edit.setPlaceholderText("Введите пароль")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self._submit)
        layout.addWidget(self.login_label)
        layout.addWidget(self.login_edit)
        layout.addWidget(self.password_label)
        layout.addWidget(self.password_edit)

        self.confirm_label = QLabel("Повторите пароль", card)
        self.confirm_edit = PasswordEdit(card)
        self.confirm_edit.setPlaceholderText("Повторите пароль")
        self.confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pairing_label = QLabel("Код из Telegram", card)
        self.pairing_edit = QLineEdit(card)
        self.pairing_edit.setPlaceholderText("Например, A7K9M2Q4")
        for widget in (
            self.confirm_label,
            self.confirm_edit,
            self.pairing_label,
            self.pairing_edit,
        ):
            widget.hide()
            layout.addWidget(widget)

        self.reset_code_label = QLabel("Код из Telegram", card)
        self.reset_code_edit = QLineEdit(card)
        self.reset_code_edit.setPlaceholderText("Одноразовый код из Telegram-бота")
        self.reset_password_label = QLabel("Новый пароль", card)
        self.reset_password_edit = PasswordEdit(card)
        self.reset_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_confirm_label = QLabel("Повторите новый пароль", card)
        self.reset_confirm_edit = PasswordEdit(card)
        self.reset_confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.reset_fields = (
            self.reset_code_label,
            self.reset_code_edit,
            self.reset_password_label,
            self.reset_password_edit,
            self.reset_confirm_label,
            self.reset_confirm_edit,
        )
        for widget in self.reset_fields:
            widget.hide()
            layout.addWidget(widget)

        self.status_label = QLabel("", card)
        self.status_label.setObjectName("LoginStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.submit_button = QPushButton("Войти", card)
        self.submit_button.setObjectName("LoginButton")
        self.submit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.submit_button.clicked.connect(self._submit)
        layout.addWidget(self.submit_button)

        self.mode_button = QPushButton("Создать аккаунт", card)
        self.mode_button.setObjectName("ModeButton")
        self.mode_button.clicked.connect(self._on_mode_button)
        layout.addWidget(self.mode_button)

        self.forgot_button = QPushButton("Забыли пароль? Получить код в Telegram", card)
        self.forgot_button.setObjectName("ModeButton")
        self.forgot_button.clicked.connect(self._enter_reset_mode)
        layout.addWidget(self.forgot_button)

        note = QLabel("Защищённое соединение · MOON Account")
        note.setObjectName("SecurityNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(note)

        self.setStyleSheet(
            """
            QDialog#LoginDialog { background: transparent; }
            QLabel { color: #f4f6fc; }
            QLabel#BrandMark { background: transparent; }
            QLabel#LoginTitle { font-size: 25px; font-weight: 700; }
            QLabel#LoginSubtitle, QLabel#SecurityNote { color: #a6afc2; font-size: 12px; }
            QLabel#LoginStatus { color: #ff9caa; min-height: 20px; }
            QLineEdit { color: #f4f6fc; background: rgba(9, 13, 24, 145); border: 1px solid rgba(205, 215, 240, 42); border-radius: 11px; min-height: 42px; padding: 0 13px; selection-background-color: #7868f7; }
            QLineEdit:focus { border: 1px solid #9286ff; background: rgba(12, 17, 31, 200); }
            QToolButton#PasswordToggle { color: #aeb6cc; background: transparent; border: none; min-width: 30px; min-height: 30px; font-size: 16px; }
            QToolButton#PasswordToggle:hover { color: #ffffff; background: rgba(255, 255, 255, 20); border-radius: 8px; }
            QPushButton { color: #eef0f8; background: rgba(255, 255, 255, 15); border: 1px solid rgba(255, 255, 255, 35); border-radius: 10px; }
            QPushButton#CloseButton { font-size: 22px; }
            QPushButton#CloseButton:hover { background: rgba(255, 255, 255, 35); }
            QPushButton#LoginButton { color: white; font-size: 14px; font-weight: 600; background: #7566f4; border: 1px solid rgba(200, 192, 255, 80); min-height: 46px; margin-top: 4px; }
            QPushButton#LoginButton:hover { background: #877aff; }
            QPushButton#LoginButton:disabled { color: #bdc1cf; background: #49465f; }
            QPushButton#ModeButton { color: #c7c0ff; background: transparent; border: none; min-height: 34px; }
            QPushButton#ModeButton:hover { color: #ffffff; }
            """
        )

    def _submit(self) -> None:
        login = self.login_edit.text().strip()
        password = self.password_edit.text()
        if self._reset_mode:
            password = self.reset_password_edit.text()
            if len(password) < 10 or len(password) > 128:
                self.status_label.setText("Пароль должен содержать от 10 до 128 символов.")
                return
            if password != self.reset_confirm_edit.text():
                self.status_label.setText("Пароли не совпадают.")
                return
            if not self.reset_code_edit.text().strip():
                self.status_label.setText("Получите одноразовый код в Telegram-боте.")
                return
        elif not login or not password:
            self.status_label.setText("Введите логин и пароль.")
            return
        if self._register_mode:
            if len(password) < 10 or len(password) > 128:
                self.status_label.setText("Пароль должен содержать от 10 до 128 символов.")
                return
            if password != self.confirm_edit.text():
                self.status_label.setText("Пароли не совпадают.")
                return
            if not self.pairing_edit.text().strip():
                self.status_label.setText("Сначала получите код привязки в Telegram-боте.")
                return
        if self._worker is not None and self._worker.isRunning():
            return
        self.status_label.setText("Проверяем данные…")
        self.status_label.setStyleSheet("color: #c5c0ff;")
        self.submit_button.setEnabled(False)
        self.login_edit.setEnabled(False)
        self.password_edit.setEnabled(False)
        for widget in self.reset_fields:
            widget.setEnabled(False)
        self.close_button.setEnabled(False)
        self.mode_button.setEnabled(False)
        self.forgot_button.setEnabled(False)
        operation = "reset" if self._reset_mode else "register" if self._register_mode else "login"
        pairing_code = self.reset_code_edit.text().strip() if self._reset_mode else self.pairing_edit.text().strip()
        self._worker = LoginWorker(
            operation,
            login,
            password,
            pairing_code,
            self,
        )
        self._worker.finished_with_result.connect(self._on_result)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.start()

    def _on_result(
        self, operation: str, success: bool, message: str, session_token: str, expires_at: float
    ) -> None:
        self._worker = None
        self.submit_button.setEnabled(True)
        self.login_edit.setEnabled(True)
        self.password_edit.setEnabled(True)
        self.confirm_edit.setEnabled(True)
        self.pairing_edit.setEnabled(True)
        self.mode_button.setEnabled(True)
        self.forgot_button.setEnabled(True)
        for widget in self.reset_fields:
            widget.setEnabled(True)
        self.close_button.setEnabled(True)
        if operation == "login" and success:
            self.session_token = session_token
            self.session_expires_at = expires_at
            self.accept()
            return
        if operation == "register" and success:
            self._set_mode(False)
            self.password_edit.clear()
            self.confirm_edit.clear()
            self.pairing_edit.clear()
            self.status_label.setStyleSheet("color: #8de0b1;")
            self.status_label.setText("Аккаунт создан. Для доступа оформите покупку в Telegram-боте.")
            return
        if operation == "reset" and success:
            self._set_mode(False)
            self.reset_code_edit.clear()
            self.reset_password_edit.clear()
            self.reset_confirm_edit.clear()
            self.status_label.setStyleSheet("color: #8de0b1;")
            self.status_label.setText("Пароль обновлён. Теперь войдите с новым паролем.")
            return
        self.status_label.setStyleSheet("color: #ff9caa;")
        self.status_label.setText(message)

    def _toggle_mode(self) -> None:
        self._set_mode(not self._register_mode)

    def _on_mode_button(self) -> None:
        if self._reset_mode:
            self._set_mode(False)
            return
        self._toggle_mode()

    def _enter_reset_mode(self) -> None:
        self._register_mode = False
        self._reset_mode = True
        self.title.setText("Восстановление пароля")
        self.subtitle.setText("Получите одноразовый код в Telegram-боте")
        self.submit_button.setText("Сменить пароль")
        self.mode_button.setText("Назад ко входу")
        self.forgot_button.hide()
        for widget in (
            self.login_label, self.login_edit, self.password_label, self.password_edit,
            self.confirm_label, self.confirm_edit, self.pairing_label, self.pairing_edit,
        ):
            widget.hide()
        for widget in self.reset_fields:
            widget.show()
        self.status_label.clear()
        self.setFixedSize(470, 690)

    def _set_mode(self, registering: bool) -> None:
        returning_from_reset = self._reset_mode
        self._register_mode = registering
        self._reset_mode = False
        self.title.setText("Создать аккаунт" if registering else "С возвращением")
        self.subtitle.setText(
            "Введите данные и код привязки из Telegram"
            if registering
            else "Войдите в аккаунт, чтобы продолжить"
        )
        self.submit_button.setText("Зарегистрироваться" if registering else "Войти")
        self.mode_button.setText("Уже есть аккаунт · Войти" if registering else "Создать аккаунт")
        for widget in (self.confirm_label, self.confirm_edit, self.pairing_label, self.pairing_edit):
            widget.setVisible(registering)
        for widget in self.reset_fields:
            widget.hide()
        for widget in (
            self.login_label,
            self.login_edit,
            self.password_label,
            self.password_edit,
        ):
            widget.show()
        if returning_from_reset:
            self.password_edit.clear()
            self.password_edit.toggle_button.setChecked(False)
            self.reset_code_edit.clear()
            self.reset_password_edit.clear()
            self.reset_password_edit.toggle_button.setChecked(False)
            self.reset_confirm_edit.clear()
            self.reset_confirm_edit.toggle_button.setChecked(False)
        self.forgot_button.setVisible(not registering)
        self.status_label.clear()
        self.status_label.setStyleSheet("")
        self.setFixedSize(470, 750 if registering else 620)

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        super().reject()


class PasswordEdit(QLineEdit):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setTextMargins(0, 0, 38, 0)
        self.toggle_button = QToolButton(self)
        self.toggle_button.setObjectName("PasswordToggle")
        self.toggle_button.setText("◉")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_button.setToolTip("Показать пароль")
        self.toggle_button.toggled.connect(self._toggle_visibility)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "toggle_button"):
            return
        button_size = self.toggle_button.sizeHint()
        self.toggle_button.setGeometry(
            self.width() - button_size.width() - 6,
            (self.height() - button_size.height()) // 2,
            button_size.width(),
            button_size.height(),
        )

    def _toggle_visibility(self, visible: bool) -> None:
        self.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.toggle_button.setText("◎" if visible else "◉")
        self.toggle_button.setToolTip("Скрыть пароль" if visible else "Показать пароль")


class GlassCard(QWidget):
    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 25, 25)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor(42, 49, 70, 238))
        gradient.setColorAt(0.5, QColor(25, 31, 49, 232))
        gradient.setColorAt(1.0, QColor(17, 22, 36, 242))
        painter.fillPath(path, gradient)
        painter.setPen(QColor(255, 255, 255, 60))
        painter.drawPath(path)
