"""
Настройки бота. Все параметры берутся из переменных окружения / .env файла.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Загружаем .env если он есть рядом с файлом настроек
_BASE_DIR = Path(__file__).parent.parent
load_dotenv(_BASE_DIR / ".env")


@dataclass
class Settings:
    # ── Обязательные ────────────────────────────────────────────────────────
    BOT_TOKEN: str = field(default_factory=lambda: _require("BOT_TOKEN"))

    # ── ID администраторов (через запятую) ───────────────────────────────────
    ADMIN_IDS: List[int] = field(
        default_factory=lambda: [
            int(x.strip())
            for x in os.getenv("ADMIN_IDS", "").split(",")
            if x.strip().isdigit()
        ]
    )

    # ── Источники прокси ─────────────────────────────────────────────────────
    PROXY_SOURCES: dict = field(
        default_factory=lambda: {
            "mtproto_ru": "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_ru.txt",
            "mtproto_eu": "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_eu.txt",
            "mtproto_all": "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/proxy_all.txt",
            "socks5": "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/socks5.txt",
            "json_verified": "https://raw.githubusercontent.com/kort0881/telegram-proxy-collector/main/verified/proxy_all_verified.json",
        }
    )

    # ── Автообновление ────────────────────────────────────────────────────────
    AUTO_UPDATE_INTERVAL: int = int(os.getenv("AUTO_UPDATE_INTERVAL", "3600"))  # секунды
    AUTO_NOTIFY_USERS: bool = os.getenv("AUTO_NOTIFY_USERS", "true").lower() == "true"

    # ── Проверка прокси ───────────────────────────────────────────────────────
    CHECK_TIMEOUT: int = int(os.getenv("CHECK_TIMEOUT", "8"))         # секунды
    MAX_PING_MS: int = int(os.getenv("MAX_PING_MS", "3000"))          # мс
    TOP_PROXIES_COUNT: int = int(os.getenv("TOP_PROXIES_COUNT", "10"))

    # ── Хранилище ─────────────────────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", str(_BASE_DIR / "proxy_bot.db"))

    # ── Предпочитаемый регион ─────────────────────────────────────────────────
    DEFAULT_REGION: str = os.getenv("DEFAULT_REGION", "all")  # ru / eu / all

    # ── Предпочитаемый тип прокси ─────────────────────────────────────────────
    DEFAULT_PROXY_TYPE: str = os.getenv("DEFAULT_PROXY_TYPE", "mtproto")  # mtproto / socks5


def _require(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Обязательная переменная окружения '{key}' не задана.\n"
            f"Создайте файл .env в корне проекта (см. .env.example)."
        )
    return value


settings = Settings()
