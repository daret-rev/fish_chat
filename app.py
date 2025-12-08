import os
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
import model
import inspect
import json
# ------------------------------------------------------------------
# Инициализация приложения и БД
# ------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = 'super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(BASE_DIR, "test.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------------------------------------------------------
# Модель: сообщение + правильный ответ + комментарии
# ------------------------------------------------------------------
class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)

    # --- новые поля ---
    correct     = db.Column(db.Boolean, nullable=False)
    price_correct = db.Column(db.Float, default=0.0) 
    price_wrong   = db.Column(db.Float, default=0.0)

    comment_yes = db.Column(db.Text, nullable=True)
    comment_no  = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Message {self.id}>'

def check_arg(func):
    sign = inspect.signature(func)

    def wrap(*args, **kwargs):
        try:
            bound = sign.bind_partial(*args, **kwargs)
        except:
            pass
    
    return wrap

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
@app.route('/train/<int:step>', methods=['GET', 'POST'])
def train(step):
    if step == 0:
        session.pop('answers', None)
        session['experience'] = 0
        session.pop('explanation', None)
        session.pop('exp_change', None)
    messages = Message.query.order_by(Message.id).all()
    if not messages:
        flash('Нет сообщений в базе. Добавьте их через /admin')
        return redirect(url_for('index'))

    # Инициализируем опыт, если его ещё нет
    session.setdefault('experience', 0)

    if request.method == 'POST':
        answer = request.form.get('answer')

        if answer == 'finish':
            correct_count = sum(
                1 for m in messages
                if session.get('answers', {}).get(str(m.id)) == ('yes' if m.correct else 'no')
            )
            exp_before_reset = session.get('experience', 0)
            return render_template(
                'results.html',
                experience=exp_before_reset,
                total=len(messages),
                correct_count=correct_count
            )
            
        current_msg = messages[step]
        is_correct = (answer == 'yes') == current_msg.correct

        # Определяем прирост опыта
        delta_exp = current_msg.price_correct if is_correct else current_msg.price_wrong

        # Обновляем опыт в сессии
        session['experience'] = session.get('experience', 0) + delta_exp

        # Сохраняем справку и переход к следующему шагу
        session['explanation'] = (
            current_msg.comment_yes if is_correct else current_msg.comment_no
        )
        answers = session.get('answers', {})
        answers[str(current_msg.id)] = answer
        session['answers'] = answers

        next_step = step + 1                       # ← вычисляем следующий шаг
        session['next_step'] = next_step
        session['exp_change'] = delta_exp          # чтобы показать изменение

        # **Новый код** – проверяем, достигли ли конца списка сообщений
        if next_step >= len(messages):
            correct_count = sum(1 for m in messages if session.get('answers', {}).get(str(m.id)) == ('yes' if m.correct else 'no'))
            return render_template(
                'results.html',
                experience=session.get('experience', 0),
                total=len(messages),
                correct_count=correct_count
            )

        return redirect(url_for('train', step=next_step)) 

    # При GET‑запросе читаем данные из сессии (если они есть)
    explanation   = session.pop('explanation', None)
    next_step     = session.pop('next_step', None)
    exp_change    = session.pop('exp_change', 0)

    return render_template(
        'train.html',
        message=messages[step],
        step=step,
        total=len(messages),
        explanation=explanation,
        next_step=next_step,
        experience=session.get('experience', 0),
        exp_change=exp_change
    )

# В app.py
@app.route('/reset_experience')
def reset_experience():
    session['experience'] = 0
    return redirect(url_for('index'))
# -----------------------------------------------------------------------
# Админка – защита паролем (простейший вариант)
# ------------------------------------------------------------------------
@app.route('/admin')
def admin():
    # Если пользователь не авторизован – показываем форму входа
    if not session.get('admin'):
        return redirect(url_for('login_admin'))   # будем использовать /admin/login для ввода пароля

    # Пользователь уже вошёл → отображаем меню
    return render_template('admin_menu.html')

@app.route('/admin/login', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        pwd = request.form.get('password')
        if pwd != 'admin':
            flash('Неверный пароль')
            return redirect(url_for('login_admin'))
        session['admin'] = True
        return redirect(url_for('admin'))

    # GET‑запрос – показываем форму ввода пароля
    return render_template('admin_login.html')


@app.route('/admin/add', methods=['GET', 'POST'])
def add_message():
    if not session.get('admin'):
        flash('Неавторизован')
        return redirect(url_for('admin'))

    if request.method == 'POST':
        text = request.form['text']
        correct = request.form['correct'] == 'yes'
        comment_yes = request.form['comment_yes']
        comment_no  = request.form['comment_no']
        price_correct = float(request.form.get('price_correct', 0))
        price_wrong   = float(request.form.get('price_wrong', 0))

        msg = Message(
            text=text,
            correct=correct,
            comment_yes=comment_yes,
            comment_no=comment_no,
            price_correct=price_correct,
            price_wrong=price_wrong
        )
        db.session.add(msg)
        db.session.commit()
        flash('Сообщение добавлено')
        return redirect(url_for('add_message'))

    return render_template('add.html')

# ------------------------------------------------------------------
# Админка – список всех сообщений + кнопки редактировать / удалить
# ------------------------------------------------------------------
@app.route('/admin/list')
def admin_list():
    if not session.get('admin'):
        flash('Неавторизован')
        return redirect(url_for('admin'))
    messages = Message.query.order_by(Message.id).all()
    return render_template('list.html', messages=messages)


# ------------------------------------------------------------------
# Редактирование конкретного сообщения
# ------------------------------------------------------------------
@app.route('/admin/edit/<int:msg_id>', methods=['GET', 'POST'])
def edit_message(msg_id):
    if not session.get('admin'):
        flash('Неавторизован')
        return redirect(url_for('admin'))

    msg = Message.query.get_or_404(msg_id)

    if request.method == 'POST':
        msg.text = request.form['text']
        msg.correct = request.form['correct'] == 'yes'
        msg.comment_yes = request.form['comment_yes']
        msg.comment_no  = request.form['comment_no']
        msg.price_correct = float(request.form.get('price_correct', 0))
        msg.price_wrong   = float(request.form.get('price_wrong', 0))
        db.session.commit()
        flash('Сообщение обновлено')
        return redirect(url_for('admin_list'))

    return render_template('edit.html', message=msg)


# ------------------------------------------------------------------
# Удалить сообщение
# ------------------------------------------------------------------
@app.route('/admin/delete/<int:msg_id>', methods=['POST'])
def delete_message(msg_id):
    if not session.get('admin'):
        flash('Неавторизован')
        return redirect(url_for('admin'))

    msg = Message.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash('Сообщение удалено')
    return redirect(url_for('admin_list'))

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('Вы вышли из админки')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)




