# AgentIQ — Lifecycle Communication Strategy Pages

Интерактивные прототипы и документация по customer lifecycle коммуникациям для WB.

## 📄 Страницы

### 1. [index.html](index.html) — Главная страница
Лендинг с описанием двух основных ресурсов:
- Dashboard (интерактивный прототип)
- Scenarios (документация)
- Live метрики: +20% конверсия, 58% win rate, 7.2x ROI, 315k₽/мес

### 2. [lifecycle-dashboard.html](lifecycle-dashboard.html) — Interactive Dashboard
**Интерактивный UI прототип** для управления lifecycle сценариями:

**Компоненты:**
- **Live Stats** — 4 анимированных метрики (конверсия вопросов, win rate, upsell, ROI)
- **Charts** — Line chart (конверсия по сценариям), Doughnut chart (распределение по lifecycle этапам)
- **Scenario Cards** — 8 сценариев с метриками и статусами:
  - 🔴 Critical: Спасение негатива, Вопрос→Конверсия, Churn Prevention
  - 🟢 High ROI: Upsell на 5★, Апгрейд 3★
  - 🟡 Medium: Проактивная активация 48h, VIP Advocacy, Win-back
- **Active Message Chains** — 12 активных цепочек с прогресс-барами
- **Automation Settings** — 6 настроек автоматизации (toggle switches + inputs)

**Технологии:**
- Chart.js для графиков
- Vanilla JS (анимированные счетчики, фильтры)
- Светлая тема (дизайн Chat Center)
- Responsive (mobile/tablet/desktop)

**Фильтры:**
- Все / Critical / High ROI / Medium
- Client-side filtering по data-атрибутам

### 3. [scenarios.html](scenarios.html) — Detailed Documentation
**Полная документация** сценариев коммуникаций:

**Секции:**
1. **Hero Stats** — 4 ключевые метрики WB
2. **AARRR Framework** — 5 этапов lifecycle:
   - Acquisition (вопросы → покупки)
   - Activation (первые 24-48h после доставки)
   - Retention (review management 1-3★)
   - Revenue (upsell/cross-sell на 5★)
   - Referral (VIP advocacy программа)
3. **7 детальных сценариев** — с flow-диаграммами, метриками, ROI, экспертными инсайтами
4. **Классификаторы** — intent, emotion, priority (12 intent классов, 7 эмоций, 4 SLA уровня)
5. **Продвинутые тактики**:
   - Predictive churn scoring
   - Optimal send-time prediction
   - Message chain optimization
   - Cohort analysis (first-time, repeat, VIP, at-risk, churned)
   - Cross-channel orchestration
   - Dynamic response templates
6. **ROI таблица** — по всем сценариям
7. **Roadmap** — 4 фазы внедрения (Foundation → Automation → Intelligence → Orchestration)
8. **Метрики Dashboard** — operational, business, ROI метрики
9. **Customer Journey Flow** — Mermaid диаграмма
10. **10 Expert Insights** — от lifecycle expert

**Дизайн:**
- Тёмная тема (Reviews App style: #0a1018, #e8a838)
- Mermaid.js для диаграмм
- Анимации fadeIn
- Интерактивные элементы

## 🎯 Цель проекта

Построить **полноценную CRM-систему lifecycle коммуникаций** для WB-селлеров:
- Автоматизация сценариев (платный чат, upsell, churn prevention)
- Predictive analytics (churn scoring, send-time optimization)
- ROI tracking по каждому сценарию
- Интеграция с WB Chat API + Questions API + Feedbacks API

## 📊 Ключевые метрики

| Метрика | Значение | Источник |
|---------|----------|----------|
| Конверсия вопрос→покупка при ответе <1h | **+20%** | Офиц. данные WB |
| Win Rate 1★→4-5★ через платный чат | **40-60%** | Industry benchmarks |
| Upsell conversion на 5★ | **12-18%** | E-commerce best practices |
| ROI коммуникаций | **2-10x** | Зависит от сценария |
| Стоимость платной отсрочки негатива | **315k₽/мес** | При 10M обороте, комиссия +1.75-3.15% |

## 🚀 Как открыть

### Локально:
```bash
# Открыть главную
open /Users/ivanilin/Documents/ivanilin/agentiq/pages/index.html

# Или Dashboard напрямую
open /Users/ivanilin/Documents/ivanilin/agentiq/pages/lifecycle-dashboard.html

# Или документацию
open /Users/ivanilin/Documents/ivanilin/agentiq/pages/scenarios.html
```

### На GitHub Pages:
1. Положить содержимое `pages/` в корень ветки `gh-pages`
2. Настроить GitHub Pages в Settings → Pages
3. URL: `https://<username>.github.io/agentiq/`

### На VPS (agentiq.ru):
```bash
# Залить на сервер
rsync -avz -e "ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem" \
  pages/ ubuntu@79.137.175.164:/var/www/agentiq/pages/

# Доступ
https://agentiq.ru/pages/
https://agentiq.ru/pages/lifecycle-dashboard.html
https://agentiq.ru/pages/scenarios.html
```

## 📁 Структура файлов

```
pages/
├── index.html                    # Главная страница (лендинг)
├── lifecycle-dashboard.html      # Интерактивный Dashboard UI
├── scenarios.html                # Документация сценариев
└── README.md                     # Этот файл
```

## 🎨 Дизайн-система

### Dashboard (светлая тема)
- Фон: `#f5f7fa`
- Карточки: `#ffffff`
- Акцент: `#1a73e8` (синий)
- Успех: `#16a34a`, Ошибка: `#dc2626`, Предупреждение: `#f59e0b`
- Шрифт: Inter

### Scenarios (тёмная тема)
- Фон: `#0a1018`
- Карточки: `#141e2b`
- Акцент: `#e8a838` (оранжевый)
- Шрифт: Segoe UI

## 🔗 Связанные документы

- `docs/chat-center/WB_CHAT_API_RESEARCH.md` — исследование WB Chat API, секция 13 (чат меняет рейтинг)
- `docs/QUALITY_SCORE_FORMULA.md` — формула расчёта quality_score
- `docs/reviews/RESPONSE_GUARDRAILS.md` — правила ответов
- `mvp/PROJECT_SUMMARY.md` — архитектура проекта

---

**Автор:** AgentIQ Strategy Team
**Дата:** Февраль 2026
**Версия:** 1.0
