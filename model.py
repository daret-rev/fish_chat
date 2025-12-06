import json
import openai


BASE_URL = "http://192.168.3.8:1234/v1"
API_KEY = "lmstudio"
MODEL_ID = "openai/gpt-oss-20b"

# Создаём клиент (подключаемся к локальному серверу)
client = openai.OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,          # здесь указывается http://<IP вашего хоста>:1234/v1
)


def prompt(message: str):
    #промт для корректного ответа от модели
    system_msg = (
        "Вы – эксперт по безопасности и мошенничеству. " 
        "Нужно оценить входящее сообщение от банка/рассылки.\n"
        "Ответьте строго в JSON‑формате без лишних символов:\n"
        "{\n"
        '  "status": "REAL" | "FAKE",\n'
        '  "certainty": <float>,   // процент уверенности (0–100)\n'
        '  "text": "<рекомендации>",\n'
        '  "comment": "<доп. комментарий>" | null\n'
        "}\n"
        "Никаких дополнительных строк, не добавляйте ничего сверх JSON."
    )

    user_msg = f"Сообщение: \"{message}\""

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]


def analyze_text(message: str):
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message должен быть строкой")

    # Запрос к модели
    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=prompt(message),
            temperature=0.0,
            max_tokens=512,
            top_p=1.0,
            n=1,
            stream=False,
            stop=None,
        )
    except Exception:
        raise RuntimeError(f"Ошибка при обращении к модели: {Exception}") from Exception

    raw_text = resp.choices[0].message.content.strip()

    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Модель вернула некорректный JSON: {raw_text}"
        ) from exc

    # Проверка полей
    if not isinstance(result, dict):
        raise ValueError("Ответ должен быть JSON")

    required = {"status", "certainty", "text", "comment"}
    missing   = required - result.keys()
    if missing:
        raise ValueError(f"Отсутствуют поля в ответе: {missing}")

    # Проверка типов
    if result["status"] not in ("REAL", "FAKE"):
        raise ValueError("Поле status должно быть REAL или FAKE")
    try:
        certainty = float(result["certainty"])
    except Exception:
        raise ValueError("Поле certainty должно быть числом float")
    if not isinstance(result["text"], str):
        raise ValueError("Поле text должно быть строкой")
    if result["comment"] is not None and not isinstance(result["comment"], str):
        raise ValueError("Поле comment должно быть строкой или null")


    return {
        "status": result["status"],
        "certainty": certainty,
        "text": result["text"],
        "comment": result["comment"]
    }


#?---------------------------------------------------------------------------------
def check_message(msg):
    try:
        output = analyze_text(msg)
        return(json.dumps(output, ensure_ascii=False, indent=2))
    except Exception:
        print(f"❌ Ошибка: {Exception}")

#check_message("Срочно! На вашем счете замечена подозрительная активность. Для предотвращения риска, просим перевести средства по номеру 9XXXXXXXXXX. С уважением, служба безопасности БАНКА")