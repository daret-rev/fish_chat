from pathlib import Path
from pyexpat.errors import messages
from unittest import case
from functools import wraps
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify,
    Response
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, UserMixin, LoginManager
from flask_sqlalchemy import SQLAlchemy
import json
import random
import logging
# ------------------------------------------------------------------
# Инициализация приложения, БД и менаджера авторизации
# ------------------------------------------------------------------
BASE_DIR = Path(__file__).parent.resolve()
app = Flask(__name__)
app.secret_key = 'super_secret_key'
DB_PATH = BASE_DIR.joinpath("app.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH.absolute()}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
print(app.config['SQLALCHEMY_DATABASE_URI'])

db = SQLAlchemy(app)
logging.basicConfig(level=logging.INFO)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

login_manager = LoginManager()
login_manager.init_app(app)
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
# Модель: пользователь + пароль + ID
# ------------------------------------------------------------------
class User(db.Model, UserMixin):
    __tablename__ = 'Users'

    id =  db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(64), nullable=False)

    privileges = db.Column(db.Integer, default = 0)

    def __repr__(self):
        return f'<User {self.username}>'

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    @property
    def is_admin(self):
        return self.privileges

    @property
    def role_name(self):
        roles = {
            0: 'user',
            1: 'teacher',
            2: 'admin'
        }
        return roles.get(self.privileges, 'unknown')

    @staticmethod
    def create_default_users():
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', privileges=1)
            admin.set_password('admin_admin')
            db.session.add(admin)

        db.session.commit()

    @staticmethod
    def create_user(username, password):

        user = User(username=username, privileges=0)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        return user

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

mgn = '/templateM/'
con = '/console_dir/'
# ------------------------------------------------------------------
# Группа/класс: пользователи + ID
# ------------------------------------------------------------------
class Group(db.Model):
    __tablename__ = 'Groups'

    id = db.Column(db.Integer, primary_key=True)

    groupname = db.Column(db.String(64), unique=True, nullable=False)
    users = db.Column(db.JSON, nullable=False)

    def __init__(self, groupname):
        self.groupname = groupname
        self.users = ""

    def __repr__(self):
        return f'<Group {self.groupname}>'

    def add_users(self, users: list):
        self.users = users

    def add_user(self, user_id):
        """Добавить пользователя в группу"""
        if self.users is None:
            self.users = ""

        if self.users:
            self.users += user_id
            return True
        return False

    def set_groupname(self, groupname):
        self.groupname = groupname

    def save(self):
        db.session.add(self)
        db.session.commit()
        print(f"Группа '{self.groupname}' создана с ID: {self.id}")

# ------------------------------------------------------------------
# Модель: урок + участники + задания
# ------------------------------------------------------------------
class Lesson(db.Model):
    __tablename__ = 'Lessons'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64), unique=True, nullable=False)
    time = db.Column(db.Integer, nullable=False)
    price_correct = db.Column(db.Integer, default=1)
    price_wrong = db.Column(db.Integer, default=-1)
    questions = db.Column(db.JSON, nullable=False)

    def __init__(self, name):
        self.name = name
        self.time = None

    def __repr__(self):
        return f'<Lesson {self.name}>'

    def set_count_questions(self, count_questions: int):
        self.count_questions = count_questions

    def set_time(self, time):
        self.time = time

    def add_questions(self,  questions_id: list[int] = None, rand=True):
        if questions_id is None:
            all_messages = Message.query.all()
            shuffled_ids = [m.id for m in all_messages]
            random.shuffle(shuffled_ids)
            questions_id = shuffled_ids[:self.count_questions]

        if rand:
            random.shuffle(questions_id)

        self.questions = questions_id

    def set_expirience(self, expirience_yes = 1, expirience_no = -1):
        self.price_correct = expirience_yes
        self.price_wrong = expirience_no

    def save(self):
        db.session.add(self)
        db.session.commit()
        print(f"Урок '{self.name}' создан с ID: {self.id}")

# ------------------------------------------------------------------
# Группа/класс: пользователи + ID
# ------------------------------------------------------------------
class Testing(db.Model):
    __tablename__ = 'Testings'

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.Boolean, nullable=False)
    lesson_id = db.Column(db.Integer, nullable=False)
    group_id = db.Column(db.JSON, nullable=False)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'<Testing {self.name}>'

    def set_status(self, status: bool):
        self.status = status

    def add_lesson(self, lesson: int):
        self.lesson_id = lesson

    def add_group(self, group: list[int]):
        self.group_id = group

    def save(self):
        db.session.add(self)
        db.session.commit()
        print(f"Тестирование '{self.name}' создан с ID: {self.id}")

# ------------------------------------------------------------------
# Модель: результаты тестирования
# ------------------------------------------------------------------
class Result(db.Model):
    __tablename__ = 'Results'
    id = db.Column(db.Integer, primary_key=True)
    testing_id = db.Column(db.Integer, nullable=False)
    lesson_id = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    score = db.Column(db.Integer, nullable=False)
    correct_answers_id = db.Column(db.JSON, nullable=False)
    wrong_answers_id = db.Column(db.JSON, nullable=False)

    def __repr__(self):
        return f'<Result {self.id}>'

    def __init__(self, testing_id, lesson_id, user_id, score, correct_answers_id, wrong_answers_id):
        self.testing_id = testing_id
        self.lesson_id = lesson_id
        self.user_id = user_id
        self.score = score
        self.correct_answers_id = correct_answers_id
        self.wrong_answers_id = wrong_answers_id


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
    username = session.get('curent_user')
    if not username:
        return render_template('index.html')
    else:
        user = User.query.filter(User.username == username).first()
        return render_template('index.html', user=user)

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
            username = session.get('curent_user')  # Сохраняем
            session.clear()  # Очищаем всю сессию для новой тренировки
            session['curent_user'] = username
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

