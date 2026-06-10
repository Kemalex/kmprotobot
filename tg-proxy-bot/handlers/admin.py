"""
Административные команды: /update, /broadcast, /admin.
Доступны только пользователям из списка ADMIN_IDS.
"""

from __future__ import annotations

import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import settings
from services.database import Database
from services.scheduler import ProxyScheduler

logger = logging.getLogger(__name__)
router = Router(name="admin")

_db = Database(settings.DB_PATH)


def _is_admin(user_id: int) -> bool:
    return user_id in settings.ADMIN_IDS


# ── /admin ────────────────────────────────────────────────────────────────────


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    counts = _db.count_proxies()
    subs = _db.subscriber_count()
    text = (
        "🔧 <b>Панель администратора</b>\n\n"
        f"📦 Всего прокси: {counts['total']}\n"
        f"🇷🇺 RU: {counts['ru']}  🇪🇺 EU: {counts['eu']}\n"
        f"🔒 Probe Resistant: {counts['probe_resistant']}\n"
        f"👥 Подписчиков: {subs}\n\n"
        "<b>Команды:</b>\n"
        "/update — принудительное обновление базы\n"
        "/broadcast &lt;текст&gt; — рассылка всем подписчикам\n"
        "/cleardb — очистить устаревшие прокси\n"
    )
    await message.answer(text, parse_mode="HTML")


# ── /update ───────────────────────────────────────────────────────────────────


@router.message(Command("update"))
async def cmd_force_update(message: Message, scheduler: ProxyScheduler) -> None:
    if not _is_admin(message.from_user.id):
        return
    msg = await message.answer("🔄 Запускаю обновление базы прокси...")
    try:
        stats = await scheduler.run_update()
        await msg.edit_text(
            f"✅ <b>Обновление завершено!</b>\n\n"
            f"📥 Загружено: {stats['fetched']}\n"
            f"✅ Живых: {stats['alive']}\n"
            f"➕ Добавлено новых: {stats['added']}\n"
            f"📦 Всего в БД: {stats['total']}\n"
            f"⏱ Время: {stats['elapsed_sec']} сек.",
            parse_mode="HTML",
        )
    except Exception as exc:
        await msg.edit_text(f"❌ Ошибка: {exc}")
        logger.error("Force update error: %s", exc, exc_info=True)


# ── /broadcast ────────────────────────────────────────────────────────────────


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return

    text = message.text.removeprefix("/broadcast").strip()
    if not text:
        await message.answer("Использование: /broadcast <текст>")
        return

    subscribers = _db.get_all_subscribers()
    if not subscribers:
        await message.answer("Нет подписчиков.")
        return

    msg = await message.answer(f"📢 Рассылаю {len(subscribers)} подписчикам...")
    sent = 0
    for uid in subscribers:
        try:
            await message.bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            pass

    await msg.edit_text(f"✅ Рассылка завершена: {sent}/{len(subscribers)}")


# ── /cleardb ──────────────────────────────────────────────────────────────────


@router.message(Command("cleardb"))
async def cmd_cleardb(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    deleted = _db.clear_old_proxies(older_than_hours=1)
    await message.answer(f"🗑 Удалено устаревших прокси: {deleted}")
