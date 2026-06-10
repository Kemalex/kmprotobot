"""
ProxyScheduler — фоновая задача автоматического обновления прокси.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from config.settings import Settings
from services.fetcher import ProxyFetcher
from services.checker import ProxyChecker
from services.database import Database

logger = logging.getLogger(__name__)


class ProxyScheduler:
    """Периодически обновляет базу прокси и уведомляет подписчиков."""

    def __init__(self, bot: Bot, settings: Settings):
        self._bot = bot
        self._settings = settings
        self._db = Database(settings.DB_PATH)
        self._fetcher = ProxyFetcher(settings.PROXY_SOURCES)
        self._checker = ProxyChecker(timeout=settings.CHECK_TIMEOUT)
        self._task: Optional[asyncio.Task] = None
        self._last_run: Optional[float] = None
        self._running = False

    # ── Жизненный цикл ───────────────────────────────────────────────────────

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="proxy_scheduler")
        logger.info(
            "Планировщик запущен (интервал %d сек.)",
            self._settings.AUTO_UPDATE_INTERVAL,
        )

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Планировщик остановлен.")

    # ── Основной цикл ────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        # Первый запуск — сразу после старта
        await asyncio.sleep(10)
        while self._running:
            try:
                await self.run_update()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Ошибка в планировщике: %s", exc, exc_info=True)

            try:
                await asyncio.sleep(self._settings.AUTO_UPDATE_INTERVAL)
            except asyncio.CancelledError:
                break

    # ── Публичный метод обновления ────────────────────────────────────────────

    async def run_update(self) -> dict:
        """
        Принудительный запуск обновления.
        Возвращает словарь со статистикой.
        """
        logger.info("Начало обновления прокси...")
        t_start = time.monotonic()

        # 1. Загрузка
        raw = await self._fetcher.fetch_all(
            region=self._settings.DEFAULT_REGION,
            proxy_type=self._settings.DEFAULT_PROXY_TYPE,
        )

        # 2. Проверка
        alive = await self._checker.check_all(
            raw,
            max_count=self._settings.TOP_PROXIES_COUNT * 5,
        )

        # 3. Сохранение
        self._db.clear_old_proxies(older_than_hours=6)
        added = self._db.save_proxies(alive)

        elapsed = time.monotonic() - t_start
        self._last_run = time.time()

        stats = self._db.count_proxies()
        stats["fetched"] = len(raw)
        stats["alive"] = len(alive)
        stats["added"] = added
        stats["elapsed_sec"] = round(elapsed, 1)

        logger.info(
            "Обновление завершено за %.1f с: загружено=%d, живых=%d, "
            "добавлено=%d, всего в БД=%d",
            elapsed, len(raw), len(alive), added, stats["total"],
        )

        # 4. Уведомление подписчиков
        if self._settings.AUTO_NOTIFY_USERS and alive:
            best = self._db.get_best_proxy()
            if best:
                await self._notify_subscribers(best, stats)

        return stats

    @property
    def last_run(self) -> Optional[float]:
        return self._last_run

    # ── Уведомления ──────────────────────────────────────────────────────────

    async def _notify_subscribers(self, best_proxy, stats: dict) -> None:
        subscribers = self._db.get_all_subscribers()
        if not subscribers:
            return

        text = (
            "🔄 <b>Прокси обновлены!</b>\n\n"
            f"📊 Живых прокси: <b>{stats['alive']}</b>\n"
            f"🇷🇺 RU: {stats.get('ru', 0)}  🇪🇺 EU: {stats.get('eu', 0)}\n"
            f"🔒 Probe Resistant: {stats.get('probe_resistant', 0)}\n\n"
            f"⚡️ Лучший прокси:\n"
            f"<code>{best_proxy.display_name}</code>\n\n"
            f"Нажми кнопку чтобы подключить 👇"
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🔗 Подключить лучший прокси",
                url=best_proxy.tg_link,
            )
        ]])

        sent = 0
        failed = 0
        for uid in subscribers:
            try:
                await self._bot.send_message(
                    chat_id=uid, text=text, reply_markup=kb,
                    parse_mode="HTML",
                )
                sent += 1
                await asyncio.sleep(0.05)  # Throttle
            except (TelegramForbiddenError, TelegramBadRequest):
                # Пользователь заблокировал бота
                self._db.remove_subscriber(uid)
                failed += 1
            except Exception as exc:
                logger.warning("Не удалось отправить uid=%d: %s", uid, exc)
                failed += 1

        logger.info(
            "Уведомления: отправлено=%d, не удалось=%d", sent, failed
        )
