# Этап 1: Сборка зависимостей
FROM python:3.13-slim AS web-deps
WORKDIR /app
COPY requirements.txt .
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

# Этап 2: Финальный образ
FROM python:3.13-slim
WORKDIR /app

# Обновляем pip
RUN python3 -m pip install --upgrade pip

# Копируем и устанавливаем колеса
COPY --from=web-deps /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl

# Копируем код приложения
COPY . .

# Устанавливаем права доступа
RUN chmod -R 755 static templates

# Открываем порты
EXPOSE 5000
EXPOSE 1234

# Устанавливаем переменные окружения
ENV API_KEY="lmstudio"
ENV MODEL_ID="openai/gpt-oss-20b"

ENV FLASK_ENV=production
ENV FLASK_APP=app.py

# Добавляем зависимости
COPY requirements.txt .
RUN pip install -r requirements.txt

# Команда запуска
CMD ["python", "app.py"]