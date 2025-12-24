import os
from pathlib import Path
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify, g
)
from flask_sqlalchemy import SQLAlchemy
import model
import json
import random
import logging
import sqlite3
# ------------------------------------------------------------------
# Инициализация приложения и БД
# ------------------------------------------------------------------
#BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = Path(__file__).parent.resolve()
app = Flask(__name__)
app.secret_key = 'super_secret_key'
DB_PATH = BASE_DIR.joinpath("app.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH.absolute()}'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///C:/Users/uzver/Desktop/VSOSH/kod/fish_chat/appd.db'
#app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "app.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print(app.config['SQLALCHEMY_DATABASE_URI'])

db = SQLAlchemy(app)
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
# ------------------------------------------------------------------
# Модель: сообщение + правильный ответ + комментарии
# ------------------------------------------------------------------
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    correct     = db.Column(db.Boolean, nullable=False)
    price_correct = db.Column(db.Float, default=0.0) 
    price_wrong   = db.Column(db.Float, default=0.0)

    comment_yes = db.Column(db.Text, nullable=True)
    comment_no  = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Message {self.id}>'

# ------------------------------------------------------------------
# Создаём таблицы (первый запуск)
# ------------------------------------------------------------------
with app.app_context():
    db.create_all()


# ------------------------------------------------------------------
# Главная страница
# ------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

# ------------------------------------------------------------------
# Памятка
# ------------------------------------------------------------------
@app.route('/memo')
def memo():
    return render_template('memo.html')
# ------------------------------------------------------------------
# Проверка сообщений
# ------------------------------------------------------------------
@app.route('/check_preview')
def check_preview():
    return render_template('check_preview.html')

@app.route('/check')
def check():
    return render_template('check.html')

@app.route('/check_massege', methods=['POST'])
def check_massege():
    # Получаем данные из формы
    msg = request.form.get('msg')
    
    if not msg:
        return jsonify({'error': 'Message is required'}), 400
    
    try:
        # Получаем ответ от модели
        resp_json = model.check_message(msg)
        
        # Проверяем, что ответ не пустой
        if not resp_json:
            return jsonify({'error': 'Empty response from model'}), 500
        
        # Парсим JSON с обработкой ошибок
        try:
            data = json.loads(resp_json)
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON response from model'}), 500
        
        # Проверяем наличие необходимых полей
        required_fields = ['text', 'status', 'certainty', 'comment']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields in response'}), 500
        
        # Извлекаем данные
        text = data['text']
        status = data['status']
        certainty = data['certainty']
        comment = data['comment']
        
        # Возвращаем шаблон
        return render_template('check_result.html',
                              text=text,
                              status=status,
                              certainty=certainty,
                              comment=comment)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500
# ------------------------------------------------------------------------
# Тренировка
# ------------------------------------------------------------------------
@app.route('/train_preview')
def train_preview():
    return render_template('train_preview.html')
@app.route('/train/<int:step>', methods=['GET', 'POST'])
def train(step):
    # Получаем все сообщения один раз
    print(f"DEBUG: Entering train(step={step})")
    print(f"DEBUG: Session before: {dict(session)}")
    all_messages = Message.query.all()
    if not all_messages:
        flash('Нет сообщений в базе. Добавьте их через /admin')
        return redirect(url_for('index'))
    
    # Инициализируем или получаем перемешанные ID
    if 'shuffled_ids' not in session or step == 0:
        # При step == 0 сбрасываем сессию
        if step == 0 and request.method == "GET":
            session.clear()  # Очищаем всю сессию для новой тренировки
            session['experience'] = 0
            session['answers'] = {}
            session['answered_current'] = False  # Флаг, что на текущий вопрос ответили
        
        # Создаем новый перемешанный список
        shuffled_ids = [m.id for m in all_messages]
        random.shuffle(shuffled_ids)
        session['shuffled_ids'] = shuffled_ids
    
    # Получаем сообщения в нужном порядке
    messages = [Message.query.get(mid) for mid in session['shuffled_ids']]
    total_messages = len(messages)
    
    # Проверяем, что запрашиваемый шаг существует
    if step >= total_messages:
        # Показываем результаты, если вышли за пределы
        correct_count = sum(
            1 for m in messages
            if session.get('answers', {}).get(str(m.id)) == ('yes' if m.correct else 'no')
        )
        return render_template(
            'results.html',
            experience=session.get('experience', 0),
            total=total_messages,
            correct_count=correct_count
        )
    
    # Инициализируем опыт, если его ещё нет
    session.setdefault('experience', 0)
    session.setdefault('answers', {})
    session.setdefault('answered_current', False)
    
    current_msg = messages[step]
    
    if request.method == 'POST':
        answer = request.form.get('answer')
        action = request.form.get('action', '')
        
        # Если нажали кнопку "дальше" (из состояния с ответом)
        if action == 'next':
            print(f"DEBUG: Next button pressed, current experience: {session.get('experience')}")
            # Сбрасываем флаг ответа для следующего вопроса
            session['answered_current'] = False
            session.pop('current_answer', None)
            session.pop('current_explanation', None)
            session.pop('current_exp_change', None)
            session.pop('current_is_correct', None)
            
            # Переходим к следующему шагу
            next_step = step + 1
            print(f"DEBUG: Redirecting to step {next_step}, experience: {session.get('experience')}")
            
            # Проверяем, не закончились ли сообщения
            if next_step >= total_messages:
                return redirect(url_for('show_results'))
            
            return redirect(url_for('train', step=next_step))
        
        # Если нажали "завершить" из любого состояния
        if answer == 'finish':
            # Подсчитываем правильные ответы
            answers = session.get('answers', {})
            correct_count = sum(
                1 for m in messages
                if answers.get(str(m.id)) == ('yes' if m.correct else 'no')
            )
            return render_template(
                'results.html',
                experience=session.get('experience', 0),
                total=total_messages,
                correct_count=correct_count,
                step=step
            )
        if action == 'finish':
            answers = session.get('answers', {})
            correct_count = sum(
                1 for m in messages
                if answers.get(str(m.id)) == ('yes' if m.correct else 'no')
            )
            return render_template(
                'results.html',
                experience=session.get('experience', 0),
                total=total_messages,
                correct_count=correct_count,
                step=step+1
            )
        
        # Если пользователь выбрал ответ (yes/no) И еще не отвечал на текущий вопрос
        if answer in ['yes', 'no'] and not session.get('answered_current', False):
            # Проверяем ответ
            is_correct = (answer == 'yes') == current_msg.correct
            
            # Определяем прирост опыта
            delta_exp = current_msg.price_correct if is_correct else current_msg.price_wrong
            
            # Обновляем опыт
            session['experience'] = float(session.get('experience', 0)) + float(delta_exp)
            
            # Сохраняем ответ
            answers = session.get('answers', {})
            answers[str(current_msg.id)] = answer
            session['answers'] = answers
            
            # Сохраняем объяснение для показа на этой же странице
            session['current_answer'] = answer
            session['current_explanation'] = current_msg.comment_yes if is_correct else current_msg.comment_no
            session['current_exp_change'] = delta_exp
            session['current_is_correct'] = is_correct
            session['answered_current'] = True  # Отмечаем, что на этот вопрос ответили
    
    # GET-запрос: отображаем текущий вопрос
    current_answer = session.get('current_answer')
    current_explanation = session.get('current_explanation')
    current_exp_change = session.get('current_exp_change', 0)
    current_is_correct = session.get('current_is_correct')
    
    # Определяем состояние страницы
    if session.get('answered_current', False):
        state = 'answered'
    else:
        state = 'question'
    
    return render_template(
        'train.html',
        message=current_msg,
        step=step,
        total=total_messages,
        explanation=current_explanation,
        experience=session.get('experience', 0),
        exp_change=current_exp_change,
        current_answer=current_answer,
        is_correct=current_is_correct,
        state=state  # 'question' или 'answered'
    )


@app.route('/results', methods=['GET'])
def results():
    # Получаем все сообщения
    all_messages = Message.query.all()
    messages = [Message.query.get(mid) for mid in session['shuffled_ids']]
    total = len(messages)
    
    # Подсчет правильных ответов
    correct_count = sum(
        1 for m in messages
        if session.get('answers', {}).get(str(m.id)) == ('yes' if m.correct else 'no')
    )
    
    return render_template(
        'results.html',
        experience=session.get('experience', 0),
        total=total,
        correct_count=correct_count
    )

# В app.py
@app.route('/reset_experience')
def reset_experience():
    session['experience'] = 0
    return redirect(url_for('index'))

if __name__ == '__main__':
    print("Регистрация маршрутов:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods} {rule.rule}")
    app.run(debug=True, host='0.0.0.0', port=5000)

