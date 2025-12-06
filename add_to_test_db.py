import sqlite3

DB_PATH = 'test.db'

# Re‑define the 10 demo records with realistic Russian texts
messages = [
    {
        "text": "Счёт за коммунальные услуги выписан на имя Иванова Ивана Петровича, сумма 3 234,57 руб. Срочно оплатите по номеру 9XXXXXXXXXX, иначе все коммунальные услуги будут отключены!",
        "correct": True,
        "comment_yes": "(ВЕРНО!) Телефон указан как единственный способ оплаты и есть требования срочной оплаты с угрозами.",
        "comment_no": "(НЕВЕРНО) В счете указан телефон как единственный способ оплаты, хотя в реальном счете должны быть альтернативные варианты в виде банковских реквизитах, QR-код и другие."
        "Также присутствуют требования срочности оплаты и угрозы, которые мошенники часто используют, чтобы ввести жертву в состояние стресса.",
        "price_correct": 1,
        "price_wrong": -0.4
    },
    {
        "text": "Важное сообщение от банка ВТБ! Ваша карта заблокирована из-за подозрительной активности. Срочно позвоните на номер 8-800-XXX-XX-XX для разблокировки. Время ограничено!",
        "correct": True,
        "comment_yes": "(ВЕРНО!) Указан только телефонный номер, используются слова срочности и угроза блокировки карты.",
        "comment_no": "(НЕВЕРНО) Реальный банк никогда не будет требовать срочного звонка по номеру из СМС. Используются манипулятивные техники.",
        "price_correct": 0.7,
        "price_wrong": -0.4
    },
    {
        "text": "Уведомление от Сбербанка. На ваш счёт поступила крупная сумма денег. Для активации перевода позвоните 8-9XX-XXX-XX-XX. Действуйте быстро, предложение ограничено!",
        "correct": True,
        "comment_yes": "(ВЕРНО!) Присутствует номер телефона как единственный контакт, используются заманчивые предложения и срочность.",
        "comment_no": "(НЕВЕРНО) Банки не рассылают подобные сообщения с просьбой позвонить на сторонние номера. Это классическая схема мошенничества.",
        "price_correct": 0.6,
        "price_wrong": -0.6
    },
    {
        "text": "Служба безопасности Альфа-Банка. Обнаружена попытка взлома вашего аккаунта. Сохраните номер 8-800-XXX-XX-XX для подтверждения личности.",
        "correct": True,
        "comment_yes": "(ВЕРНО!) Используется бренд известного банка, присутствует угроза безопасности и требование сохранить номер.",
        "comment_no": "(НЕВЕРНО) Банки никогда не сообщают о подобных попытках через СМС и не просят сохранять номера телефонов.",
        "price_correct": 0.9,
        "price_wrong": -0.5
    }
]


conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
# Create table if not exists (matching Message model)
cursor.execute('''
CREATE TABLE IF NOT EXISTS message (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    correct BOOLEAN NOT NULL,
    price_correct REAL DEFAULT 0.0,
    price_wrong REAL DEFAULT 0.0,
    comment_yes TEXT,
    comment_no TEXT
)''')
conn.commit()
# Insert messages
for m in messages:
    cursor.execute('INSERT INTO message (text, correct, price_correct, price_wrong, comment_yes, comment_no) VALUES (?, ?, ?, ?, ?, ?)',
                   (m['text'], int(m['correct']), m['price_correct'], m['price_wrong'], m['comment_yes'], m['comment_no']))
conn.commit()
conn.close()
print('Inserted', len(messages), 'records into', DB_PATH)
