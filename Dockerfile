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

# Копируем необходимые файлы из корня
COPY model.py .
COPY requirements.txt .
COPY app.db .
COPY app.py .

# Копируем остальные директории
COPY static static
COPY templates templates

# Устанавливаем права доступа
RUN chmod -R 755 static templates

# Открываем порты
EXPOSE 5000

# Устанавливаем переменные окружения
ENV BASE_URL="http://192.168.3.8:1234/v1"
ENV API_KEY="lmstudio"
ENV MODEL_ID="openai/gpt-oss-20b"
ENV SQLALCHEMY_DATABASE_URI="sqlite:////app/data/app.db"

ENV FLASK_ENV=production
ENV FLASK_APP=app.py

# Добавляем зависимости

RUN pip install -r requirements.txt

# Команда запуска
CMD ["python", "app.py"]