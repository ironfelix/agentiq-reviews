# AgentIQ — Claude Memory

## ПЕРЕД РАБОТОЙ
1. **`docs/reviews/PROJECT_SUMMARY.md`** — архитектура, файлы, quickstart, API
2. **`docs/reviews/RESPONSE_GUARDRAILS.md`** — banned phrases, формат ответов
3. **`scripts/llm_analyzer.py:608-700`** — COMM_SYSTEM промпт + JSON формат
4. **`scripts/llm_analyzer.py:478-519`** — GUARDRAILS конфиг
5. **`docs/reviews/QUALITY_SCORE_FORMULA.md`** — формула расчёта quality_score (1-10)

## Критичные правила
- "Как стоило ответить" = **готовый текст от лица продавца**, НЕ инструкция
- Правильно: `«Нам жаль! Оформите возврат через ЛК WB»`
- Неправильно: `«Стоило извиниться и вежливо объяснить...»`
- НИКОГДА не обещать возвраты/замены/компенсации в рекомендациях

## Quality Score формула (1-10) — ПРОЦЕНТНАЯ
- `score = 10 - (harmful_pct × 0.1) - (risky_pct × 0.05) + (good_pct × 0.02)`
- Процент от total_analyzed, НЕ абсолютное число
- Пример: 5 harmful из 202 (2.5%) → 10 - 0.25 - ... = 9.65 → 10/10
- Контекст важен: «Спасибо!» на 5★ = acceptable, на 1★ = harmful (ignore)
- LLM промпт: `llm_analyzer.py:639-655` с примерами расчёта

## WB CDN API (без авторизации)
Base: `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/`
- `V` = `nmId // 100000`, `P` = `nmId // 1000`
- Card: `…/ru/card.json` → `imt_name`, `description`, `options[]`
- Prices: `…/price-history.json` → kopecks ÷ 100 = rubles

### Basket ranges (Feb 2026):
```
≤143→01 ≤287→02 ≤431→03 ≤719→04 ≤1007→05 ≤1061→06 ≤1115→07
≤1169→08 ≤1313→09 ≤1601→10 ≤1655→11 ≤1919→12 ≤2045→13
≤2189→14 ≤2405→15 ≤2621→16 ≤2837→17 ≤3053→18 ≤3269→19
≤3485→20 ≤3701→21 ≤3917→22 ≤4133→23 ≤4349→24 ≤4565→25 else→26
```

## WBCON API v2 (отзывы)
- Base: `https://19-fb.wbcon.su/`, Auth: header `token: <JWT>` (exp 2026-03-10)
- `POST /create_task_fb` → `GET /task_status` → `GET /get_results_fb?offset=0`
- Pagination: offset +100, dedup по `fb_id` (дубликаты!)
- Fields: `fb_id`, `fb_text`, `valuation`, `color`, `size`, `fb_created_at`, `answer_text`, `answer_created_at`, `advantages`, `disadvantages`
- Old `01-fb.wbcon.su` мёртв (502). Old `qs.wbcon.su` работает для вопросов.

## WB Chat API + Официальная позиция платформы
- **+20% конверсии** при ответе в течение 1h (офиц. стат. WB) → коммуникация = прямой ROI
- **3 дня** на спасение негативного отзыва до публикации (таймер после ответа покупателя)
- **Платная отсрочка негатива:** +1.75-3.15% комиссии → 315k₽/мес при 10M обороте (!!!!)
- **Чат меняет рейтинг:** покупатель может обновить 1★→5★, старая оценка удаляется
- **SLA критичные:** негатив < 1h, вопросы < 1h (+20% конверсия), обычное < 24h
- **Gap'ы:** Chat API не показывает связь с негативными отзывами, нет дедлайна, нет статуса отзыва
- **Решение:** интегрировать Feedbacks API + Questions API параллельно с Chat API
- Полная документация: `docs/chat-center/WB_CHAT_API_RESEARCH.md` секция 13

## Паттерны и баги
- **12-month filter** — `wbcon-task-to-card-v2.py:882-902` фильтрует feedbacks (366 days для boundary case). Пример: 202→123 отзыва (Royal Canin). Rebuild: `scripts/rebuild_all_reports.py`
- **WBCON pagination** — offset возвращает дубликаты, dedup обязателен
- **Color normalization** — `color` может быть "4 шт. · 120 м". Split + filter via `is_color_variant()`
- **LLM distribution** — LLM может не классифицировать все отзывы. Post-processing добавляет gap в `acceptable`
- **Celery timeout** — 300s для subprocess (DeepSeek бывает медленный)
- **Trend fallback** — 30-day window нужно >=3 отзывов, иначе split-half
- **f-string gotcha** — `!r` нельзя внутри f-string, используй temp var
- **venv** — system python нет dotenv, запускай через `source venv/bin/activate`

## Стиль
- Фон: `#0a1018`, карточки: `#141e2b`
- Акцент: `#e8a838` (оранжевый), ошибки: `#e85454`, успех: `#4ecb71`, инфо: `#7db8e8`
- Шрифт: Montserrat, max-width: 560px
