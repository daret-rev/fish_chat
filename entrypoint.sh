#!/bin/bash
set -e

echo "=== Starting Container ==="

# 1. Установка зависимостей для бота
echo "1. Installing bot dependencies..."
if [ -f "/app/bot_app/requirements.txt" ]; then
    cd /app/bot_app
    pip install -r requirements.txt
    echo "✓ Dependencies from requirements.txt installed"
else
    pip install flask requests
    echo "✓ Flask and requests installed"
fi

# 2. Запускаем Flask (основное приложение)
echo "2. Starting Flask application on port 8000..."
cd /app
gunicorn --bind 0.0.0.0:8000 --workers 2 app:app &
FLASK_PID=$!

# 3. Запускаем бот-приложение
echo "3. Starting bot application on port 3000..."
if [ -f "/app/bot_app/app.py" ]; then
    cd /app/bot_app
    # Устанавливаем переменные окружения для бота
    export BASE_URL=http://host.docker.internal:1234/v1
    export MODEL_ID=openai/gpt-oss-20b
    export API_KEY=lmstudio
    
    # Запускаем с логированием
    python app.py --host 0.0.0.0 --port 3000 > /var/log/bot.log 2>&1 &
    BOT_PID=$!
    echo "Bot started with PID: $BOT_PID"
else
    echo "Bot app not found, starting simple HTTP server..."
    echo '{"service": "bot", "status": "running"}' > /tmp/bot.json
    python3 -m http.server 3000 --directory /tmp > /var/log/simple_bot.log 2>&1 &
fi

# Ждём
echo "4. Waiting for services to start..."
sleep 7

# 5. Проверяем
echo "5. Checking services..."
if curl -s -f http://localhost:8000/ > /dev/null 2>&1; then
    echo "✓ Flask: OK (port 8000)"
else
    echo "✗ Flask: FAILED"
fi

if curl -s -f http://localhost:3000/ > /dev/null 2>&1; then
    echo "✓ Bot: OK (port 3000)"
else
    echo "✗ Bot: FAILED"
    echo "Bot logs:"
    tail -20 /var/log/bot.log 2>/dev/null || echo "No bot logs"
fi

# 6. Запускаем nginx
echo "6. Starting nginx..."
exec nginx -g "daemon off;"