"""
Database — хранение проверенных прокси и настроек пользователей.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

from services.fetcher import ProxyEntry

logger = logging.getLogger(__name__)


class Database:
    """SQLite хранилище прокси и настроек пользователей."""

    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._init_db()

    # ── Инициализация ────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS proxies (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    type        TEXT NOT NULL,
                    host        TEXT NOT NULL,
                    port        INTEGER NOT NULL,
                    secret      TEXT,
                    username    TEXT,
                    password    TEXT,
                    region      TEXT DEFAULT 'all',
                    domain      TEXT,
                    probe_resistant INTEGER DEFAULT 0,
                    ping_ms     INTEGER,
                    raw_link    TEXT NOT NULL UNIQUE,
                    fetched_at  REAL,
                    updated_at  REAL
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id         INTEGER PRIMARY KEY,
                    region          TEXT DEFAULT 'all',
                    proxy_type      TEXT DEFAULT 'mtproto',
                    auto_notify     INTEGER DEFAULT 1,
                    current_proxy   TEXT,
                    updated_at      REAL
                );

                CREATE TABLE IF NOT EXISTS subscribers (
                    user_id     INTEGER PRIMARY KEY,
                    username    TEXT,
                    added_at    REAL
                );

                CREATE INDEX IF NOT EXISTS idx_proxies_region
                    ON proxies(region);
                CREATE INDEX IF NOT EXISTS idx_proxies_type
                    ON proxies(type);
                CREATE INDEX IF NOT EXISTS idx_proxies_ping
                    ON proxies(ping_ms);
            """)
        logger.info("База данных инициализирована: %s", self._path)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Прокси ───────────────────────────────────────────────────────────────

    def save_proxies(self, proxies: List[ProxyEntry]) -> int:
        """Сохраняет / обновляет прокси. Возвращает количество добавленных."""
        now = time.time()
        added = 0
        with self._conn() as conn:
            for p in proxies:
                cur = conn.execute(
                    """
                    INSERT INTO proxies
                        (type, host, port, secret, username, password, region,
                         domain, probe_resistant, ping_ms, raw_link, fetched_at, updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(raw_link) DO UPDATE SET
                        ping_ms         = excluded.ping_ms,
                        probe_resistant = excluded.probe_resistant,
                        region          = excluded.region,
                        domain          = excluded.domain,
                        updated_at      = excluded.updated_at
                    """,
                    (
                        p.type, p.host, p.port, p.secret,
                        p.username, p.password,
                        p.region, p.domain,
                        1 if p.probe_resistant else 0,
                        p.ping_ms, p.raw_link,
                        p.fetched_at, now,
                    ),
                )
                if cur.lastrowid and cur.rowcount == 1:
                    added += 1
        logger.debug("Сохранено прокси: %d новых из %d", added, len(proxies))
        return added

    def get_top_proxies(
        self,
        region: str = "all",
        proxy_type: str = "mtproto",
        limit: int = 10,
    ) -> List[ProxyEntry]:
        """Возвращает топ прокси по пингу."""
        query = """
            SELECT * FROM proxies
            WHERE ping_ms IS NOT NULL
        """
        params: list = []

        if proxy_type != "all":
            query += " AND type = ?"
            params.append(proxy_type)

        if region != "all":
            query += " AND (region = ? OR region = 'all')"
            params.append(region)

        query += " ORDER BY probe_resistant DESC, ping_ms ASC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def get_best_proxy(
        self,
        region: str = "all",
        proxy_type: str = "mtproto",
    ) -> Optional[ProxyEntry]:
        """Возвращает лучший прокси."""
        top = self.get_top_proxies(region, proxy_type, limit=1)
        return top[0] if top else None

    def count_proxies(self) -> dict:
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM proxies WHERE ping_ms IS NOT NULL"
            ).fetchone()[0]
            ru = conn.execute(
                "SELECT COUNT(*) FROM proxies WHERE region='ru' AND ping_ms IS NOT NULL"
            ).fetchone()[0]
            eu = conn.execute(
                "SELECT COUNT(*) FROM proxies WHERE region='eu' AND ping_ms IS NOT NULL"
            ).fetchone()[0]
            probe = conn.execute(
                "SELECT COUNT(*) FROM proxies WHERE probe_resistant=1 AND ping_ms IS NOT NULL"
            ).fetchone()[0]
        return {"total": total, "ru": ru, "eu": eu, "probe_resistant": probe}

    def clear_old_proxies(self, older_than_hours: int = 24) -> int:
        """Удаляет прокси старше N часов."""
        threshold = time.time() - older_than_hours * 3600
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM proxies WHERE updated_at < ? OR ping_ms IS NULL",
                (threshold,),
            )
        return cur.rowcount

    # ── Настройки пользователя ───────────────────────────────────────────────

    def get_user_settings(self, user_id: int) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row:
            return dict(row)
        return {
            "user_id": user_id,
            "region": "all",
            "proxy_type": "mtproto",
            "auto_notify": 1,
            "current_proxy": None,
        }

    def update_user_settings(self, user_id: int, **kwargs) -> None:
        settings = self.get_user_settings(user_id)
        settings.update(kwargs)
        settings["updated_at"] = time.time()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO user_settings
                    (user_id, region, proxy_type, auto_notify, current_proxy, updated_at)
                VALUES (:user_id, :region, :proxy_type, :auto_notify, :current_proxy, :updated_at)
                ON CONFLICT(user_id) DO UPDATE SET
                    region          = excluded.region,
                    proxy_type      = excluded.proxy_type,
                    auto_notify     = excluded.auto_notify,
                    current_proxy   = excluded.current_proxy,
                    updated_at      = excluded.updated_at
                """,
                settings,
            )

    # ── Подписчики ───────────────────────────────────────────────────────────

    def add_subscriber(self, user_id: int, username: Optional[str] = None) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO subscribers (user_id, username, added_at)
                VALUES (?, ?, ?)
                """,
                (user_id, username, time.time()),
            )

    def remove_subscriber(self, user_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM subscribers WHERE user_id = ?", (user_id,)
            )

    def get_all_subscribers(self) -> List[int]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT user_id FROM subscribers"
            ).fetchall()
        return [r["user_id"] for r in rows]

    def subscriber_count(self) -> int:
        with self._conn() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM subscribers"
            ).fetchone()[0]

    # ── Вспомогательные ──────────────────────────────────────────────────────

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> ProxyEntry:
        d = dict(row)
        return ProxyEntry(
            type=d["type"],
            host=d["host"],
            port=d["port"],
            secret=d.get("secret"),
            username=d.get("username"),
            password=d.get("password"),
            region=d.get("region", "all"),
            domain=d.get("domain"),
            probe_resistant=bool(d.get("probe_resistant", 0)),
            ping_ms=d.get("ping_ms"),
            raw_link=d.get("raw_link", ""),
            fetched_at=d.get("fetched_at", 0.0),
        )
