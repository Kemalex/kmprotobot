"""
ProxyChecker — проверяет доступность прокси через TCP-соединение.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional, Tuple

from services.fetcher import ProxyEntry

logger = logging.getLogger(__name__)

# Telegram DC серверы для проверки подключения
TELEGRAM_DC_HOSTS = [
    ("149.154.167.51", 443),
    ("149.154.175.100", 443),
    ("91.108.4.1", 443),
]


class ProxyChecker:
    """Проверяет список прокси и сортирует по пингу."""

    def __init__(self, timeout: int = 8, max_concurrent: int = 30):
        self._timeout = timeout
        self._max_concurrent = max_concurrent

    async def check_all(
        self,
        proxies: List[ProxyEntry],
        max_count: Optional[int] = None,
    ) -> List[ProxyEntry]:
        """
        Проверяет прокси конкурентно.
        Возвращает только живые, отсортированные по пингу.
        """
        if not proxies:
            return []

        semaphore = asyncio.Semaphore(self._max_concurrent)

        async def _checked(p: ProxyEntry) -> Optional[ProxyEntry]:
            async with semaphore:
                return await self._check_one(p)

        tasks = [asyncio.create_task(_checked(p)) for p in proxies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        alive = [r for r in results if isinstance(r, ProxyEntry)]

        # Сортировка: probe_resistant > пинг
        alive.sort(
            key=lambda p: (
                0 if p.probe_resistant else 1,
                p.ping_ms if p.ping_ms else 9999,
            )
        )

        logger.info(
            "Проверено: %d, живых: %d", len(proxies), len(alive)
        )

        if max_count:
            alive = alive[:max_count]

        return alive

    async def _check_one(self, proxy: ProxyEntry) -> Optional[ProxyEntry]:
        """
        Проверяет один прокси по TCP на сам сервер прокси.
        Возвращает ProxyEntry с заполненным ping_ms или None.
        """
        ping = await self._tcp_ping(proxy.host, proxy.port)
        if ping is None:
            return None
        proxy.ping_ms = ping
        return proxy

    async def _tcp_ping(self, host: str, port: int) -> Optional[int]:
        """TCP-пинг до хоста:порта. Возвращает мс или None."""
        start = time.monotonic()
        try:
            conn = asyncio.open_connection(host, port)
            reader, writer = await asyncio.wait_for(conn, timeout=self._timeout)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return elapsed_ms
        except (OSError, asyncio.TimeoutError, ConnectionRefusedError):
            return None
        except Exception as exc:
            logger.debug("TCP ping %s:%d → %s", host, port, exc)
            return None

    async def check_single(self, proxy: ProxyEntry) -> Tuple[bool, Optional[int]]:
        """Проверяет один прокси. Возвращает (жив, пинг_мс)."""
        result = await self._check_one(proxy)
        if result:
            return True, result.ping_ms
        return False, None
