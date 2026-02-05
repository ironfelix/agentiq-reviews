# Webcon отзывы WB — методы работы (DEMO)

## Назначение
API‑сервис получения отзывов на товары Wildberries (DEMO).

## Базовая схема работы
1. Создать задачу на сбор отзывов по артикулу.
2. Проверять статус задачи.
3. Получить результаты задачи.

## 1) Создать задачу
**POST** `https://fb.wbcon.su/create_task_fb`

Тело запроса (JSON):
```json
{
  "article": 0000000
}
```

Пример ответа:
```json
{
  "created": true,
  "task_id": 111
}
```

Ошибки:
- **403** — артикул не подходит. В демо доступны только `117220345`, `178614734`, `255299570`.

## 2) Проверить статус задачи
**GET** `https://fb.wbcon.su/task_status?task_id={task_id}`

Пример ответа:
```json
{
  "is_ready": true,
  "error": ""
}
```

## 3) Получить результаты
**GET** `https://fb.wbcon.su/get_results_fb?task_id={task_id}`

### Пагинация (недокументированная, но работает)

API отдаёт максимум **100 отзывов** за запрос. Для получения всех используй `offset`:

```bash
# Первые 100
GET /get_results_fb?task_id=194&offset=0

# Следующие 100
GET /get_results_fb?task_id=194&offset=100

# И так далее...
GET /get_results_fb?task_id=194&offset=200
```

**Параметры:**
| Параметр | Работает | Описание |
|----------|----------|----------|
| `offset` | ✅ Да | Смещение (0, 100, 200...) |
| `limit` | ❌ Нет | Игнорируется, всегда 100 |

**Пример: получить все отзывы:**
```python
def fetch_all_feedbacks(task_id: int) -> list:
    all_feedbacks = []
    offset = 0

    while True:
        url = f"{BASE_URL}/get_results_fb?task_id={task_id}&offset={offset}&email={EMAIL}&password={PASS}"
        data = requests.get(url).json()
        feedbacks = data[0].get("feedbacks", [])

        if not feedbacks:
            break

        all_feedbacks.extend(feedbacks)
        offset += 100

        # Rate limit: 2 запроса/мин для демо, 5000/мин для безлимита
        time.sleep(0.5)

    return all_feedbacks
```

**Для 10 000 отзывов:** ~100 запросов, ~50 сек на безлимите.

Пример ответа:
```json
[
  {
    "feedback_count": 28,
    "feedback_count_with_photo": 13,
    "feedback_count_with_text": 19,
    "feedback_count_with_video": 1,
    "bigger_size_percentage": 0,
    "smaller_size_percentage": 0,
    "ok_size_percentage": 100,
    "five_valuation_distr": 25,
    "four_valuation_distr": 2,
    "three_valuation_distr": 0,
    "two_valuation_distr": 1,
    "one_valuation_distr": 0,
    "rating": 4.8,
    "feedbacks": [
      {
        "fb_id": "J80SduNG_kZ27nTwK72Y",
        "user_id": "50932832",
        "user_photo": "false",
        "user_country": "ru",
        "user_name": "Юлия",
        "article": "302360915",
        "fb_text": "Отличная куртка. Качество пошива хорошее. Размер соответствует. Для Краснодарской зимы идеальный вариант.",
        "valuation": "5",
        "rank": "7.0",
        "color": "черный",
        "size": "XL",
        "fb_created_at": "2025-01-09T14:07:22Z",
        "fb_updated_at": "2025-01-09T14:57:08Z",
        "answer_country": "wbRu",
        "answer_created_at": "2025-01-09T14:48:14Z",
        "answer_updated_at": "2025-01-09T14:57:08Z",
        "answer_editable": "false",
        "supplier_id": "106539",
        "answer_text": "Юлия, здравствуйте! Мы благодарим Вас за отзыв и высокую оценку нашего товара! Нам очень приятно получать обратную связь, мы ценим каждый отзыв! Отдельная благодарность Вам за предоставленные фотографии. Рады, что наша модель так идеально подошла. Носите с удовольствием! Ваше доверие и поддержка являются для нас важными и вдохновляющими факторами.  Для того, чтобы не пропустить наши акции с хорошими скидками, добавляйте наш бренд в избранное, нажав на сердечко в правом верхнем углу на странице бренда. С уважением и заботой, команда бренда IL Primissimo",
        "vote_plus": "0",
        "vote_minus": "0",
        "problems": "[]",
        "advantages": "Отличная",
        "disadvantages": "",
        "count_plus": 0,
        "count_minus": 0
      }
    ]
  }
]
```

