FROM python:3.11-slim

WORKDIR /app

# Зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Исходный код
COPY . .

# Том для базы данных и логов
VOLUME ["/app/data"]
ENV DB_PATH=/app/data/proxy_bot.db

CMD ["python", "bot.py"]