# Очищение опыта после тренировки
@app.route('/reset_experience')
def reset_experience():
    session['experience'] = 0
    return redirect(url_for('index'))
# -----------------------------------------------------------
# Авторизация: создание пользователей и вход
# -----------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username')
    password = request.form.get('password')

    user = User.query.filter(
        User.username.ilike(username)
    ).first()

    if user and user.check_password(password):
        login_user(user)
        session['curent_user'] = user.username

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            match user.role_name:
                case 'admin':
                    redirect_url = '/cons'
                case 'teacher':
                    redirect_url = '/dashboard'
                case 'user':
                    redirect_url = '/'

            return jsonify({
                'success': True,
                'redirect': redirect_url
            })

        match user.role_name:
            case 'admin':
                return redirect(url_for('cons'))
            case 'teacher':
                return redirect(url_for('dashboard'))
            case 'user':
                return redirect(url_for('index'))
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Неверный логин или пароль'
            }), 401

        return render_template('login.html', error='Неверный логин или пароль')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('username')
    password = request.form.get('password')

    existing = User.query.filter(
        User.username.ilike(username)
    ).first()

    if existing:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': 'Пользователь уже существует'
            })
        return render_template('register.html', error='Пользователь уже существует')

    # Создаем пользователя
    user = User(username=username, privileges=0)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    user_id = user.id
    print(f"Создан пользователь: {username}, ID: {user_id}")

    # УДАЛЯЕМ старую группу и создаем новую
    Group.query.filter_by(groupname='new').delete()

    # Получаем ВСЕХ пользователей для группы
    all_user_ids = [u.id for u in User.query.filter(User.privileges == 0).all()]

    # Создаем новую группу со всеми пользователями
    group = Group('new')
    group.users = all_user_ids  # Все обычные пользователи
    db.session.add(group)
    db.session.commit()

    print(f"✅ Группа 'new' пересоздана с {len(all_user_ids)} пользователями")
    print(f"Список: {all_user_ids}")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'redirect': url_for('index')
        })

    return redirect(url_for('index'))

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session['curent_user'] = None
    return redirect(url_for('index'))
# ---------------------------------------------------------
# Панель управления
# ---------------------------------------------------------
@app.route('/ErAuth', methods=['GET'])
def ErAuth():
    # Логика для разных типов ошибок на будущее
    error_type = session.pop('error_type', 'access_denied')
    error_message = session.pop('error_message', None)

    return render_template(mgn + 'ErAuth.html',
                           error_type=error_type,
                           error_message=error_message)

def check_privileges():
    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()
    print("DEBUD: curent user-teacher is",curent_user)
    print("DEBUG: curent user-teacher privileges -",curent_user.is_admin)

    if not curent_user or not curent_user.is_admin:
        return False
    else:
        return True


def check_admin():
    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()
    print("DEBUD: curent user-admin is", curent_user)
    print("DEBUG: curent user-admin privileges -", curent_user.is_admin)

    if not curent_user or curent_user.role_name != 'admin':
        return False
    else:
        return True

def check_user_id(usr_id: int):
    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()
    print("DEBUD: curent user-teacher is", curent_user)
    print("DEBUG: curent user-teacher privileges -", curent_user.is_admin)

    if not curent_user or curent_user.id != usr_id:
        return False
    else:
        return True

@app.route('/dashboard')
def dashboard():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()

    return render_template(mgn + 'dashboard.html', user=curent_user)

@app.route('/dashboard/dashboard_instruction')
def dashboard_instruction():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    return render_template(mgn + 'dashboard_instruction.html')
# ---------------------------------------------------------
# Панель управления БД
# ---------------------------------------------------------
@app.route('/dashboard/DB_management', methods=['GET', 'POST'])
def DB_management():

    if not check_privileges():
        return redirect(url_for('ErAuth'))

    if request.method == 'GET':
        return render_template(mgn + 'DB_management.html')

@app.route('/dashboard/DB_management/DB_management_instruction')
def DB_management_instruction():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    if request.method == 'GET':
        return render_template(mgn + 'DB_management_instruction.html')

@app.route('/dashboard/DB_management/DB_msg_create', methods=['GET', 'POST'])
def DB_msg_create():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    if request.method == 'GET':
        return render_template(mgn + 'DB_msg_create.html')

    text = request.form['text']
    correct = request.form['correct'] == 'yes'
    comment_yes = request.form['comment_yes']
    comment_no = request.form['comment_no']
    price_correct = float(request.form.get('price_correct', 0))
    price_wrong = float(request.form.get('price_wrong', 0))

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
    return redirect(url_for('DB_msg_create'))

@app.route('/dashboard/DB_management/DB_msg_list')
def DB_msg_list():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    messages = Message.query.order_by(Message.id).all()
    return render_template(mgn + 'DB_msg_list.html', messages=messages)

