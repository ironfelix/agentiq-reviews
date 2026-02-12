# 12-Month Filter — Summary

## Что сделали

### ✅ Добавлен фильтр 12 месяцев
**Файл:** [`scripts/wbcon-task-to-card-v2.py:882-902`](../scripts/wbcon-task-to-card-v2.py#L882-L902)

До фильтра скрипт обрабатывал **все отзывы** (до 5+ лет назад), что искажало:
- Quality score (включал древние ошибки)
- Money loss (неточный расчёт)
- Fashion-анализ (период "фев 2024 — фев 2026")
- Worst responses (отзывы из 2021 года!)

Теперь:
```python
cutoff_12months = now_utc - timedelta(days=366)  # 366 для граничных дат
if created_dt >= cutoff_12months:
    filtered_feedbacks.append(fb)
```

### ✅ Пересобраны все отчёты
**Скрипт:** [`scripts/rebuild_all_reports.py`](../scripts/rebuild_all_reports.py)

**Результаты:**
- **Task 3** (433575851): 24 отзыва, quality 4/10
- **Task 4** (177068052 Royal Canin): **202 → 123** отзыва (-39%), quality **10/10 → 8/10**

**Вывод:** Старые отзывы завышали quality score!

### ✅ Перезапущены воркеры
```bash
# Celery worker
celery -A backend.tasks.celery_app worker --loglevel=info --detach

# FastAPI
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### ✅ Обновлена документация
1. **CHANGELOG_12_MONTH_FILTER.md** — полное описание изменений
2. **MEMORY.md** — добавлен баг "12-month filter"
3. **QUALITY_SCORE_FORMULA.md** — пример Royal Canin (123 вместо 202)

---

## Зачем это нужно

### 1. **Актуальность данных**
Отзывы 3-5 лет назад **не релевантны**:
- Товар изменился (состав, производитель)
- Продавец улучшил коммуникацию
- Старые проблемы решены

### 2. **Честная оценка**
Quality score должен отражать **текущую** работу, а не ошибки 2021 года.

**Пример (Royal Canin):**
- **До фильтра:** 10/10 (но включал 79 древних отзывов)
- **После:** 8/10 (реальная оценка за 12 мес)

### 3. **Корректный money_loss**
Потери рассчитываются от **текущих продаж**, а не древних отзывов.

### 4. **Соответствие заявленному**
"12 месяцев" теперь реально 12 месяцев, а не "всё что есть в API".

---

## Что изменилось в отчётах

| Метрика | До | После |
|---------|----|----|
| Период анализа | All-time (5+ лет) | 12 месяцев |
| Feedback count | 202 | 123 (Royal Canin) |
| Worst responses | 2021-2024 года | Только 2025-2026 |
| Quality score | 10/10 (завышен) | 8/10 (честно) |
| Fashion-анализ | "фев 2024 — фев 2026" | Корректный 12-мес |

---

## Для разработчиков

### Как работает фильтр
```python
# 1. Dedup по fb_id (в скрипте)
# 2. Filter по дате (НОВОЕ!)
cutoff = now - timedelta(days=366)
if fb.created_at >= cutoff:
    keep_feedback()

# 3. Анализ (LLM, classification, etc.)
```

### Почему 366 дней?
Cutoff включает **время** (не только дату):
- Отзыв "2025-02-07 10:00" не пройдёт если cutoff "2025-02-07 23:00"
- +1 день запаса = boundary dates включены

### Как пересобрать отчёты
```bash
cd agentiq
source apps/reviews/venv/bin/activate
python3 scripts/rebuild_all_reports.py
```

**Output:**
```
Task 4: Article 177068052
  12-month filter: 202 -> 123 feedbacks
  ✅ SUCCESS! Quality score: 8/10
```

---

## См. также
- **CHANGELOG_12_MONTH_FILTER.md** — подробный changelog
- **QUALITY_SCORE_FORMULA.md** — формула расчёта quality_score
- **wbcon-task-to-card-v2.py:882-902** — код фильтра
