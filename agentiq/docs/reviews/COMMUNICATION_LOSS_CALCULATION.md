# Методология расчёта потерь от плохой коммуникации

**Версия:** 1.0
**Дата:** 07.02.2026
**Пример:** Артикул 282955222 (Фонарь налобный)

---

## 1. Исходные данные

### Из WBCON API:
- **145 отзывов** за 13 месяцев (13 дек 2024 — 2 фев 2026)
- **30 негативных** (1-3 звезды), **115 позитивных** (4-5 звезд)
- **144 с ответом продавца**, 1 без ответа

### Из WB Public Card API:
- **Цена товара:** 3,229₽ (актуальная цена на момент анализа)
- **Категория:** Фонари налобные (функциональный товар)

### Из LLM-анализа (DeepSeek):
- **Quality Score:** 4/10
- **Классификация ответов:**
  - 30 хороших (20.7%)
  - 95 нормальных (65.5%)
  - 8 критичных (5.5%) — обвинение, игнор, без ответа
  - 66 рискованных (45.5%) — шаблоны
  - 1 подтверждает проблему (0.7%)

---

## 2. Шаг 1: Индекс вреда от ответов

### Веса по типам ошибок:
```
Критичные (blame, ignore, no_answer):  вес 10
Рискованные (template, amplify):       вес 1
Нормальные (ok):                       вес 0
Хорошие (good):                        вес -1 (положительный эффект)
```

### Расчёт:
```
8 критичных × 10 = 80 баллов
66 рискованных × 1 = 66 баллов
────────────────────────────────
Итого: 146 баллов вреда

Максимум: 145 ответов × 10 = 1,450 баллов

Индекс вреда = 146 / 1,450 = 10.1%
```

**Интерпретация:** 10.1% от максимально возможного вреда.

---

## 3. Шаг 2: Влияние на конверсию

### Факторы:
1. **Доля читающих отзывы:** 30-50% покупателей (industry benchmark для маркетплейсов РФ)
2. **Индекс вреда:** 10.1%
3. **Коэффициент категории:** 0.8 (функциональный товар — высокая важность отзывов)

### Формула:
```
CR impact = % читателей × Индекс вреда × Коэфф. категории

Консервативно (30% читают):
  0.30 × 0.101 × 0.8 = 2.4%

Среднее (40% читают):
  0.40 × 0.101 × 0.8 = 3.2%

Максимум (50% читают):
  0.50 × 0.101 × 0.8 = 4.0%
```

**→ Диапазон потерь CR: 2-4%** (округлено для простоты)

---

## 4. Шаг 3: Оценка объёма продаж

### Статистика: Review Rate (доля оставляющих отзывы)

**Данные по РФ маркетплейсам (2024-2025):**
- General e-commerce: 1-3%
- Электроника/техника: 5-7%
- FMCG/одежда: 0.5-1%
- **Функциональные товары (фонари, инструменты):** 3-5%

### Расчёт продаж:
```
145 отзывов / Review Rate = Покупки

Консервативно (5% оставляют отзыв):
  145 / 0.05 = 2,900 покупок за 13 мес
  ≈ 223 покупки/мес

Оптимистично (3% оставляют отзыв):
  145 / 0.03 = 4,833 покупки за 13 мес
  ≈ 372 покупки/мес
```

**→ Диапазон: 223-372 покупки/месяц**

---

## 5. Шаг 4: Денежные потери

### Месячный оборот:
```
Покупки/мес × Цена товара = Оборот

Минимум: 223 × 3,229₽ = 720,000₽/мес
Максимум: 372 × 3,229₽ = 1,201,000₽/мес

Среднее: ~960,000₽/мес
```

### Потери от плохих ответов:
```
Оборот × CR impact = Потери

Консервативно (2% CR loss):
  720,000₽ × 0.02 = 14,400₽/мес

Среднее (3% CR loss):
  960,000₽ × 0.03 = 28,800₽/мес

Максимум (4% CR loss):
  1,201,000₽ × 0.04 = 48,000₽/мес
```

**→ Потери: 15,000 - 50,000₽/месяц**

---

## 6. Валидация и ограничения

### ✅ Что мы знаем точно:
- 145 отзывов за 13 месяцев (факт из WBCON)
- Цена 3,229₽ (факт из WB Card API)
- Качество ответов 4/10 (LLM-анализ с примерами)
- 8 критичных + 66 рискованных ответов (классификация LLM)

### ⚠️ Что мы предполагаем:
- **Review Rate 3-5%** — оценка на основе industry benchmarks
- **40% покупателей читают отзывы** — среднее по маркетплейсам
- **CR impact 3-7%** — расчётная модель, не A/B тест

### ❌ Чего мы НЕ знаем:
- Реальное количество продаж (нет доступа к статистике продавца)
- Реальный Review Rate для этого товара
- Точный CR (conversion rate) товара
- Как плохие ответы влияют на решение купить (нет A/B теста)

---

## 7. Как улучшить точность оценки

### Для продавца:
1. **Предоставить статистику продаж** → точный Review Rate
2. **Данные о трафике и CR** → точное влияние отзывов
3. **A/B тест:** улучшить качество ответов на 50% товаров → измерить разницу CR

### Для платформы:
1. **Интеграция с WB Seller API** → автоматический импорт продаж и трафика
2. **ML-модель предсказания CR** на основе исторических данных
3. **Benchmark база** — средний Review Rate по категориям

---

## 8. Выводы

