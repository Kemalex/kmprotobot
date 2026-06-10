# 🤖 Telegram Proxy Bot

Telegram-бот для автоматического поиска, проверки и смены MTProto/SOCKS5 прокси.

Источник прокси: [telegram-proxy-collector](https://kort0881.github.io/telegram-proxy-collector/) — обновляется ежечасно.

---

## ✨ Возможности

- **Автоматическое обновление** базы прокси каждый час
- **TCP-проверка** каждого прокси с измерением пинга
- **Приоритет** Probe Resistant прокси (обходят DPI/блокировки)
- **Фильтрация** по региону (🇷🇺 RU / 🇪🇺 EU) и типу (MTProto / SOCKS5)
- **Подписка** — уведомление при каждом обновлении с кнопкой подключения
- **Одно нажатие** — прокси открывается прямо в Telegram
- **Настройки** под каждого пользователя
- **Админ-панель** с ручным обновлением и рассылкой

---

## 🚀 Быстрый старт

### 1. Получить токен бота

1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Создай бота командой `/newbot`
3. Скопируй токен

### 2. Настроить конфигурацию

```bash
cp .env.example .env
nano .env
```

Заполни обязательные поля:
```
BOT_TOKEN=твой_токен
ADMIN_IDS=твой_telegram_id
```

Свой Telegram ID можно узнать у [@userinfobot](https://t.me/userinfobot).

### 3a. Запуск через Python

```bash
pip install -r requirements.txt
python bot.py
```

### 3b. Запуск через Docker (рекомендуется)

```bash
docker compose up -d
docker compose logs -f
```

---

## 📱 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Главное меню |
| `/proxy` | Лучший прокси прямо сейчас |
| `/top` | Топ-10 прокси по пингу |
| `/stats` | Статистика базы |
| `/subscribe` | Подписаться на обновления |
| `/settings` | Регион, тип прокси, уведомления |
| `/help` | Справка |

### Админ-команды

| Команда | Описание |
|---------|----------|
| `/admin` | Панель администратора |
| `/update` | Принудительное обновление базы |
| `/broadcast <текст>` | Рассылка всем подписчикам |
| `/cleardb` | Очистить устаревшие прокси |

---

## ⚙️ Конфигурация (.env)

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `BOT_TOKEN` | — | Токен бота (обязательно) |
| `ADMIN_IDS` | — | ID администраторов через запятую |
| `AUTO_UPDATE_INTERVAL` | `3600` | Интервал обновления (сек.) |
| `AUTO_NOTIFY_USERS` | `true` | Уведомлять подписчиков |
| `CHECK_TIMEOUT` | `8` | Таймаут TCP-проверки (сек.) |
| `MAX_PING_MS` | `3000` | Максимальный пинг (мс) |
| `TOP_PROXIES_COUNT` | `10` | Количество топ-прокси |
| `DEFAULT_REGION` | `all` | Регион: `ru` / `eu` / `all` |
| `DEFAULT_PROXY_TYPE` | `mtproto` | Тип: `mtproto` / `socks5` |
| `DB_PATH` | `proxy_bot.db` | Путь к SQLite-базе |

---

## 🏗 Структура проекта

```
tg-proxy-bot/
├── bot.py                  # Точка входа
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config/
│   └── settings.py         # Конфигурация из .env
├── services/
│   ├── fetcher.py          # Загрузка и парсинг прокси
│   ├── checker.py          # TCP-проверка прокси
│   ├── database.py         # SQLite хранилище
│   └── scheduler.py        # Фоновый планировщик
├── handlers/
│   ├── common.py           # /start, /help
│   ├── proxy.py            # /proxy, /top, /stats, /settings
│   └── admin.py            # /update, /broadcast
└── utils/
    └── keyboards.py        # Клавиатуры и кнопки
```

---

## 📦 Источники прокси

Все прокси берутся из репозитория [kort0881/telegram-proxy-collector](https://github.com/kort0881/telegram-proxy-collector):

- `proxy_ru.txt` — MTProto с маскировкой под RU-сайты (Яндекс, ВК, Госуслуги...)
- `proxy_eu.txt` — MTProto с международной маскировкой (Google, Amazon, Cloudflare...)
- `proxy_all.txt` — все MTProto прокси
- `socks5.txt` — SOCKS5 прокси
- `verified/proxy_all_verified.json` — полный JSON с пингом и probe_resistant

---

## 📄 Лицензия

MIT
