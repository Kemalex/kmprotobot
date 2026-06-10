"""
Общие команды: /start, /help, меню.
"""

from __future__ import annotations

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

from utils.keyboards import main_menu_kb

router = Router(name="common")

WELCOME_TEXT = """
👋 <b>Telegram Proxy Bot</b>

Автоматически нахожу и проверяю свежие прокси каждый час. \
Одним нажатием подключаешь лучший прокси прямо в Telegram.

<b>Что умею:</b>
• 🔄 Выдать лучший проверенный прокси
• 📋 Показать топ-10 прокси по пингу
• 🇷🇺 / 🇪🇺 Фильтровать по региону
• 🔒 Prioritize Probe-Resistant прокси (обходит DPI)
• 🔔 Уведомлять при обновлении базы
• ⚙️ Настраивать тип и регион под себя

<b>Источник прокси:</b>
<a href="https://kort0881.github.io/telegram-proxy-collector/">Telegram Proxy Collector</a> — обновляется ежечасно

Нажми <b>🔄 Получить прокси</b> чтобы начать!
""".strip()

HELP_TEXT = """
📖 <b>Справка</b>

/start — Главное меню
/proxy — Лучший прокси прямо сейчас
/top — Топ-10 прокси
/stats — Статистика базы
/subscribe — Подписка на обновления
/settings — Настройки (регион, тип прокси)
/help — Эта справка

<b>Типы прокси:</b>
🔐 <b>MTProto</b> — нативный протокол Telegram. Поддерживает Fake-TLS (маскировка под обычный HTTPS). Лучший выбор для России.
🧦 <b>SOCKS5</b> — универсальный прокси. Работает там, где MTProto блокируется.

<b>🔒 Probe Resistant</b> — прокси, которые маскируются под легитимные сайты и выдерживают активные проверки DPI-оборудования.
""".strip()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        WELCOME_TEXT,
        parse_mode="HTML",
        reply_markup=main_menu_kb(),
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")
