# Этап 1: Сборка зависимостей
FROM python:3.13-slim AS web-deps
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

# Этап 2: Финальный образ с nginx
FROM python:3.13-slim
WORKDIR /app

# Устанавливаем nginx и зависимости
RUN apt-get update && apt-get install -y \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Обновляем pip
RUN python3 -m pip install --upgrade pip
RUN pip install --no-cache-dir gunicorn

# Копируем и устанавливаем колеса
COPY --from=web-deps /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl

# Копируем код приложения
COPY . .

# Устанавливаем права доступа
RUN chmod -R 755 static templates

# Копируем конфигурацию nginx
COPY nginx.conf /etc/nginx/nginx.conf

# Копируем entrypoint скрипт
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Открываем порт для nginx
EXPOSE 5000

# Устанавливаем переменные окружения
ENV API_KEY="lmstudio"
ENV MODEL_ID="openai/gpt-oss-20b"
ENV FLASK_ENV=production
ENV FLASK_APP=app.py

# Команда запуска
CMD ["/app/entrypoint.sh"]