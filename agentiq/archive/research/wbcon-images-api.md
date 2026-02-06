# WBCon Images API (01-img)

## Назначение
Сервис получения ссылок на изображения товаров Wildberries.ru.

## Базовый URL
`https://01-img.wbcon.su`

## Доступ
- Email: `vanili7@gmail.com` (без «n»)
- Пароль выдаётся поддержкой и **не хранится в репозитории**.

Рекомендация: хранить пароль локально в переменной окружения `WBCON_PASS`.

## Получить ссылки на изображения
**GET** `/get`

Параметры:
- `article` — артикул товара
- `email` — ваш email
- `password` — пароль

Пример:
```bash
export WBCON_EMAIL="vanili7@gmail.com"
export WBCON_PASS="<ваш_пароль>"
ARTICLE=267824421

curl -s --get "https://01-img.wbcon.su/get" \
  --data-urlencode "article=${ARTICLE}" \
  --data-urlencode "email=${WBCON_EMAIL}" \
  --data-urlencode "password=${WBCON_PASS}" \
  | python3 -m json.tool | head -n 40
```

Пример ответа:
```json
{
  "article": 169619643,
  "images_urls": [
    "https://basket-12.wbbasket.ru/vol1696/part169619/169619643/images/big/1.jpg",
    "https://basket-12.wbbasket.ru/vol1696/part169619/169619643/images/big/2.jpg",
    "https://basket-12.wbbasket.ru/vol1696/part169619/169619643/images/big/3.jpg",
    "https://basket-12.wbbasket.ru/vol1696/part169619/169619643/images/big/4.jpg"
  ]
}
```

## Ограничения
- Технические рекомендации для безлимита: **50 запросов/мин**, **60000/сутки**.

## OpenAPI
- Версия: `0.1.0`
- OAS: `3.1`
- Спецификация: `/openapi.json`
- UI: `N|Solid`
