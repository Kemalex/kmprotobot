"""
Клавиатуры для бота.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from typing import List
from services.fetcher import ProxyEntry


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🔄 Получить прокси"),
                KeyboardButton(text="⚙️ Настройки"),
            ],
            [
                KeyboardButton(text="📋 Список топ-10"),
                KeyboardButton(text="ℹ️ Статистика"),
            ],
            [
                KeyboardButton(text="🔔 Подписка"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие...",
    )


def proxy_list_kb(proxies: List[ProxyEntry]) -> InlineKeyboardMarkup:
    """Инлайн-кнопки для списка прокси — каждый открывается в Telegram."""
    buttons = []
    for i, p in enumerate(proxies, 1):
        label = f"{i}. {p.display_name}"
        buttons.append([
            InlineKeyboardButton(text=label[:60], url=p.tg_link)
        ])
    buttons.append([
        InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def single_proxy_kb(proxy: ProxyEntry) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔗 Подключить в Telegram",
                url=proxy.tg_link,
            )
        ],
        [
            InlineKeyboardButton(text="🔄 Следующий", callback_data="next_proxy"),
            InlineKeyboardButton(text="📋 Показать все", callback_data="show_top"),
        ],
    ])


def settings_kb(current: dict) -> InlineKeyboardMarkup:
    region = current.get("region", "all")
    ptype = current.get("proxy_type", "mtproto")
    notify = bool(current.get("auto_notify", 1))

    region_labels = {
        "ru": "🇷🇺 Россия",
        "eu": "🇪🇺 Европа",
        "all": "🌍 Все регионы",
    }
    type_labels = {
        "mtproto": "🔐 MTProto",
        "socks5": "🧦 SOCKS5",
    }

    def _check(val: str, current_val: str) -> str:
        return "✅ " if val == current_val else ""

    buttons = [
        # Регион
        [InlineKeyboardButton(text="— Регион —", callback_data="noop")],
        [
            InlineKeyboardButton(
                text=f"{_check('ru', region)}{region_labels['ru']}",
                callback_data="set_region_ru",
            ),
            InlineKeyboardButton(
                text=f"{_check('eu', region)}{region_labels['eu']}",
                callback_data="set_region_eu",
            ),
            InlineKeyboardButton(
                text=f"{_check('all', region)}{region_labels['all']}",
                callback_data="set_region_all",
            ),
        ],
        # Тип
        [InlineKeyboardButton(text="— Тип прокси —", callback_data="noop")],
        [
            InlineKeyboardButton(
                text=f"{_check('mtproto', ptype)}{type_labels['mtproto']}",
                callback_data="set_type_mtproto",
            ),
            InlineKeyboardButton(
                text=f"{_check('socks5', ptype)}{type_labels['socks5']}",
                callback_data="set_type_socks5",
            ),
        ],
        # Уведомления
        [InlineKeyboardButton(text="— Уведомления —", callback_data="noop")],
        [
            InlineKeyboardButton(
                text=f"{'🔔' if notify else '🔕'} Автоуведомления: {'Вкл' if notify else 'Выкл'}",
                callback_data="toggle_notify",
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscribe_kb(is_subscribed: bool) -> InlineKeyboardMarkup:
    if is_subscribed:
        btn = InlineKeyboardButton(
            text="🔕 Отписаться от обновлений",
            callback_data="unsubscribe",
        )
    else:
        btn = InlineKeyboardButton(
            text="🔔 Подписаться на обновления",
            callback_data="subscribe",
        )
    return InlineKeyboardMarkup(inline_keyboard=[[btn]])
