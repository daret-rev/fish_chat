from pathlib import Path
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, jsonify
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import login_user, UserMixin, LoginManager
from flask_sqlalchemy import SQLAlchemy
import model
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

    privileges = db.Column(db.Boolean, default = False)

    def __repr__(self):
        return f'<User {self.username}>'

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    @property
    def is_admin(self):
        return self.privileges

    @staticmethod
    def create_default_users():
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', privileges=True)
            admin.set_password('admin_admin')
            db.session.add(admin)

        db.session.commit()

    @staticmethod
    def create_user(username, password):

        user = User(username=username, privileges=False)
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        return user

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
mgn = '/templateM/'

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
        print('User is admin:',user.is_admin)

        session['curent_user'] = user.username
        if user.is_admin:
            """return jsonify({
            'success': True,
            'redirect': url_for('dashboard'),
            'message': 'Вход выполнен'
            })"""

            return redirect(url_for('dashboard'))
        else:
            """return jsonify({
            'success': True,de
            'redirect': url_for('index'),
            'message': 'Вход выполнен'
            })"""
            return  render_template('index.html', user=user)
    else:
        return jsonify({
            'success': False,
            'message': 'Неверный логин или пароль'
        }), 401
    
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
        return jsonify({
            'success': False,
            'message': 'Пользователь уже существует'
        })
    
    user = User.create_user(username, password)

    """if user:
        return jsonify({
            'success': True,
            'redirect': url_for('index'),
            'message': 'Пользователь создан'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Пользователь уже существует'
        })"""
    if user:
        return render_template('index.html')
    else:
        return jsonify({
            'success': False,
            'message': 'Пользователь уже существует'
        })

@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session['curent_user'] = None
    return redirect(url_for('index'))
# ---------------------------------------------------------
# Панель управления БД
# ---------------------------------------------------------
@app.route('/ErAuth', methods=['GET'])
def ErAuth():
    return render_template(mgn + 'ErAuth.html')

def check_privileges():
    curent_user = User.query.filter(
        User.username.ilike(
            session.get('curent_user')
        )
    ).first()
    print("DEBUD: curent user is",curent_user)
    print("DEBUG: curent user privileges -",curent_user.is_admin)

    if not curent_user or not curent_user.is_admin:
        return False
    else:
        return True

@app.route('/dashboard')
def dashboard():
    if not check_privileges():
        return redirect(url_for('ErAuth'))

    return render_template(mgn + 'dashboard.html')
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
    time = request.form.get('time')
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

    users = User.query.order_by(User.id).offset(1).all()
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
    users = User.query.order_by(User.id).offset(1).all()
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
# Панель управления Тестами
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
    app.run(debug=True, host='0.0.0.0', port=5000)

