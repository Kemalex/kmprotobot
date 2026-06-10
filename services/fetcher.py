"""
ProxyFetcher — загружает и парсит списки прокси из открытых источников.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

logger = logging.getLogger(__name__)

# Регулярки для извлечения прокси из разных форматов
_RE_MTPROTO_TG = re.compile(
    r"tg://proxy\?[^\s<>\"']+", re.IGNORECASE
)
_RE_SOCKS5_TG = re.compile(
    r"tg://socks\?[^\s<>\"']+", re.IGNORECASE
)
_RE_MTPROTO_TME = re.compile(
    r"https?://t\.me/proxy\?[^\s<>\"']+", re.IGNORECASE
)
_RE_SOCKS5_URL = re.compile(
    r"socks5://(?:[^\s@]+@)?([^\s/:]+):(\d+)", re.IGNORECASE
)


@dataclass
class ProxyEntry:
    """Одна запись прокси."""

    type: str            # "mtproto" | "socks5"
    host: str
    port: int
    secret: Optional[str] = None   # только для MTProto
    username: Optional[str] = None  # только для SOCKS5
    password: Optional[str] = None  # только для SOCKS5

    region: str = "all"            # "ru" | "eu" | "all"
    domain: Optional[str] = None   # домен-маска Fake-TLS
    probe_resistant: bool = False
    ping_ms: Optional[int] = None

    raw_link: str = ""             # исходная tg:// ссылка
    fetched_at: float = field(default_factory=time.time)

    # ── удобные свойства ────────────────────────────────────────────────────

    @property
    def tg_link(self) -> str:
        """Ссылка для открытия прокси в Telegram."""
        if self.raw_link:
            return self.raw_link
        if self.type == "mtproto":
            return (
                f"tg://proxy?server={self.host}&port={self.port}"
                + (f"&secret={self.secret}" if self.secret else "")
            )
        # socks5
        base = f"tg://socks?server={self.host}&port={self.port}"
        if self.username:
            base += f"&user={self.username}&pass={self.password or ''}"
        return base

    @property
    def display_name(self) -> str:
        region_icon = {"ru": "🇷🇺", "eu": "🇪🇺"}.get(self.region, "🌍")
        lock = "🔒" if self.probe_resistant else ""
        ping = f" {self.ping_ms}ms" if self.ping_ms else ""
        domain_part = f" ({self.domain})" if self.domain else ""
        return f"{region_icon}{lock} {self.host}:{self.port}{domain_part}{ping}"

    def __str__(self) -> str:
        return self.display_name


class ProxyFetcher:
    """Загружает и парсит прокси из источников kort0881."""

    HEADERS = {
        "User-Agent": "Mozilla/5.0 TelegramProxyBot/1.0",
        "Accept": "text/plain, application/json",
    }

    def __init__(self, sources: dict, timeout: int = 15):
        self._sources = sources
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    # ── Публичный API ────────────────────────────────────────────────────────

    async def fetch_all(
        self,
        region: str = "all",
        proxy_type: str = "mtproto",
    ) -> List[ProxyEntry]:
        """
        Загружает список прокси.

        :param region: "ru" | "eu" | "all"
        :param proxy_type: "mtproto" | "socks5" | "all"
        """
        proxies: List[ProxyEntry] = []

        # Сначала пробуем взять верифицированный JSON (максимум информации)
        json_proxies = await self._fetch_json()
        if json_proxies:
            proxies.extend(json_proxies)
            logger.info("JSON-источник: получено %d прокси", len(json_proxies))
        else:
            # Фоллбек: текстовые списки
            txt_proxies = await self._fetch_txt_sources(region, proxy_type)
            proxies.extend(txt_proxies)
            logger.info("TXT-источники: получено %d прокси", len(txt_proxies))

        # Применяем фильтр по региону и типу
        result = self._filter(proxies, region, proxy_type)
        logger.info(
            "После фильтрации (region=%s, type=%s): %d прокси",
            region, proxy_type, len(result),
        )
        return result

    # ── Приватные методы ─────────────────────────────────────────────────────

    async def _fetch_json(self) -> List[ProxyEntry]:
        url = self._sources.get("json_verified")
        if not url:
            return []
        try:
            async with aiohttp.ClientSession(headers=self.HEADERS) as session:
                async with session.get(url, timeout=self._timeout) as resp:
                    if resp.status != 200:
                        return []
                    data = await resp.json(content_type=None)
        except Exception as exc:
            logger.warning("Не удалось загрузить JSON: %s", exc)
            return []

        entries = []
        items = data if isinstance(data, list) else data.get("proxies", [])
        for item in items:
            try:
                entry = self._parse_json_item(item)
                if entry:
                    entries.append(entry)
            except Exception:
                pass
        return entries

    async def _fetch_txt_sources(
        self, region: str, proxy_type: str
    ) -> List[ProxyEntry]:
        urls = []
        if proxy_type in ("mtproto", "all"):
            if region in ("ru", "all"):
                urls.append(("mtproto", "ru", self._sources["mtproto_ru"]))
            if region in ("eu", "all"):
                urls.append(("mtproto", "eu", self._sources["mtproto_eu"]))
            if region == "all":
                urls.append(("mtproto", "all", self._sources["mtproto_all"]))
        if proxy_type in ("socks5", "all"):
            urls.append(("socks5", "all", self._sources["socks5"]))

        # Дедупликация URL
        seen_urls: set = set()
        unique_urls = []
        for item in urls:
            if item[2] not in seen_urls:
                seen_urls.add(item[2])
                unique_urls.append(item)

        entries: List[ProxyEntry] = []
        async with aiohttp.ClientSession(headers=self.HEADERS) as session:
            for ptype, preg, url in unique_urls:
                try:
                    async with session.get(url, timeout=self._timeout) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                    parsed = self._parse_txt(text, ptype, preg)
                    entries.extend(parsed)
                    logger.debug("URL %s → %d прокси", url, len(parsed))
                except Exception as exc:
                    logger.warning("Ошибка загрузки %s: %s", url, exc)

        return entries

    # ── Парсеры ──────────────────────────────────────────────────────────────

    def _parse_json_item(self, item: dict) -> Optional[ProxyEntry]:
        ptype = item.get("type", "mtproto").lower()
        host = item.get("host") or item.get("server")
        port = item.get("port")
        if not host or not port:
            return None

        # Строим raw_link
        raw = item.get("link", "")
        if not raw:
            if ptype == "mtproto":
                secret = item.get("secret", "")
                raw = f"tg://proxy?server={host}&port={port}&secret={secret}"
            else:
                raw = f"tg://socks?server={host}&port={port}"

        return ProxyEntry(
            type=ptype,
            host=host,
            port=int(port),
            secret=item.get("secret"),
            region=item.get("region", "all"),
            domain=item.get("domain"),
            probe_resistant=bool(item.get("probe_resistant", False)),
            ping_ms=item.get("ping"),
            raw_link=raw,
        )

    def _parse_txt(
        self, text: str, ptype: str, region: str
    ) -> List[ProxyEntry]:
        entries: List[ProxyEntry] = []
        seen: set = set()

        def _add(raw_link: str, entry_type: str, entry_region: str) -> None:
            key = raw_link.lower()
            if key in seen:
                return
            seen.add(key)
            entry = self._link_to_entry(raw_link, entry_type, entry_region)
            if entry:
                entries.append(entry)

        for link in _RE_MTPROTO_TG.findall(text):
            _add(link, "mtproto", region)
        for link in _RE_MTPROTO_TME.findall(text):
            tg_link = link.replace("https://t.me/proxy?", "tg://proxy?")
            _add(tg_link, "mtproto", region)
        if ptype in ("socks5", "all"):
            for link in _RE_SOCKS5_TG.findall(text):
                _add(link, "socks5", region)

        return entries

    def _link_to_entry(
        self, raw: str, ptype: str, region: str
    ) -> Optional[ProxyEntry]:
        try:
            parsed = urlparse(raw)
            qs = parse_qs(parsed.query)

            def _q(key: str) -> Optional[str]:
                vals = qs.get(key)
                return vals[0] if vals else None

            host = _q("server") or _q("host")
            port_str = _q("port")
            if not host or not port_str:
                return None

            secret = _q("secret")
            # Определяем регион по домену из секрета Fake-TLS
            detected_region = region
            domain = None
            if secret and secret.startswith("ee"):
                domain = self._extract_domain(secret)
                if domain:
                    detected_region = self._classify_region(domain)

            return ProxyEntry(
                type=ptype,
                host=host,
                port=int(port_str),
                secret=secret,
                region=detected_region,
                domain=domain,
                raw_link=raw,
            )
        except Exception:
            return None

    @staticmethod
    def _extract_domain(secret: str) -> Optional[str]:
        """Извлекает домен-маску из Fake-TLS секрета (ee...)."""
        try:
            # Убираем префикс ee и декодируем hex → bytes → domain
            hex_part = secret[2:]  # убрать 'ee'
            # Первые 16 байт — случайный ключ, далее идёт домен как строка
            raw_bytes = bytes.fromhex(hex_part)
            # Домен — последовательность печатных ASCII байт в конце
            domain_bytes = bytearray()
            for b in reversed(raw_bytes):
                if 32 <= b < 127:
                    domain_bytes.append(b)
                else:
                    break
            if domain_bytes:
                candidate = domain_bytes[::-1].decode("ascii", errors="ignore")
                if "." in candidate and len(candidate) > 3:
                    return candidate
        except Exception:
            pass
        return None

    _RU_KEYWORDS = {
        "yandex", "vk.com", "mail.ru", "ok.ru", "sber", "tinkoff",
        "gosuslugi", "ozon", "wildberries", "avito", "kinopoisk",
        "mos.ru", "2gis", "rutube", "rbc",
    }
    _EU_KEYWORDS = {
        "google", "amazon", "microsoft", "cloudflare", "apple",
        "github", "twitter", "facebook", "instagram", "netflix",
    }

    def _classify_region(self, domain: str) -> str:
        d = domain.lower()
        if any(kw in d for kw in self._RU_KEYWORDS):
            return "ru"
        if any(kw in d for kw in self._EU_KEYWORDS):
            return "eu"
        return "all"

    @staticmethod
    def _filter(
        proxies: List[ProxyEntry], region: str, proxy_type: str
    ) -> List[ProxyEntry]:
        result = []
        for p in proxies:
            if proxy_type not in ("all", p.type):
                continue
            if region != "all" and p.region not in ("all", region):
                continue
            result.append(p)
        return result