### Текущая оценка (артикул 282955222):
```
Качество ответов:      4/10 (плохо)
Индекс вреда:          10.1%
Потери конверсии:      ~2-4%
Денежные потери:       15,000 - 50,000₽/мес
Годовые потери:        180,000 - 600,000₽/год
```

### Критичные проблемы:
1. **8 ответов с обвинением/игнором** (5.5%) — максимальный вред репутации
2. **65 шаблонных ответов** (45%) — создают впечатление безразличия
3. **1 отзыв без ответа** на прямой вопрос о возврате — игнор клиента

### Потенциал улучшения:
При улучшении качества ответов с 4/10 до 7/10:
- Индекс вреда: 10.1% → ~3%
- CR impact: 2-4% → 1-2%
- **Возврат:** 20,000 - 30,000₽/мес дополнительной прибыли

---

## 9. Использование в коде

### Python (wbcon-task-to-card-v2.py):

```python
# Получить цену товара из WB Card API
def fetch_wb_card_info(nm_id: int) -> dict:
    """
    Fetch product card info from WB public API.
    Returns: {
        "price": int,  # в копейках
        "name": str,
        "category": str,
        ...
    }
    """
    basket_num = _wb_basket_num(nm_id)
    vol = nm_id // 100000
    part = nm_id // 1000
    url = f"https://basket-{basket_num}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"
    resp = requests.get(url, timeout=10)
    data = resp.json()

    # Извлечь цену из sizes[0].price (если есть)
    price_kopeks = data.get("sizes", [{}])[0].get("price", {}).get("basic", 0)
    price_rub = price_kopeks / 100 if price_kopeks else None

    return {
        "price": price_rub,
        "name": data.get("imt_name"),
        "category": data.get("subj_name"),
    }

# Расчёт денежных потерь
def calculate_money_loss(review_count: int, period_months: int, price_rub: float, quality_score: int) -> dict:
    """
    Calculate estimated money loss from poor communication quality.

    Args:
        review_count: Total reviews received
        period_months: Period in months
        price_rub: Product price in rubles
        quality_score: LLM quality score (1-10)

    Returns:
        {
            "purchases_per_month_min": int,
            "purchases_per_month_max": int,
            "revenue_per_month_min": int,
            "revenue_per_month_max": int,
            "loss_per_month_min": int,
            "loss_per_month_max": int,
        }
    """
    # Review rate assumptions (3-5% for functional products)
    review_rate_min = 0.03
    review_rate_max = 0.05

    # Calculate purchases
    total_purchases_min = int(review_count / review_rate_max)  # conservative
    total_purchases_max = int(review_count / review_rate_min)  # optimistic

    purchases_per_month_min = int(total_purchases_min / period_months)
    purchases_per_month_max = int(total_purchases_max / period_months)

    # Calculate revenue
    revenue_per_month_min = int(purchases_per_month_min * price_rub)
    revenue_per_month_max = int(purchases_per_month_max * price_rub)

    # CR impact based on quality score (inverse relationship)
    # Updated: risky weight = 1 (was 2), reduces harm index and CR impact
    cr_impact_min = 0.02  # 2% for quality 4-6
    cr_impact_max = 0.04  # 4% for quality 1-3

    if quality_score >= 7:
        cr_impact_min, cr_impact_max = 0.01, 0.02
    elif quality_score >= 4:
        cr_impact_min, cr_impact_max = 0.02, 0.04
    else:
        cr_impact_min, cr_impact_max = 0.03, 0.06

    # Calculate losses
    loss_per_month_min = int(revenue_per_month_min * cr_impact_min)
    loss_per_month_max = int(revenue_per_month_max * cr_impact_max)

    return {
        "purchases_per_month_min": purchases_per_month_min,
        "purchases_per_month_max": purchases_per_month_max,
        "revenue_per_month_min": revenue_per_month_min,
        "revenue_per_month_max": revenue_per_month_max,
        "loss_per_month_min": loss_per_month_min,
        "loss_per_month_max": loss_per_month_max,
    }
```

### Jinja2 template (report.html):

```jinja2
{% if data.money_loss %}
<div style="margin-top: 16px; padding: 12px; background: rgba(232, 168, 56, 0.08); border-left: 3px solid #e8a838; border-radius: 0 8px 8px 0;">
  <div style="font-size: 11px; color: #a8bcc8; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">Примерные денежные потери</div>
  <div style="font-size: 18px; font-weight: 700; color: #e8a838; margin-bottom: 4px;">
    {{ data.money_loss.loss_per_month_min|format_number }} - {{ data.money_loss.loss_per_month_max|format_number }}₽/месяц
  </div>
  <div style="font-size: 10px; color: #7a9bb5; line-height: 1.4;">
    На основе оценки ~{{ data.money_loss.purchases_per_month_min }}-{{ data.money_loss.purchases_per_month_max }} покупок/мес и цены товара {{ data.price }}₽
  </div>
</div>
{% endif %}
```

---

## 10. Disclaimer

**Эта оценка носит приблизительный характер и предназначена для:**
- Демонстрации бизнес-влияния плохого качества ответов
- Оценки потенциала улучшения коммуникации
- Приоритизации работы над качеством ответов

**Для точной оценки потерь требуется:**
- Доступ к реальной статистике продаж
- A/B тест (сравнение товаров с хорошими vs плохими ответами)
- Учёт других факторов (сезонность, конкуренты, реклама)

**Не используйте эту оценку для:**
- Финансовой отчётности
- Юридических споров
- Гарантированных прогнозов ROI
