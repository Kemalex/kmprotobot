"""
Обработчики команд прокси: /proxy, /top, /stats, /subscribe, /settings.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from services.database import Database
from services.fetcher import ProxyEntry
from utils.keyboards import (
    main_menu_kb,
    proxy_list_kb,
    single_proxy_kb,
    settings_kb,
    subscribe_kb,
)

logger = logging.getLogger(__name__)
router = Router(name="proxy")

_db = Database(settings.DB_PATH)

# ── /proxy ────────────────────────────────────────────────────────────────────


@router.message(Command("proxy"))
@router.message(F.text == "🔄 Получить прокси")
async def cmd_proxy(message: Message) -> None:
    user_settings = _db.get_user_settings(message.from_user.id)
    region = user_settings.get("region", "all")
    ptype = user_settings.get("proxy_type", "mtproto")

    proxy = _db.get_best_proxy(region=region, proxy_type=ptype)
    if not proxy:
        await message.answer(
            "⚠️ Нет проверенных прокси в базе.\n"
            "Попробуй через минуту — идёт первичная загрузка.",
            reply_markup=main_menu_kb(),
        )
        return

    await _send_proxy_card(message, proxy)


async def _send_proxy_card(message: Message, proxy: ProxyEntry) -> None:
    region_icons = {"ru": "🇷🇺", "eu": "🇪🇺", "all": "🌍"}
    ptype_names = {"mtproto": "MTProto 🔐", "socks5": "SOCKS5 🧦"}

    lines = [
        f"{region_icons.get(proxy.region, '🌍')} <b>Прокси найден!</b>",
        "",
        f"🖥 <b>Сервер:</b> <code>{proxy.host}</code>",
        f"🔌 <b>Порт:</b> <code>{proxy.port}</code>",
        f"📡 <b>Тип:</b> {ptype_names.get(proxy.type, proxy.type)}",
    ]
    if proxy.domain:
        lines.append(f"🎭 <b>Маскировка:</b> <code>{proxy.domain}</code>")
    if proxy.probe_resistant:
        lines.append("🔒 <b>Probe Resistant:</b> обходит DPI ✅")
    if proxy.ping_ms:
        lines.append(f"⚡️ <b>Пинг:</b> {proxy.ping_ms} мс")

    lines += [
        "",
        "👇 Нажми кнопку чтобы подключить в Telegram:",
    ]

    await message.answer(
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=single_proxy_kb(proxy),
    )


# ── /top ──────────────────────────────────────────────────────────────────────


@router.message(Command("top"))
@router.message(F.text == "📋 Список топ-10")
async def cmd_top(message: Message) -> None:
    user_settings = _db.get_user_settings(message.from_user.id)
    region = user_settings.get("region", "all")
    ptype = user_settings.get("proxy_type", "mtproto")

    proxies = _db.get_top_proxies(
        region=region,
        proxy_type=ptype,
        limit=10,
    )
    if not proxies:
        await message.answer(
            "⚠️ Нет прокси в базе. Подожди немного — идёт обновление."
        )
        return

    header = (
        f"📋 <b>Топ-{len(proxies)} прокси</b> "
        f"(регион: {region.upper()}, тип: {ptype})\n"
        "Нажми на любой чтобы подключить:\n"
    )
    await message.answer(
        header,
        parse_mode="HTML",
        reply_markup=proxy_list_kb(proxies),
    )


# ── /stats ────────────────────────────────────────────────────────────────────


@router.message(Command("stats"))
@router.message(F.text == "ℹ️ Статистика")
async def cmd_stats(message: Message) -> None:
    counts = _db.count_proxies()
    subs = _db.subscriber_count()

    text = (
        "📊 <b>Статистика базы прокси</b>\n\n"
        f"✅ Всего живых прокси: <b>{counts['total']}</b>\n"
        f"🇷🇺 RU (маскировка под RU-сайты): <b>{counts['ru']}</b>\n"
        f"🇪🇺 EU (Google, Amazon и др.): <b>{counts['eu']}</b>\n"
        f"🔒 Probe Resistant: <b>{counts['probe_resistant']}</b>\n\n"
        f"👥 Подписчиков: <b>{subs}</b>\n\n"
        f"🔄 Источник: <a href=\"https://kort0881.github.io/telegram-proxy-collector/\">"
        f"telegram-proxy-collector</a>\n"
        "⏱ Обновление каждый час автоматически."
    )
    await message.answer(
        text, parse_mode="HTML", disable_web_page_preview=True
    )


# ── /subscribe ────────────────────────────────────────────────────────────────


@router.message(Command("subscribe"))
@router.message(F.text == "🔔 Подписка")
async def cmd_subscribe(message: Message) -> None:
    user_id = message.from_user.id
    subs = _db.get_all_subscribers()
    is_sub = user_id in subs

    text = (
        "🔔 <b>Подписка на обновления</b>\n\n"
        "При обновлении базы прокси (каждый час) получишь уведомление "
        "с лучшим актуальным прокси."
        if not is_sub
        else "✅ Ты уже подписан. Получаешь уведомления при каждом обновлении."
    )
    await message.answer(
        text, parse_mode="HTML", reply_markup=subscribe_kb(is_sub)
    )


@router.callback_query(F.data == "subscribe")
async def cb_subscribe(query: CallbackQuery) -> None:
    _db.add_subscriber(
        query.from_user.id, query.from_user.username
    )
    await query.answer("✅ Подписка оформлена!")
    await query.message.edit_reply_markup(reply_markup=subscribe_kb(True))
    await query.message.edit_text(
        "✅ <b>Подписка оформлена!</b>\n\n"
        "Буду присылать лучший прокси при каждом обновлении базы.",
        parse_mode="HTML",
        reply_markup=subscribe_kb(True),
    )


@router.callback_query(F.data == "unsubscribe")
async def cb_unsubscribe(query: CallbackQuery) -> None:
    _db.remove_subscriber(query.from_user.id)
    await query.answer("🔕 Отписка оформлена")
    await query.message.edit_text(
        "🔕 <b>Ты отписан от обновлений.</b>\n\n"
        "Можно подписаться снова в любой момент через /subscribe",
        parse_mode="HTML",
        reply_markup=subscribe_kb(False),
    )


# ── /settings ────────────────────────────────────────────────────────────────


@router.message(Command("settings"))
@router.message(F.text == "⚙️ Настройки")
async def cmd_settings(message: Message) -> None:
    user_settings = _db.get_user_settings(message.from_user.id)
    await message.answer(
        "⚙️ <b>Настройки</b>\n\nВыбери регион и тип прокси:",
        parse_mode="HTML",
        reply_markup=settings_kb(user_settings),
    )


@router.callback_query(F.data.startswith("set_region_"))
async def cb_set_region(query: CallbackQuery) -> None:
    region = query.data.replace("set_region_", "")
    _db.update_user_settings(query.from_user.id, region=region)
    user_settings = _db.get_user_settings(query.from_user.id)
    await query.answer(f"Регион: {region.upper()}")
    await query.message.edit_reply_markup(reply_markup=settings_kb(user_settings))


@router.callback_query(F.data.startswith("set_type_"))
async def cb_set_type(query: CallbackQuery) -> None:
    ptype = query.data.replace("set_type_", "")
    _db.update_user_settings(query.from_user.id, proxy_type=ptype)
    user_settings = _db.get_user_settings(query.from_user.id)
    await query.answer(f"Тип: {ptype}")
    await query.message.edit_reply_markup(reply_markup=settings_kb(user_settings))


@router.callback_query(F.data == "toggle_notify")
async def cb_toggle_notify(query: CallbackQuery) -> None:
    user_settings = _db.get_user_settings(query.from_user.id)
    current = bool(user_settings.get("auto_notify", 1))
    _db.update_user_settings(query.from_user.id, auto_notify=0 if current else 1)
    user_settings = _db.get_user_settings(query.from_user.id)
    await query.answer("Настройка сохранена")
    await query.message.edit_reply_markup(reply_markup=settings_kb(user_settings))


# ── Callback: next proxy ──────────────────────────────────────────────────────


@router.callback_query(F.data == "next_proxy")
async def cb_next_proxy(query: CallbackQuery) -> None:
    user_settings = _db.get_user_settings(query.from_user.id)
    region = user_settings.get("region", "all")
    ptype = user_settings.get("proxy_type", "mtproto")

    proxies = _db.get_top_proxies(region=region, proxy_type=ptype, limit=5)
    if len(proxies) < 2:
        await query.answer("Больше прокси нет — нажми 🔄 Получить прокси")
        return

    # Берём второй в очереди (не тот что уже показан)
    proxy = proxies[1]
    await query.message.delete()
    await _send_proxy_card(query.message, proxy)
    await query.answer()


@router.callback_query(F.data == "show_top")
async def cb_show_top(query: CallbackQuery) -> None:
    user_settings = _db.get_user_settings(query.from_user.id)
    region = user_settings.get("region", "all")
    ptype = user_settings.get("proxy_type", "mtproto")

    proxies = _db.get_top_proxies(region=region, proxy_type=ptype, limit=10)
    if not proxies:
        await query.answer("Нет прокси в базе")
        return

    await query.message.answer(
        f"📋 <b>Топ-{len(proxies)} прокси</b>:",
        parse_mode="HTML",
        reply_markup=proxy_list_kb(proxies),
    )
    await query.answer()


@router.callback_query(F.data == "refresh_list")
async def cb_refresh_list(query: CallbackQuery) -> None:
    user_settings = _db.get_user_settings(query.from_user.id)
    region = user_settings.get("region", "all")
    ptype = user_settings.get("proxy_type", "mtproto")

    proxies = _db.get_top_proxies(region=region, proxy_type=ptype, limit=10)
    await query.message.edit_reply_markup(reply_markup=proxy_list_kb(proxies))
    await query.answer("✅ Список обновлён")


@router.callback_query(F.data == "noop")
async def cb_noop(query: CallbackQuery) -> None:
    await query.answer()
