# 12-Month Date Filter — Changelog

> **Дата:** 2026-02-08
> **Задача:** Исправить проблему с устаревшими отзывами в отчётах

---

## Проблема

### Симптомы
1. **Fashion-анализ показывал "фев 2024 — фев 2026"** (2 года) вместо 12 месяцев
2. **Worst responses содержали отзывы 2021-2023 года** (3-5 лет назад!)
3. **Header "785 БЕЗ ОТВЕТА"** считался от всех отзывов (all-time), а не за 12 мес
4. **Quality score и money_loss** рассчитывались на всех отзывах, включая древние

### Причина
**Скрипт `wbcon-task-to-card-v2.py` НЕ фильтровал отзывы по дате** — обрабатывал все отзывы, которые вернул WBCON API (до 5+ лет давности).

### Обнаружение
GitHub HTML отчёт (Benetton) показал:
- "215 отзывов за 12 месяцев" — но период "фев 2024 — фев 2026"
- Worst responses с датами 2024-10-13, 2023-02-17, 2021-08-20

---

## Решение

### Изменения в коде

**1. Добавлен 12-месячный фильтр** ([wbcon-task-to-card-v2.py:882-902](../scripts/wbcon-task-to-card-v2.py#L882-L902))

```python
# Filter feedbacks to last 12 months (366 days to include boundary dates)
now_utc = datetime.now(timezone.utc)
cutoff_12months = now_utc - timedelta(days=366)
filtered_feedbacks = []
for fb in feedbacks:
    created_str = fb.get("created_at") or fb.get("fb_created_at") or ""
    if not created_str:
        continue
    try:
        # Parse ISO date: "2025-02-07T12:34:56Z" or "2025-02-07 12:34:56"
        created_dt = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        if created_dt >= cutoff_12months:
            filtered_feedbacks.append(fb)
    except (ValueError, AttributeError):
        # If date parse fails, include (safer to include than exclude)
        filtered_feedbacks.append(fb)
if len(filtered_feedbacks) < len(feedbacks):
    print(f"12-month filter: {len(feedbacks)} -> {len(filtered_feedbacks)} feedbacks")
feedbacks = filtered_feedbacks
```

**Почему 366 дней вместо 365?**
- Cutoff включает **время** (не только дату)
- Отзыв "ровно год назад в 10:00" НЕ пройдёт если cutoff в 23:00
- Добавили 1 день запаса для включения граничных дат

**2. Исправлен header.feedback_count** ([wbcon-task-to-card-v2.py:1435](../scripts/wbcon-task-to-card-v2.py#L1435))

До:
```python
"feedback_count": total  # All-time total from WBCON API
```

После:
```python
"feedback_count": len(feedbacks)  # 12-month filtered count
```

---

## Результаты

### Тестирование на mock data
```
5 отзывов (2026-01-15, 2025-03-10, 2025-02-07, 2023-02-17, 2021-08-20)
                                           ↓ ФИЛЬТР ↓
12-month filter: 5 -> 3 feedbacks  ✅
```

### Пересборка отчётов

**Task 3 (артикул 433575851):**
- Отзывов: 24 (все за 12 мес)
- Quality score: 4/10

**Task 4 (артикул 177068052 — Royal Canin):**
- **До фильтра:** 202 отзыва
- **После фильтра:** 123 отзыва (отсечено 79 старых = 39%)
- **Quality score:** 10/10 → **8/10** (более честная оценка)
- **Money loss:** 3,599-11,995₽/мес (вместо 14,669₽ — было завышено)

**Вывод:** Старые отзывы (2021-2024) искажали статистику!

---

## Impact

### Что изменилось в отчётах

| Метрика | До фильтра | После фильтра |
|---------|------------|---------------|
| **Период анализа** | All-time (до 5+ лет) | 12 месяцев |
| **Feedback count** | Total от API | Фильтрованное кол-во |
| **Worst responses** | Могли быть из 2021 года | Только за 12 мес |
| **Fashion-анализ** | 2-летний период | Корректный 12-мес |
| **Quality score** | Искажён старыми ответами | Актуальная оценка |
| **Money loss** | Неточный расчёт | Корректные потери |

### Что НЕ изменилось
- WB CDN API (цены, карточка) — без изменений
- WBCON API flow — без изменений
- Логика классификации LLM — без изменений
- UI/UX отчётов — без изменений

---

## Миграция

### Скрипт пересборки отчётов

Создан [`rebuild_all_reports.py`](../scripts/rebuild_all_reports.py):
```bash
cd agentiq
source apps/reviews/venv/bin/activate
python3 scripts/rebuild_all_reports.py
```

**Что делает:**
1. Находит все completed tasks с `wbcon_task_id`
2. Re-fetch feedbacks через WBCON API (`get_results_fb`)
3. Запускает `wbcon-task-to-card-v2.py` с новым фильтром
4. Обновляет `reports.data` в БД

**Output:**
```
Task 3: Article 433575851
  Total feedbacks: 24
  ✅ SUCCESS! Quality score: 4/10

Task 4: Article 177068052
  12-month filter: 202 -> 123 feedbacks
  ✅ SUCCESS! Quality score: 8/10

DONE: 2/2 tasks rebuilt successfully
```

### Для новых задач
Фильтр применяется автоматически — ничего менять не нужно.

---

## Почему это важно

### 1. **Актуальность данных**
Старые отзывы (3-5 лет назад) НЕ релевантны:
- Товар мог измениться (состав, качество, производитель)
- Продавец мог улучшить коммуникацию
- Старые проблемы могли быть решены

### 2. **Честная оценка коммуникации**
Quality score должен отражать **текущую** работу продавца, а не ошибки 2021 года.

### 3. **Корректный money_loss**
Потери конверсии считаются от **текущих продаж**, а не древних отзывов.

### 4. **Соответствие заявленному периоду**
"12 месяцев" должно быть реально 12 месяцев, а не "фев 2024 — фев 2026".

---

## Обновления документации

1. **MEMORY.md** — добавлен баг: "12-month filter" с примером boundary case
2. **QUALITY_SCORE_FORMULA.md** — пример Royal Canin обновлён (123 отзыва вместо 202)
3. **PROJECT_SUMMARY.md** — упомянут фильтр в архитектуре

---

## Checklist для будущих изменений

Если меняешь логику фильтрации:
- [ ] Проверь boundary case (ровно год назад в разное время)
- [ ] Обнови тесты с реальными датами
- [ ] Пересобери существующие отчёты через `rebuild_all_reports.py`
- [ ] Проверь что `header.feedback_count` соответствует фильтрованному числу
- [ ] Обнови примеры в документации

---

## См. также
- [QUALITY_SCORE_FORMULA.md](QUALITY_SCORE_FORMULA.md) — формула расчёта quality_score
- [wbcon-task-to-card-v2.py:882-902](../scripts/wbcon-task-to-card-v2.py#L882-L902) — код фильтра
- [rebuild_all_reports.py](../scripts/rebuild_all_reports.py) — скрипт миграции