## Параметры ответа
- `feedback_count`: кол-во отзывов
- `feedback_count_with_photo`: кол-во отзывов с фото
- `feedback_count_with_text`: кол-во отзывов с текстом
- `feedback_count_with_video`: кол-во отзывов с видео
- `bigger_size_percentage`: соответствие размеру — большемерит
- `smaller_size_percentage`: соответствие размеру — маломерит
- `ok_size_percentage`: соответствие размеру — соответствует
- `five_valuation_distr`: оценки «5*»
- `four_valuation_distr`: оценки «4*»
- `three_valuation_distr`: оценки «3*»
- `two_valuation_distr`: оценки «2*»
- `one_valuation_distr`: оценки «1*»
- `rating`: рейтинг
- `fb_id`: идентификатор отзыва
- `user_id`: id клиента
- `user_photo`: имеется ли фотография клиента
- `user_country`: страна клиента
- `user_name`: имя клиента
- `article`: артикул
- `fb_text`: текст отзыва
- `valuation`: оценка в отзыве
- `rank`: ранк отзыва
- `color`: цвет товара
- `size`: размер товара
- `fb_created_at`: дата и время создания отзыва
- `fb_updated_at`: дата и время обновления отзыва
- `answer_country`: страна ответа на отзыв
- `answer_created_at`: дата и время создания ответа на отзыв
- `answer_updated_at`: дата и время обновления ответа на отзыв
- `answer_editable`: ответ на отзыв доступен к изменению
- `supplier_id`: id продавца
- `answer_text`: текст ответа на отзыв
- `vote_plus`: голос «+»
- `vote_minus`: голос «-»
- `problems`: проблематика
- `advantages`: преимущества товара
- `disadvantages`: недостатки товара
- `count_plus`: кол-во оценок «+»
- `count_minus`: кол-во оценок «-»

## Ограничения и тарифы
- Сервис **не** распространяется на тариф «Разовый запрос» (0,5 руб / запрос).
- Доступен только тариф **БЕЗЛИМИТНЫЙ** с выделенным сервером: **5000 руб/мес**.
- Технические рекомендации для безлимита: **5000 отзывов/мин**, **5 000 000/сутки**.
- Демо-ограничения: **3 артикула** (`117220345`, `178614734`, `255299570`) и **2 запроса/мин**.

## Хосты демо vs 50 коп
По ответу поддержки: у сервисов тарифа **50 коп** базовый домен отличается — добавляется префикс `01-`.

Пример:
- Демо: `https://img.wbcon.su/docs`
- 50 коп: `https://01-img.wbcon.su/docs`

Для отзывов (50 коп):
- Документация: **скрыта** (API‑ссылка)
- Базовый URL: **скрыт** (API‑хост)
- Доступ/пароль выдаёт поддержка (не хранить в репозитории)

## API: обязательные email/password
Параметры `email` и `password` обязательны **для всех** ручек и передаются в query‑строке.

Пример (создать задачу):
```bash
export WBCON_EMAIL=\"<ваш_email>\"
export WBCON_PASS=\"<ваш_пароль>\"
export WBCON_FB_BASE=\"<api_host>\"

curl -s -X POST \"${WBCON_FB_BASE}/create_task_fb?email=${WBCON_EMAIL}&password=${WBCON_PASS}\" \\
  -H \"Content-Type: application/json\" \\
  -d '{\"article\":117220345}'
```

Статус:
```bash
curl -s \"${WBCON_FB_BASE}/task_status?task_id=111&email=${WBCON_EMAIL}&password=${WBCON_PASS}\"
```

Результаты:
```bash
curl -s \"${WBCON_FB_BASE}/get_results_fb?task_id=111&email=${WBCON_EMAIL}&password=${WBCON_PASS}\" \\
  | python3 -m json.tool | head -n 120
```

## Быстрый парсинг ответа (пример)
Вывести только отзывы (первые 3):
```bash
curl -s \"${WBCON_FB_BASE}/get_results_fb?task_id=111&email=${WBCON_EMAIL}&password=${WBCON_PASS}\" \\
  | python3 - <<'PY'
import json, sys
data = json.load(sys.stdin)
feedbacks = (data[0].get(\"feedbacks\") if data and isinstance(data, list) else []) or []
for f in feedbacks[:3]:
    print(f.get(\"fb_id\"), f.get(\"valuation\"), f.get(\"fb_text\", \"\")[:80])
PY
```

## Частые ошибки и причины
- `missing email/password` — email и пароль обязательны в query‑строке.
- `Rate limit exceeded` — лимит исчерпан, попробуйте позже или уточните тариф.
- `Некорректный email или пароль` — неверные креды или доступ не активирован.

## Примечания из OpenAPI
- Версия OpenAPI: `3.1.0`.
- Тип `article`: **integer**.

## OpenAPI
- Версия: `0.1.0`
- OAS: `3.1`
- Спецификация: `/openapi.json`
- UI: `N|Solid`

## Эндпоинты (кратко)
- **POST** `/create_task_fb` — создать задачу
- **GET** `/task_status` — проверить статус
- **GET** `/get_results_fb` — получить результаты
