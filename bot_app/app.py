# bot_app/app.py - ИСПРАВЛЕННАЯ ВЕРСИЯ

import os
from flask import Flask, jsonify, request  # ИЗМЕНИЛИ ИМПОРТ
import requests

# СОЗДАЁМ Flask приложение
app = Flask(__name__)  # ← ЭТО ВАЖНАЯ СТРОКА!

@app.route('/')
def index():
    return jsonify({
        "service": "bot_app", 
        "endpoints": ["/", "/status", "/api/assistant"],
        "message": "Это второе приложение доступно по /bot"
    })

@app.route('/status')
def status():
    return jsonify({"service": "bot", "status": "ok"})

@app.route('/api/assistant', methods=['POST'])
def assistant():
    """
    Универсальный ассистент для консоли
    Отвечает на любые вопросы, зная контекст (консоль, нет интернета)
    """
    data = request.get_json()
    
    if not data or 'message' not in data:
        return jsonify({'error': 'No message provided'}), 400
    
    user_message = data['message']
    history = data.get('history', [])
    
    # Системный промпт
    system_prompt = """Ты — универсальный ассистент, отвечающий пользователю в КОНСОЛЬНОМ интерфейсе.

ВАЖНЫЙ КОНТЕКСТ:
1. Пользователь общается с тобой через ТЕКСТОВУЮ КОНСОЛЬ
2. У пользователя НЕТ доступа к интернету
3. Не предлагай "нажать кнопку", "выбрать вариант", "перейти по ссылке"
4. Давай полные, самодостаточные ответы
5. Форматируй ответ для чтения в консоли"""

    messages = [{"role": "system", "content": system_prompt}]
    
    for msg in history[-6:]:
        messages.append(msg)
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        # Используем BASE_URL из переменных окружения или значение по умолчанию
        base_url = os.getenv('BASE_URL', 'http://host.docker.internal:1234/v1')
        model_id = os.getenv("MODEL_ID", "openai/gpt-oss-20b")
        api_key = os.getenv("API_KEY", "lmstudio")
        
        response = requests.post(
            f"{base_url}/chat/completions",
            json={
                "model": model_id,
                "messages": messages,
                "max_tokens": 1500,
                "temperature": 0.8
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=45
        )
        
        if response.status_code == 200:
            result = response.json()['choices'][0]['message']['content']
            
            cleaned_result = result.replace("в веб-интерфейсе", "в консоли")
            cleaned_result = cleaned_result.replace("на сайте", "здесь")
            cleaned_result = cleaned_result.replace("по ссылке", "ниже")
            
            return jsonify({
                'success': True,
                'response': cleaned_result,
                'tokens': response.json().get('usage', {})
            })
        else:
            return jsonify({
                'error': 'Model error', 
                'details': response.text[:200],
                'status': response.status_code
            }), 500
            
    except Exception as e:
        return jsonify({'error': str(e), 'type': 'connection'}), 500

# ВАЖНО: Добавляем запуск приложения
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)