# AgentIQ — Rules for AI Assistant

## Экономия токенов
1. **Не перечитывай файлы** — если файл читался в сессии, используй кэш
2. **Короткие ответы** — без лишних объяснений, сразу к делу
3. **Батч-редактирование** — группируй Edit вызовы в параллель
4. **Не используй Task/Explore** без явной необходимости

## Ключевые файлы
- `docs/reviews/PROJECT_SUMMARY.md` — архитектура, структура, quickstart
- `docs/reviews/RESPONSE_GUARDRAILS.md` — правила генерации ответов (ОБЯЗАТЕЛЬНО)
- `scripts/llm_analyzer.py` — LLM промпты и guardrails
- `scripts/wbcon-task-to-card-v2.py` — главный скрипт анализа
- `apps/reviews/backend/tasks.py` — Celery worker (WBCON API v2)

## Стиль
- Фон: `#0a1018`, карточки: `#141e2b`
- Акцент: `#e8a838`, ошибки: `#e85454`, успех: `#4ecb71`, инфо: `#7db8e8`
- Текст: `#fff` / `#c8d6e0` / `#a8bcc8` / `#7a9bb5`
- Шрифт: Montserrat, max-width: 560px

## Guardrails
- "Как стоило ответить" = **готовый текст от лица продавца**
- НИКОГДА: возвраты, замены, компенсации, конкретные сроки
- НИКОГДА: упоминать ИИ/бот/нейросеть/GPT
- ВСЕГДА: эмпатия + направить в ЛК WB если покупатель сам просит возврат

## API
- **WBCON v2** (отзывы): `19-fb.wbcon.su`, header `token: JWT`, exp 2026-03-10
- **WBCON QS** (вопросы): `qs.wbcon.su`, email+password
- **WB CDN**: `basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/`
- Basket table в `_wb_basket_num()` (Feb 2026, baskets 01-26)
