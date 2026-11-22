"""Client for the MOON account API."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


LOGGER = logging.getLogger("moon.auth_client")


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def authenticate(login: str, password: str) -> tuple[bool, str]:
    success, message, _token, _expires_at = authenticate_session(login, password)
    return success, message


def authenticate_session(login: str, password: str) -> tuple[bool, str, str, float]:
    result, message = _request_payload(
        "/api/auth/login", {"login": login, "password": password}, retry=True
    )
    if result is None or result.get("authorized") is not True:
        return False, message, "", 0.0
    token = result.get("session_token")
    expires_at = result.get("session_expires_at")
    if not isinstance(token, str) or not token:
        return False, "Сервер не выдал сессию. Попробуйте войти ещё раз.", "", 0.0
    try:
        expiration = float(expires_at)
    except (TypeError, ValueError):
        return False, "Сервер вернул некорректную сессию.", "", 0.0
    return True, "", token, expiration


def register_account(login: str, password: str, telegram_code: str) -> tuple[bool, str]:
    result, message = _request_payload(
        "/api/auth/register",
        {"login": login, "password": password, "telegram_code": telegram_code},
        retry=True,
    )
    if result is not None and result.get("registered") is True:
        return True, str(result.get("message", ""))
    return False, message


def reset_password(telegram_code: str, password: str) -> tuple[bool, str]:
    result, message = _request_payload(
        "/api/auth/password-reset",
        {"telegram_code": telegram_code, "password": password},
        retry=False,
    )
    if result is not None and result.get("password_reset") is True:
        return True, str(result.get("message", "Пароль обновлён."))
    return False, message


def validate_session(token: str) -> tuple[bool, str]:
    valid, message, _expires_at = renew_session(token)
    return valid, message


def renew_session(token: str) -> tuple[bool, str, float]:
    result, message = _request_payload(
        "/api/auth/session", {}, retry=True, session_token=token, timeout=4
    )
    if result is not None and result.get("authorized") is True:
        try:
            return True, "", float(result["expires_at"])
        except (KeyError, TypeError, ValueError):
            return False, "Сервер вернул некорректную сессию.", 0.0
    if result is not None and result.get("code") == "session_invalid":
        return False, "session_invalid: Сессия завершена или доступ отозван.", 0.0
    return False, message, 0.0


def logout_session(token: str) -> None:
    _request_payload("/api/auth/logout", {}, retry=False, session_token=token, timeout=2)


def _base_url() -> str:
    base_url = os.environ.get("MOON_AUTH_URL", "").strip().rstrip("/")
    # Release builds include only this public URL, never the developer's .env.
    if not base_url and getattr(sys, "frozen", False):
        bundled_url = Path(getattr(sys, "_MEIPASS", "")) / "moon_auth_url.txt"
        try:
            base_url = bundled_url.read_text(encoding="utf-8").strip().rstrip("/")
        except OSError:
            pass
    if not base_url:
        config_path = Path(__file__).resolve().parent.parent / ".env"
        try:
            for line in config_path.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "MOON_AUTH_URL":
                    base_url = value.strip().strip("\"'").rstrip("/")
                    break
        except OSError:
            pass
    # Packaged one-file builds do not bundle the developer's .env file.
    # Keep local development usable without embedding a private endpoint or key.
    return base_url or "http://127.0.0.1:8765"


def _request_payload(
    path: str,
    payload: dict[str, str],
    *,
    retry: bool,
    session_token: str = "",
    timeout: float = 8,
) -> tuple[dict[str, object] | None, str]:
    base_url = _base_url()
    if not base_url:
        return None, "Сервер авторизации не настроен. Обратитесь к администратору."
    parsed_url = urlsplit(base_url)
    local_http = parsed_url.scheme == "http" and parsed_url.hostname in {
        "127.0.0.1", "localhost", "::1"
    }
    if parsed_url.scheme != "https" and not local_http:
        return None, "Для удалённого сервера авторизации требуется HTTPS."
    if not parsed_url.hostname or parsed_url.username or parsed_url.password:
        return None, "В адресе сервера авторизации указана некорректная конфигурация."

    endpoint = base_url if base_url.endswith(path) else base_url + path
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if session_token:
        headers["Authorization"] = f"Bearer {session_token}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    attempts = 2 if retry else 1
    for attempt in range(attempts):
        try:
            opener = build_opener(_NoRedirectHandler)
            with opener.open(request, timeout=timeout) as response:
                decoded = json.loads(response.read().decode("utf-8"))
            if isinstance(decoded, dict):
                return decoded, ""
            return None, "Сервер вернул некорректный ответ."
        except HTTPError as error:
            try:
                decoded = json.loads(error.read().decode("utf-8"))
            except (OSError, ValueError):
                decoded = None
            if isinstance(decoded, dict):
                return decoded, _response_message(decoded, error.code)
            return None, _response_message({}, error.code)
        except (URLError, TimeoutError, OSError, ValueError) as error:
            LOGGER.warning("API request failed: route=%s type=%s", path, type(error).__name__)
            if attempt + 1 >= attempts:
                return None, "Не удалось связаться с сервером. Проверьте интернет и повторите попытку."
            time.sleep(0.4 * (2 ** attempt))
    return None, "Не удалось выполнить запрос. Повторите попытку."


def _response_message(payload: object, status_code: int | None = None) -> str:
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    if status_code in (401, 403):
        return "Сессия или доступ недействительны. Войдите снова."
    if status_code == 409:
        return "Логин или Telegram уже привязан к другому аккаунту."
    if status_code == 422:
        return "Проверьте введённые данные и срок действия кода."
    if status_code == 429:
        return "Слишком много попыток. Подождите и попробуйте снова."
    return "Сервер временно недоступен. Попробуйте позже."