@app.route('/dashboard/DB_msg_list/DB_msg_delete/<int:msg_id>', methods=['POST'])
def DB_msg_delete(msg_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    msg = Message.query.get_or_404(msg_id)
    db.session.delete(msg)
    db.session.commit()
    flash(f'Сообщение "{msg_id}" удалено')

    return redirect(url_for('dashboard/DB_msg_list'))

@app.route('/dashboard/DB_msg_edit/<int:msg_id>', methods=['GET', 'POST'])
def DB_msg_edit(msg_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    msg = Message.query.get_or_404(msg_id)

    if request.method == 'GET':
        return render_template(mgn + 'DB_msg_edit.html', message=msg)

    msg.text = request.form['text']
    msg.correct = request.form['correct'] == 'yes'
    msg.comment_yes = request.form['comment_yes']
    msg.comment_no = request.form['comment_no']
    msg.price_correct = float(request.form.get('price_correct', 0))
    msg.price_wrong = float(request.form.get('price_wrong', 0))
    db.session.commit()
    flash('Сообщение обновлено')
    return redirect(url_for('dashboard/DB_management/DB_msg_list'))

# ---------------------------------------------------------
# Панель управления Уроками
# ---------------------------------------------------------
@app.route('/dashboard/testing_management/lesson_create', methods=['GET', 'POST'])
def lesson_create():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    messages = Message.query.order_by(Message.id).all()
    lesson_names = [l.name for l in Lesson.query.order_by(Lesson.name).all()]
    if request.method == 'GET':
        return render_template(mgn + 'lesson_create.html', messages=messages, lesson_names=lesson_names)

    lesson_name = request.form.get('lesson_name')
    time = request.form.get('time', 0)
    price_correct = request.form.get('price_correct')
    price_wrong = request.form.get('price_wrong')
    msg_count = request.form.get('msg_count')
    selected_ids = request.form.get('selected_ids')

    lesson = Lesson(lesson_name)

    if time != '':
        lesson.set_time(time)
    else:
        lesson.set_time(0)
    lesson.set_expirience(price_correct, price_wrong)
    if selected_ids != '':
        selected_ids = [int(id) for id in selected_ids.split(',')]
        lesson.add_questions(selected_ids)
    else:
        lesson.set_count_questions(int(msg_count))
        lesson.add_questions()

    lesson.save()

    return redirect(url_for('testing_management'))

@app.route('/dashboard/testing_management/lesson_list')
def lesson_list():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    lessons = Lesson.query.order_by(Lesson.id).all()
    return render_template(mgn + 'lesson_list.html', lessons=lessons)

@app.route('/dashboard/lesson_list/lesson_edit/<int:less_id>', methods=['GET', 'POST'])
def lesson_edit(less_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    lesson = Lesson.query.get_or_404(less_id)
    messages = Message.query.order_by(Message.id).all()
    lesson_names = [l.name for l in Lesson.query.order_by(Lesson.name).all() if l.id != less_id]

    if request.method == 'GET':
        return render_template(mgn + 'lesson_edit.html', lesson=lesson, messages=messages, lesson_names=lesson_names)

    lesson.name = request.form.get('lesson_name')

    time = request.form.get('time')
    if time:
        lesson.time = time
    else:
        lesson.time = 0

    lesson.price_correct = request.form.get('price_correct')
    lesson.price_wrong = request.form.get('price_wrong')

    selected_ids_str = request.form.get('selected_ids')
    if selected_ids_str:
        question_ids = [int(id) for id in selected_ids_str.split(',')]
        lesson.questions = question_ids
    else:
        lesson.questions = []

    db.session.commit()
    #flash(f'Урок "{lesson.id}" успешно обновлен', 'success')
    return redirect(url_for('lesson_list'))

@app.route('/dashboard/testing_management/lesson_delete/<int:less_id>', methods=['POST'])
def lesson_delete(less_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    less = Lesson.query.get_or_404(less_id)
    db.session.delete(less)
    flash(f"Урок '{less_id}' удален")
    db.session.commit()

    return redirect(url_for('lesson_list'))

@app.route('/dashboard/testing_management/lesson_instruction')
def lesson_instruction():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    return render_template(mgn + 'lesson_instruction.html')
# ---------------------------------------------------------
# Панель управления Группами
# ---------------------------------------------------------
@app.route('/dashboard/testing_management/group_create', methods=['GET', 'POST'])
def group_create():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    users = [u for u in User.query.order_by(User.id).all() if u.role_name == 'user']
    group_names = [g.groupname for g in Group.query.order_by(Group.groupname).all()]
    if request.method == 'GET':
        return render_template(mgn + 'group_create.html', users=users, group_names=group_names)

    group_name = request.form.get('group_name')
    users_ids = request.form.get('selected_ids')

    group = Group(group_name)

    users_ids = [int(id) for id in users_ids.split(',')]
    group.add_users(users_ids)

    group.save()

    return redirect(url_for('testing_management'))

@app.route('/dashboard/testing_management/group_list')
def group_list():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    groups = Group.query.order_by(Group.id).all()
    return render_template(mgn + 'group_list.html', groups=groups)

@app.route('/dashboard/lesson_list/group_edit/<int:group_id>', methods=['GET', 'POST'])
def group_edit(group_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    group = Group.query.get_or_404(group_id)
    users = [u for u in User.query.order_by(User.id).all() if u.role_name == 'user']
    group_names = [g.groupname for g in Group.query.order_by(Group.groupname).all() if g.id != group_id]

    if request.method == 'GET':
        return render_template(mgn + 'group_edit.html', group=group, users=users, group_names=group_names)

    group_name = request.form.get('group_name')
    users_ids = request.form.get('selected_ids')

    group.set_groupname(group_name)

    users_ids = [int(id) for id in users_ids.split(',')]
    group.add_users(users_ids)

    db.session.commit()

    return redirect(url_for('group_list'))

@app.route('/dashboard/testing_management/group_delete/<int:group_id>', methods=['POST'])
def group_delete(group_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    group = Group.query.get_or_404(group_id)
    db.session.delete(group)
    flash(f"Группа '{group_id}' удалена")
    db.session.commit()

    return redirect(url_for('group_list'))

@app.route('/dashboard/testing_management/group_instruction')
def group_instruction():
    if not check_privileges():
        return redirect(url_for('ErAuth'))
    return render_template(mgn + 'group_instruction.html')
# ---------------------------------------------------------
# Панель управления Тестированиями
# ---------------------------------------------------------
@app.route('/dashboard/testing_management')
def testing_management():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    if request.method == 'GET':
        return render_template(mgn + 'testing_management.html')

@app.route('/dashboard/testing_management/testing_management_instruction')
def testing_management_instruction():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    if request.method == 'GET':
        return render_template(mgn + 'testing_management_instruction.html')

@app.route('/dashboard/testing_management/testing_create', methods=['GET', 'POST'])
def testing_create():
    if not check_privileges():
        return redirect(url_for('ErAuth'))
    testing_names = [t.name for t in Testing.query.order_by(Testing.name).all()]
    groups = Group.query.order_by(Group.id).all()
    lessons = Lesson.query.order_by(Lesson.id).all()
    if request.method == 'GET':
        return render_template(mgn + 'testing_create.html', groups=groups, lessons=lessons, testing_names=testing_names)

    testing_name = request.form.get('testing_name')
    status = request.form['status'] == 'active'
    lesson_id = request.form.get('lesson_id')
    groups_ids = request.form.get('group_ids')

    testing = Testing(testing_name)
    testing.set_status(status)
    testing.add_lesson(lesson_id)
    groups_ids = [int(id) for id in groups_ids.split(',')]
    testing.add_group(groups_ids)

    testing.save()

    return redirect(url_for('testing_management'))

@app.route('/dashboard/testing_management/testing_list')
def testing_list():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    testings = Testing.query.order_by(Testing.id).all()
    lessons = Lesson.query.order_by(Lesson.id).all()
    lessons_dict = {lesson.id: lesson for lesson in lessons}
    return render_template(mgn + 'testing_list.html', testings=testings, lessons_dict=lessons_dict)

@app.route('/dashboard/testing_management/testing_list/testing_edit/<int:testing_id>', methods=['GET','POST'])
def testing_edit(testing_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    testing = Testing.query.get_or_404(testing_id)

    if request.method == 'GET':
        lessons = Lesson.query.order_by(Lesson.id).all()
        groups = Group.query.order_by(Group.id).all()

        group_ids = testing.group_id
        lessons_dict = {lesson.id: lesson for lesson in lessons}
        testing_names = [t.name for t in Testing.query.order_by(Testing.name).all() if t.id != testing_id]

        return render_template(mgn + 'testing_edit.html',
                               testing=testing,
                               lessons=lessons,
                               groups=groups,
                               group_ids=group_ids,
                               lessons_dict=lessons_dict,
                               testing_names=testing_names)

    testing_name = request.form.get('testing_name')
    status = request.form['status'] == 'active'
    lesson_id = request.form.get('lesson_id')
    groups_ids = request.form.get('group_ids')

    testing.name = testing_name
    testing.set_status(status)
    testing.add_lesson(lesson_id)
    groups_ids = [int(id) for id in groups_ids.split(',')]
    testing.add_group(groups_ids)

    db.session.commit()

    return redirect(url_for('testing_list'))

@app.route('/dashboard/testing_management/testing_list/testing_delete/<int:testing_id>', methods=['POST'])
def testing_delete(testing_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    testing = Testing.query.get_or_404(testing_id)
    db.session.delete(testing)
    db.session.commit()
    flash(f'Тестирование "{testing.name}" с ID - "{testing.id}" удалено')

    return redirect(url_for('testing_list'))

# ---------------------------------------------------------
# Тестирование: режим
# ---------------------------------------------------------
@app.route('/test_room_preview')
def test_room_preview():
    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()
    testings_all = Testing.query.order_by(Testing.id).all()
    testings = list()
    user_results = Result.query.filter_by(user_id=curent_user.id).all()
    for test in testings_all:
        groups = test.group_id
        for group_id in groups:
            group = Group.query.get_or_404(group_id)
            users = group.users
            user_result = [r for r in user_results if r.testing_id == test.id]
            if curent_user.id in users and len(user_result) == 0:
                testings.append(test)
    lessons = Lesson.query.order_by(Lesson.id).all()
    lessons_dict = {lesson.id: lesson for lesson in lessons}

    return render_template('test_room_preview.html',
                           user=curent_user,
                           testings=testings,
                           lessons_dict=lessons_dict)

@app.route('/test_room_preview/test_room_memo')
def test_room_memo():
    return render_template('test_room_memo.html')


def save_test_result(session):
    if session.get('result_saved_to_db'):
        print("DEBUG: Результат уже сохранен в БД ранее")
        return

    testing_id = session.get('testing', {}).get('id')
    lesson_id = session.get('lesson', {}).get('id')
    username = session.get('curent_user')
    experience = session.get('experience', 0)
    messages_id = session.get('messages_id', [])
    answers = session.get('answers', {})

    if not testing_id or not username or not messages_id:
        print("DEBUG: Недостаточно данных для сохранения")
        return

    user = User.query.filter(User.username == username).first()
    if not user:
        print("DEBUG: Пользователь не найден")
        return

    messages = [Message.query.get(mid) for mid in messages_id]

    correct_ids = []
    wrong_ids = []

    for m in messages:
        user_answer = answers.get(str(m.id))
        if user_answer:
            is_correct = user_answer == ('yes' if m.correct else 'no')
            if is_correct:
                correct_ids.append(m.id)
            else:
                wrong_ids.append(m.id)

    print(f"DEBUG: Сохраняем результат в БД - user_id={user.id}, score={experience}")
    print(f"DEBUG: correct_ids={correct_ids}, wrong_ids={wrong_ids}")

    try:
        result = Result(
            testing_id=testing_id,
            lesson_id=lesson_id,
            user_id=user.id,
            score=experience,
            correct_answers_id=correct_ids,
            wrong_answers_id=wrong_ids
        )
        db.session.add(result)
        db.session.commit()
        print("DEBUG: Результат успешно сохранен в БД")

        session['result_saved_to_db'] = True

    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Ошибка сохранения в БД: {e}")


def show_test_results(session, messages):
    answers = session.get('answers', {})
    correct_count = sum(
        1 for m in messages
        if answers.get(str(m.id)) == ('yes' if m.correct else 'no')
    )

    session['results_correct_count'] = correct_count
    session['results_total'] = len(messages)

    session['test_completed'] = True

    save_test_result(session)

    return redirect(url_for('test_room_result'))

@app.route('/test_room/<int:test>/<int:step>', methods=['GET', 'POST'])
def test_room(test, step):

    if 'testing' not in session or step == 0:
        testing = Testing.query.filter(
            Testing.id == test
        ).first()

        if step == 0 or request.method == 'GET':
            username = session.get('curent_user')
            session.clear()
            session['curent_user'] = username
            session['answers'] = dict()
            session['answered_current'] = False
            session['experience'] = 0
            session['testing'] = {
                'id': testing.id,
                'name': testing.name
            }

        lesson_id = testing.lesson_id
        lesson = Lesson.query.get_or_404(lesson_id)
        session['lesson'] = {
            'id': lesson.id,
            'name': lesson.name,
            'price_correct': lesson.price_correct,
            'price_wrong': lesson.price_wrong,
            'questions': lesson.questions,
        }

        messages_id = lesson.questions
        session['messages_id'] = messages_id

    messages_id = session['messages_id']
    messages = [Message.query.get(m) for m in messages_id]
    total_messages = len(messages)

    if step >= total_messages:
        return show_test_results(session, messages)

    session.setdefault('experience', 0)
    session.setdefault('answers', {})
    session.setdefault('answered_current', False)

    current_msg = messages[step]

    if request.method == 'POST':
        answer = request.form.get('answer')
        action = request.form.get('action', '')

        if action == 'next':
            session['answered_current'] = False
            session.pop('current_answer', None)
            session.pop('current_explanation', None)
            session.pop('current_exp_change', None)
            session.pop('current_is_correct', None)

            next_step = step + 1
            print(f"DEBUG: Redirecting to step {next_step}, experience: {session.get('experience')}")

            if next_step >= total_messages:
                return show_test_results(session, messages)

            return redirect(url_for('test_room', test=test, step=next_step))

        if answer == 'finish' or action == 'finish':
            return show_test_results(session, messages)

        if answer in ['yes', 'no'] and not session.get('answered_current', False):
            is_correct = (answer == 'yes') == current_msg.correct

            lesson = session.get('lesson')
            delta_exp = lesson.get('price_correct') if is_correct else lesson.get('price_wrong')

            session['experience'] = session.get('experience', 0) + delta_exp

            answers = session.get('answers', {})
            answers[str(current_msg.id)] = answer
            session['answers'] = answers

            next_step = step + 1
            if next_step >= total_messages:
                return show_test_results(session, messages)
            return redirect(url_for('test_room', test=test, step=next_step))

    current_answer = session.get('current_answer')
    current_explanation = session.get('current_explanation')
    current_exp_change = session.get('current_exp_change', 0)
    current_is_correct = session.get('current_is_correct')

    return render_template(
        'test_room.html',
        message=current_msg,
        step=step,
        total=total_messages,
        explanation=current_explanation,
        experience=session.get('experience', 0),
        exp_change=current_exp_change,
        current_answer=current_answer,
        is_correct=current_is_correct,
        state='question'
    )


@app.route('/test_room_result', methods=['GET'])
def test_room_result():
    messages_id = session.get('messages_id', [])
    answers = session.get('answers', {})
    lesson_data = session.get('lesson', {})

    if not messages_id or not lesson_data:
        return render_template(
            'test_room_result.html',
            experience=0,
            step=0,
            correct_count=0,
        )

    messages = [Message.query.get(mid) for mid in messages_id]
    total = len(messages)

    price_correct = lesson_data.get('price_correct', 1)
    price_wrong = lesson_data.get('price_wrong', -1)

    correct_count = 0
    wrong_count = 0
    calculated_experience = 0

    for m in messages:
        user_answer = answers.get(str(m.id))
        if user_answer:
            is_correct = user_answer == ('yes' if m.correct else 'no')
            if is_correct:
                correct_count += 1
                calculated_experience += price_correct
            else:
                wrong_count += 1
                calculated_experience += price_wrong

    session_experience = session.get('experience', 0)

    print(f"DEBUG: Опыт из сессии: {session_experience}, Рассчитанный: {calculated_experience}")
    print(f"DEBUG: price_correct={price_correct}, price_wrong={price_wrong}")
    print(f"DEBUG: Правильных: {correct_count}, Неправильных: {wrong_count}")

    final_experience = calculated_experience

    return render_template(
        'test_room_result.html',
        experience=final_experience,
        step=total,
        correct_count=correct_count,
    )


@app.route('/clear_test_results', methods=['GET'])
def clear_test_results():
    keys_to_clear = [
        'experience', 'answers', 'messages_id', 'lesson',
        'testing', 'answered_current', 'current_answer',
        'current_explanation', 'current_exp_change', 'current_is_correct',
        'test_completed', 'results_correct_count', 'results_total',
        'result_saved_to_db'
    ]

    for key in keys_to_clear:
        if key in session:
            session.pop(key)

    flash('Данные тестирования очищены', 'info')
    return redirect(url_for('index'))

# ---------------------------------------------------------
# Результаты тестирований
# ---------------------------------------------------------
@app.route('/dashboard/testing_management/result_list')
def result_list():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    testings = Testing.query.order_by(Testing.id).all()
    lessons = Lesson.query.order_by(Lesson.id).all()
    groups = Group.query.order_by(Group.id).all()

    lessons_dict = {lesson.id: lesson for lesson in lessons}
    groups_dict = {group.id: group for group in groups}

    all_results = Result.query.all()

    test_completed_users = {}
    for result in all_results:
        test_id = result.testing_id
        user_id = result.user_id

        if test_id not in test_completed_users:
            test_completed_users[test_id] = set()
        test_completed_users[test_id].add(user_id)

    for test in testings:
        total_users = 0

        if test.group_id:
            all_users_id = set()

            group_ids = test.group_id

            for group_id in group_ids:
                group = groups_dict.get(group_id)
                if group and group.users:
                    user_ids = group.users
                    all_users_id.update(user_ids)

            total_users = len(all_users_id)

        completed_count = len(test_completed_users.get(test.id, set()))

        test.total_users = total_users
        test.completed_count = completed_count

    return render_template(mgn + 'result_list.html',
                           testings=testings,
                           lessons_dict=lessons_dict,
                           groups_dict=groups_dict)
# ---------------------------------------------------------
# Результаты тестирований
# ---------------------------------------------------------
@app.route('/dashboard/result_testing')
def result_testing():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    results_all = Result.query.get(Lesson.id).all()
    #testings_all = list(set([r.testing_id for r in results_all]))
    #lessons_all = Lesson
    testings = {}
    for r in results_all:
        if r.testing_id not in testings:
            testings[r.testing_id] = []
        testings[r.testing_id].append(r.id)


@app.route('/dashboard/testing_management/results_detailed/<int:testing_id>')
def results_detailed(testing_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    test = Testing.query.get_or_404(testing_id)
    results = Result.query.filter_by(testing_id=testing_id).all()
    groups = Group.query.filter(Group.id.in_(test.group_id)).all() if test.group_id else []

    user_to_groups = {}
    for group in groups:
        for user_id in group.users:
            if user_id not in user_to_groups:
                user_to_groups[user_id] = []
            user_to_groups[user_id].append(group.groupname)

    groups_data = []
    for group in groups:
        group_results = [r for r in results if r.user_id in group.users]

        if group_results:
            scores = []

            for result in group_results:
                correct = len(result.correct_answers_id)
                wrong = len(result.wrong_answers_id)
                total_questions = (correct + wrong)
                total_correct = correct
                scores.append(result.score)

            avg_score = sum(scores) / len(scores)
            total_score = sum(scores)

            groups_data.append({
                'id': group.id,
                'name': group.groupname,
                'total_users': len(group.users),
                'completed_users': len(group_results),
                'avg_score': round(avg_score, 1),
                'total_score': total_score,
                'accuracy': round((total_correct / total_questions * 100) if total_questions > 0 else 0, 1),
                'total_questions': total_questions,
                'total_correct': total_correct
            })

    users_data = []
    for result in results:
        user = User.query.get(result.user_id)
        if user:
            correct = len(result.correct_answers_id)
            wrong = len(result.wrong_answers_id)
            total = correct + wrong

            user_groups = user_to_groups.get(user.id, [])

            users_data.append({
                'id': user.id,
                'username': user.username,
                'group_name': user_groups[0] if user_groups else 'Без группы',
                'group_names': user_groups,
                'groups': user_groups,
                'total_questions': total,
                'correct': correct,
                'wrong': wrong,
                'accuracy': round((correct / total * 100) if total > 0 else 0, 1),
                'score': result.score
            })

    all_scores = [result.score for result in results]

    score_distribution = {}
    for score in all_scores:
        score_distribution[score] = score_distribution.get(score, 0) + 1

    sorted_scores = sorted(score_distribution.keys())

    chart_data = {
        'labels': sorted_scores,
        'values': [score_distribution[score] for score in sorted_scores]
    }

    return render_template(mgn + 'results_detail.html',
                           test=test,
                           groups_data=groups_data,
                           users_data=users_data,
                           chart_data=chart_data)


@app.route('/dashboard/testing_management/group_results/<int:testing_id>/<int:group_id>')
def group_results(testing_id, group_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    test = Testing.query.get_or_404(testing_id)
    group = Group.query.get_or_404(group_id)
    lesson = Lesson.query.get_or_404(test.lesson_id)

    group_user_ids = group.users or []

    # Результаты пользователей группы
    results = Result.query.filter_by(testing_id=testing_id).all()

    # Фильтруем результаты по пользователям группы
    group_results = [r for r in results if r.user_id in group_user_ids]

    # Собираем статистику пользователей
    users_data = []
    for result in group_results:
        user = User.query.get(result.user_id)
        if user:
            correct = len(result.correct_answers_id)
            wrong = len(result.wrong_answers_id)
            total = correct + wrong

            users_data.append({
                'id': user.id,
                'username': user.username,
                'total_questions': total,
                'correct': correct,
                'wrong': wrong,
                'accuracy': round((correct / total * 100) if total > 0 else 0, 1),
                'score': result.score
            })

    # Собираем все вопросы урока (messages)
    all_questions = Message.query.filter(Message.id.in_(lesson.questions)).all() if lesson.questions else []
    total_questions_count = len(all_questions)

    # Анализируем ошибки
    common_errors = []
    individual_errors = []
    all_errors_dict = {}

    # Собираем все ошибки
    for result in group_results:
        for wrong_id in result.wrong_answers_id:
            message = Message.query.get(wrong_id)
            if message:
                if wrong_id not in all_errors_dict:
                    all_errors_dict[wrong_id] = {
                        'count': 0,
                        'users': [],
                        'message': message
                    }
                all_errors_dict[wrong_id]['count'] += 1
                all_errors_dict[wrong_id]['users'].append(
                    User.query.get(result.user_id)
                )

    # Разделяем на общие и индивидуальные ошибки
    for message_id, error_data in all_errors_dict.items():
        message_data = {
            'id': message_id,
            'text': error_data['message'].text,
            'correct': error_data['message'].correct,
            'comment_yes': error_data['message'].comment_yes,
            'comment_no': error_data['message'].comment_no,
            'error_count': error_data['count'],
            'users': error_data['users']
        }

        if error_data['count'] > 1:
            common_errors.append(message_data)
        else:
            individual_errors.append({
                'message': message_data,
                'user': error_data['users'][0]
            })

    # Общая статистика группы
    total_questions_all = sum([len(r.correct_answers_id) + len(r.wrong_answers_id) for r in group_results])
    total_correct_all = sum([len(r.correct_answers_id) for r in group_results])

    group_stats = {
        'total_users': len(group_user_ids),
        'completed_users': len(group_results),
        'avg_score': round(sum([r.score for r in group_results]) / len(group_results), 1) if group_results else 0,
        'total_score': sum([r.score for r in group_results]),
        'total_correct': total_correct_all,
        'total_wrong': sum([len(r.wrong_answers_id) for r in group_results]),
        'total_questions': total_questions_all,
        'accuracy': round((total_correct_all / total_questions_all * 100) if total_questions_all > 0 else 0, 1)
    }

    return render_template(mgn + 'group_results.html',
                           test=test,
                           group=group,
                           users_data=users_data,
                           group_stats=group_stats,
                           common_errors=common_errors,
                           individual_errors=individual_errors,
                           common_errors_count=len(common_errors),
                           individual_errors_count=len(individual_errors),
                           total_questions_count=total_questions_count)

@app.route('/dashboard/testing_management/user_results/<int:testing_id>/<int:user_id>')
def user_results(testing_id, user_id):
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    test = Testing.query.get_or_404(testing_id)
    user = User.query.get_or_404(user_id)
    result = Result.query.filter_by(testing_id=testing_id, user_id=user_id).first_or_404()

    groups = Group.query.filter(Group.id.in_(test.group_id)).all() if test.group_id else []
    user_groups = []

    for group in groups:
        if user_id in group.users:
            user_groups.append(group.groupname)

    user_group_display = ', '.join(user_groups) if user_groups else 'Без группы'

    wrong_questions = []
    if result.wrong_answers_id:
        for question_id in result.wrong_answers_id:
            question = Message.query.get(question_id)
            if question:
                wrong_questions.append(question)

    correct_count = len(result.correct_answers_id)
    wrong_count = len(result.wrong_answers_id)
    total_count = correct_count + wrong_count

    return render_template(mgn + 'user_results.html',
                           test=test,
                           user=user,
                           result=result,
                           user_group_display=user_group_display,
                           user_groups=user_groups,
                           wrong_questions=wrong_questions,
                           correct_count=correct_count,
                           wrong_count=wrong_count,
                           total_count=total_count)

# ---------------------------------------------------------
# Тестирования пользователя: список и история
# ---------------------------------------------------------
@app.route('/test_room_preview/history_result')
def history_result():
    curent_user = User.query.filter(
        User.username.ilike(session.get('curent_user'))
    ).first()

    if not curent_user:
        return redirect(url_for('login'))

    results = Result.query.filter_by(user_id=curent_user.id).all()

    testing_ids = {r.testing_id for r in results if r.testing_id}
    lesson_ids = {r.lesson_id for r in results if r.lesson_id}

    testings_dict = {}
    if testing_ids:
        testings = Testing.query.filter(Testing.id.in_(testing_ids)).all()
        testings_dict = {t.id: t for t in testings}

    lessons_dict = {}
    if lesson_ids:
        lessons = Lesson.query.filter(Lesson.id.in_(lesson_ids)).all()
        lessons_dict = {l.id: l for l in lessons}

    return render_template('history_result.html',
                           user=curent_user,
                           results=results,
                           testings_dict=testings_dict,
                           lessons_dict=lessons_dict)

@app.route('/test_room_preview/history_result/user_result/<int:testing_id>/<int:user_id>')
def user_result(testing_id, user_id):
    curent_user = User.query.filter(
        User.username.ilike(session.get('curent_user'))
    ).first()

    if not check_user_id(user_id):
        return redirect(url_for('ErAuth'))

    if curent_user.id != user_id:
        return "Доступ запрещён", 403


    test = Testing.query.get_or_404(testing_id)
    user = User.query.get_or_404(user_id)
    result = Result.query.filter_by(testing_id=testing_id, user_id=user_id).first_or_404()

    groups = Group.query.filter(Group.id.in_(test.group_id)).all() if test.group_id else []
    user_groups = []

    for group in groups:
        if user_id in group.users:
            user_groups.append(group.groupname)

    user_group_display = ', '.join(user_groups) if user_groups else 'Без группы'

    wrong_questions = []
    if result.wrong_answers_id:
        for question_id in result.wrong_answers_id:
            question = Message.query.get(question_id)
            if question:
                wrong_questions.append(question)

    correct_count = len(result.correct_answers_id)
    wrong_count = len(result.wrong_answers_id)
    total_count = correct_count + wrong_count

    return render_template(mgn + 'user_result.html',
                           test=test,
                           user=user,
                           result=result,
                           user_group_display=user_group_display,
                           user_groups=user_groups,
                           wrong_questions=wrong_questions,
                           correct_count=correct_count,
                           wrong_count=wrong_count,
                           total_count=total_count)


# ---------------------------------------------------------
# Консоль администратора
# ---------------------------------------------------------
@app.route('/cons')
def cons():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    # Статистика
    total_users = User.query.count()
    total_teachers = User.query.filter_by(privileges=1).count()
    total_admins = User.query.filter_by(privileges=2).count()
    total_messages = Message.query.count()
    total_groups = Group.query.count()
    total_lessons = Lesson.query.count()
    total_testings = Testing.query.count()
    total_results = Result.query.count()

    # Последние N пользователей
    N = 5
    recent_users = User.query.order_by(User.id.desc()).limit(N).all()

    return render_template(con + 'cons.html',
                           total_users=total_users,
                           total_teachers=total_teachers,
                           total_admins=total_admins,
                           total_messages=total_messages,
                           total_groups=total_groups,
                           total_lessons=total_lessons,
                           total_testings=total_testings,
                           total_results=total_results,
                           recent_users=recent_users)


# ---------------------------------------------------------
# Управление пользователями
# ---------------------------------------------------------
@app.route('/cons/users')
def console_users():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    users = User.query.order_by(User.id).all()
    return render_template(con + 'console_users.html', users=users)


@app.route('/cons/users/edit/<int:user_id>', methods=['GET', 'POST'])
def console_user_edit(user_id):
    if not check_admin():
        return redirect(url_for('ErAuth'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        # Изменение ролей
        new_role = request.form.get('privileges')
        if new_role in ['0', '1', '2']:
            user.privileges = int(new_role)

        # Сброс пароля
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
            flash('Пароль изменен', 'success')

        db.session.commit()
        flash('Пользователь обновлен', 'success')
        return redirect(url_for('console_users'))

    return render_template(con + 'console_user_edit.html', user=user)


@app.route('/cons/users/delete/<int:user_id>', methods=['POST'])
def console_user_delete(user_id):
    if not check_admin():
        return redirect(url_for('ErAuth'))

    user = User.query.get_or_404(user_id)

    # Нельзя удалить себя
    current_username = session.get('curent_user')
    if user.username == current_username:
        flash('Нельзя удалить свой собственный аккаунт!', 'danger')
        return redirect(url_for('console_users'))

    # Нельзя удалить последнего админа
    if user.privileges == 2:
        admin_count = User.query.filter_by(privileges=2).count()
        if admin_count <= 1:
            flash('Нельзя удалить последнего администратора!', 'danger')
            return redirect(url_for('console_users'))

    # Удаление результатов пользователя
    Result.query.filter_by(user_id=user_id).delete()

    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь {user.username} удален', 'success')
    return redirect(url_for('console_users'))


# ---------------------------------------------------------
# Очистка истории результатов
# ---------------------------------------------------------
@app.route('/cons/cleanup')
def console_cleanup():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    total_results = Result.query.count()

    # Фильтр по пользователям
    results_by_user = {}
    all_results = Result.query.all()

    for result in all_results:
        user_id = result.user_id
        if user_id not in results_by_user:
            results_by_user[user_id] = 0
        results_by_user[user_id] += 1

    # Фильтр по тестированиям
    results_by_testing = {}
    for result in all_results:
        testing_id = result.testing_id
        if testing_id not in results_by_testing:
            results_by_testing[testing_id] = 0
        results_by_testing[testing_id] += 1

    return render_template(con + 'console_cleanup.html',
                           total_results=total_results,
                           results_by_user=results_by_user,
                           results_by_testing=results_by_testing,
                           total_users=len(results_by_user),
                           total_testings=len(results_by_testing))


@app.route('/cons/cleanup/execute', methods=['POST'])
def console_cleanup_execute():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    action = request.form.get('action')

    # Удаление всех результатов
    if action == 'clear_all_results':
        count = Result.query.count()
        Result.query.delete()
        db.session.commit()
        flash(f'Удалено {count} результатов тестирований', 'success')

    elif action == 'clear_user_results':
        # Удаление результатов пользователя
        user_id = request.form.get('user_id')
        if user_id:
            count = Result.query.filter_by(user_id=user_id).count()
            Result.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            flash(f'Удалено {count} результатов пользователя', 'success')

    elif action == 'clear_testing_results':
        # Удаление результатов тестирования
        testing_id = request.form.get('testing_id')
        if testing_id:
            count = Result.query.filter_by(testing_id=testing_id).count()
            Result.query.filter_by(testing_id=testing_id).delete()
            db.session.commit()
            flash(f'Удалено {count} результатов тестирования', 'success')

    return redirect(url_for('console_cleanup'))


# ---------------------------------------------------------
# Экспорт данных
# ---------------------------------------------------------
@app.route('/cons/export')
def console_export():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    return render_template(con + 'console_export.html')


@app.route('/cons/export/users_csv')
def export_users_csv():
    if not check_admin():
        return redirect(url_for('ErAuth'))

    users = User.query.all()

    # Создаем CSV вручную
    csv_data = "ID,Username,Role,Registration\n"
    for user in users:
        role = "Пользователь"
        if user.privileges == 1:
            role = "Учитель"
        elif user.privileges == 2:
            role = "Администратор"

        csv_data += f"{user.id},{user.username},{role}\n"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=users_export.csv"}
    )
# ---------------------------------------------------------
# Запуск дебагера
# ---------------------------------------------------------
@app.route('/test', methods=['GET', 'POST'])
def test():
    User.create_default_users()
    user = User.query.filter(
        User.username.ilike('DARET')
        ).first()

    return render_template('index.html', user=user)
if __name__ == '__main__':
    print("Регистрация маршрутов:")
    for rule in app.url_map.iter_rules():
        print(f"{rule.methods} {rule.rule}")
    app.run(debug=True, host='0.0.0.0', port=80)

