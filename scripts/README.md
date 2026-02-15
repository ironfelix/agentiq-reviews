# Scripts

Вспомогательные скрипты для AgentIQ.

## ai_code_review.py

AI-powered code review с cross-model validation.

### Usage

```bash
# Local testing
python scripts/ai_code_review.py \
  --diff pr.diff \
  --author Claude \
  --pr-number 42

# Dual review (both models)
python scripts/ai_code_review.py \
  --diff pr.diff \
  --author Human \
  --pr-number 42 \
  --dual
```

### Environment Variables

Requires:
- `ANTHROPIC_API_KEY` — для Claude API
- `OPENAI_API_KEY` — для OpenAI API
- `GITHUB_TOKEN` — для posting comments (optional для local testing)
- `GITHUB_REPOSITORY` — repo name (e.g., `ironfelix/agentiq-reviews`)

### Review Strategy

| Code Author | Reviewer(s) | Why |
|-------------|------------|-----|
| Claude | o1-preview | Reasoning model finds edge cases |
| OpenAI (o1/gpt-4o) | Claude 4.6 Opus | Deep context understanding |
| Human | Both (dual) | Maximum coverage |

### Setup GitHub Secrets

For GitHub Actions to work, add these secrets to your repository:

**Settings → Secrets and variables → Actions → New repository secret:**

1. **ANTHROPIC_API_KEY**
   - Get from: https://console.anthropic.com/settings/keys
   - Example: `sk-ant-api03-...`

2. **OPENAI_API_KEY**
   - Get from: https://platform.openai.com/api-keys
   - Example: `sk-proj-...`

3. **VPS_SSH_KEY**
   - Your VPS private SSH key (for deployment)
   - Example: содержимое `ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem`

**GITHUB_TOKEN** создаётся автоматически и не требует настройки.

### Cost Tracking

Средняя стоимость per review:
- Single review: ~$0.09
- Dual review: ~$0.11

Для 50 PRs/месяц: **~$5/мес**

---

## Другие скрипты

### rebuild_all_reports.py
Перестроить все отчёты по отзывам.

### llm_analyzer.py
LLM анализ коммуникации (качество ответов).

### wbcon-task-to-card-v2.py
Создать карточку товара из WBCON feedbacks API.

---

## Development

### Install dependencies

```bash
pip install anthropic openai PyGithub
```

### Run locally

```bash
# Get diff
git diff main...feature-branch > test.diff

# Run review
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-proj-..."

python scripts/ai_code_review.py \
  --diff test.diff \
  --author Human \
  --pr-number 0 \
  --dual
```

Review output will be printed to console if GITHUB_TOKEN not set.
