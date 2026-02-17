#!/usr/bin/env python3
"""
generate-changelog.py

Генерирует docs/CHANGELOG.html из git-истории.
Показывает только продуктовые изменения (feat/fix/perf),
скрывает технические (ci/docs/chore/refactor/test).
Ориентирован на внешних пользователей — pilots, клиенты.

Использование:
  python scripts/generate-changelog.py
  python scripts/generate-changelog.py --since 2026-01-01
  python scripts/generate-changelog.py --output /var/www/agentiq/CHANGELOG.html
"""

from __future__ import annotations

import re
import sys
import subprocess
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, OrderedDict

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "docs" / "CHANGELOG.html"

# ── Категории для пользователей ───────────────────────────────────────────────
CATEGORIES: dict[str, tuple[str, str]] = {
    "feat":    ("Новые возможности", "#1a73e8"),
    "fix":     ("Исправления",       "#34a853"),
    "perf":    ("Стало быстрее",     "#f9ab00"),
    "improve": ("Улучшения",         "#1a73e8"),
    "ui":      ("Интерфейс",         "#9334e6"),
}

# Технические типы — скрываем от внешних пользователей
SKIP_TYPES = {"ci", "chore", "docs", "refactor", "test", "build", "style", "wip"}

# Если заголовок содержит эти слова — скрыть
SKIP_KEYWORDS = {"wip:", "todo:", "temp ", "tmp ", "merge branch", "revert "}

# Scope → понятный лейбл
SCOPE_LABELS: dict[str, str] = {
    "frontend":   "Интерфейс",
    "backend":    "Бэкенд",
    "celery":     "Фоновые задачи",
    "auth":       "Авторизация",
    "sync":       "Синхронизация",
    "chat":       "Чат",
    "analytics":  "Аналитика",
    "P0":         "Критическое",
    "landing":    "Сайт",
    "rate":       "Скорость API",
    "api":        "API",
    "inbox":      "Входящие",
    "ai":         "ИИ-помощник",
}

MONTHS_RU = {
    1: "января",  2: "февраля",  3: "марта",    4: "апреля",
    5: "мая",     6: "июня",     7: "июля",      8: "августа",
    9: "сентября",10: "октября", 11: "ноября",  12: "декабря",
}


# ── Git ───────────────────────────────────────────────────────────────────────

def git_log(since: str | None = None) -> list[dict]:
    cmd = [
        "git", "-C", str(ROOT), "log",
        "--format=%H%x00%ai%x00%s",
        "--no-merges",
    ]
    if since:
        cmd += [f"--since={since}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"git log failed: {e}", file=sys.stderr)
        return []

    commits = []
    for line in result.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\x00", 2)
        if len(parts) < 3:
            continue
        sha, date_str, subject = parts[0][:7], parts[1], parts[2].strip()
        try:
            dt = datetime.fromisoformat(date_str[:19])
        except ValueError:
            continue
        commits.append({"sha": sha, "dt": dt, "subject": subject})
    return commits


# ── Парсинг коммитов ──────────────────────────────────────────────────────────

def parse_commit(subject: str) -> dict | None:
    """
    Парсит заголовок в формате conventional commits.
    Возвращает None если коммит не нужен внешним пользователям.
    """
    subject_lower = subject.lower()

    # Быстрый фильтр по ключевым словам
    if any(kw in subject_lower for kw in SKIP_KEYWORDS):
        return None

    # Conventional commits: type(scope): description
    m = re.match(r"^(\w[\w-]*)(?:\(([^)]+)\))?(!)?:\s*(.+)$", subject)

    if not m:
        # Нет conventional prefix — пропускаем (не попадает во внешний changelog)
        return None

    type_, scope, breaking, desc = (
        m.group(1).lower(), m.group(2), bool(m.group(3)), m.group(4).strip()
    )

    if type_ in SKIP_TYPES:
        return None

    # Маппинг нестандартных типов
    if type_ not in CATEGORIES:
        type_ = "feat"

    return {
        "type":     type_,
        "scope":    scope,
        "desc":     _clean_desc(desc),
        "breaking": breaking,
    }


def _clean_desc(desc: str) -> str:
    """Делает описание читаемым для пользователя."""
    # Убираем технические детали в скобках (длиннее 15 символов)
    desc = re.sub(r"\s*\([^)]{15,}\)", "", desc)
    # Убираем стрелки с техническими цифрами вроде "15s→<1s"
    desc = re.sub(r"\d+s→[<>]?\d+[sm]s?", "", desc)
    desc = re.sub(r"\s+", " ", desc).strip()
    # Первая буква заглавная
    if desc:
        desc = desc[0].upper() + desc[1:]
    return desc


# ── Группировка ───────────────────────────────────────────────────────────────

def week_key(dt: datetime) -> str:
    """ISO год-неделя, пример: '2026-07'."""
    iso = dt.isocalendar()
    return f"{iso[0]}-{iso[1]:02d}"


def week_label(dt: datetime) -> str:
    """'10–16 февраля 2026'."""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.day}–{sunday.day} {MONTHS_RU[monday.month]} {monday.year}"
    else:
        return (
            f"{monday.day} {MONTHS_RU[monday.month]} – "
            f"{sunday.day} {MONTHS_RU[sunday.month]} {sunday.year}"
        )


def group_by_week(commits: list[dict]) -> OrderedDict[str, dict]:
    """
    Возвращает OrderedDict {week_key: {label, items_by_category}},
    отсортированный от новых к старым.
    """
    weeks: dict[str, dict] = defaultdict(lambda: {"label": "", "by_cat": defaultdict(list)})

    for c in commits:
        parsed = parse_commit(c["subject"])
        if parsed is None:
            continue
        key = week_key(c["dt"])
        weeks[key]["label"] = week_label(c["dt"])
        cat = parsed["type"]
        label = SCOPE_LABELS.get(parsed["scope"] or "", "")
        weeks[key]["by_cat"][cat].append({
            "desc":     parsed["desc"],
            "scope_label": label,
            "breaking": parsed["breaking"],
            "sha":      c["sha"],
        })

    return OrderedDict(
        sorted(weeks.items(), key=lambda x: x[0], reverse=True)
    )


# ── HTML генерация ────────────────────────────────────────────────────────────

def render_html(weeks: OrderedDict, generated_at: datetime) -> str:
    weeks_html = ""

    for week_k, week_data in weeks.items():
        cats_html = ""
        for cat_type, cat_label_color in CATEGORIES.items():
            items = week_data["by_cat"].get(cat_type, [])
            if not items:
                continue
            cat_name, cat_color = cat_label_color
            items_html = "".join(
                f"""<li class="cl-item{'  cl-item--breaking' if it['breaking'] else ''}">
                  {'<span class="cl-breaking">BREAKING</span> ' if it['breaking'] else ''}
                  {it['desc']}
                  {f'<span class="cl-scope">{it["scope_label"]}</span>' if it["scope_label"] else ''}
                </li>"""
                for it in items
            )
            cats_html += f"""
          <div class="cl-cat">
            <div class="cl-cat-title" style="color:{cat_color}">{cat_name}</div>
            <ul class="cl-list">{items_html}</ul>
          </div>"""

        if not cats_html:
            continue

        weeks_html += f"""
      <div class="cl-week">
        <div class="cl-week-header">
          <span class="cl-week-label">Неделя {week_data['label']}</span>
        </div>
        <div class="cl-week-body">{cats_html}
        </div>
      </div>"""

    if not weeks_html:
        weeks_html = '<p class="cl-empty">Нет продуктовых изменений за выбранный период.</p>'

    ts = generated_at.strftime("%d.%m.%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AgentIQ — История изменений</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --color-bg: #f8f9fa;
      --color-surface: #ffffff;
      --color-border: #e8eaed;
      --color-text: #202124;
      --color-text-secondary: #5f6368;
      --color-accent: #1a73e8;
      --color-success: #34a853;
      --color-warning: #f9ab00;
      --color-danger: #ea4335;
      --radius: 12px;
      --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 8px rgba(0,0,0,0.04);
    }}
    body {{
      font-family: 'Inter', sans-serif;
      font-size: 14px;
      line-height: 1.6;
      color: var(--color-text);
      background: var(--color-bg);
      padding: 0 16px 48px;
    }}
    .container {{
      max-width: 760px;
      margin: 0 auto;
    }}

    /* ── Header ── */
    .cl-header {{
      padding: 40px 0 32px;
      border-bottom: 1px solid var(--color-border);
      margin-bottom: 32px;
    }}
    .cl-header h1 {{
      font-size: 26px;
      font-weight: 700;
      color: var(--color-text);
      margin-bottom: 6px;
    }}
    .cl-header h1 span {{ color: var(--color-accent); }}
    .cl-subtitle {{
      color: var(--color-text-secondary);
      font-size: 14px;
    }}
    .cl-meta {{
      display: flex;
      align-items: center;
      gap: 16px;
      margin-top: 16px;
      font-size: 12px;
      color: var(--color-text-secondary);
    }}
    .cl-meta a {{
      color: var(--color-accent);
      text-decoration: none;
    }}
    .cl-meta a:hover {{ text-decoration: underline; }}

    /* ── Week card ── */
    .cl-week {{
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      margin-bottom: 16px;
      overflow: hidden;
    }}
    .cl-week-header {{
      padding: 14px 20px;
      border-bottom: 1px solid var(--color-border);
      background: #fafbfc;
    }}
    .cl-week-label {{
      font-weight: 600;
      font-size: 13px;
      color: var(--color-text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .cl-week-body {{
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}

    /* ── Category ── */
    .cl-cat-title {{
      font-weight: 600;
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .cl-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 6px;
    }}
    .cl-item {{
      padding-left: 16px;
      position: relative;
      color: var(--color-text);
      font-size: 14px;
    }}
    .cl-item::before {{
      content: '·';
      position: absolute;
      left: 4px;
      color: var(--color-text-secondary);
    }}
    .cl-item--breaking {{
      background: rgba(234,67,53,0.06);
      border-left: 3px solid var(--color-danger);
      border-radius: 4px;
      padding: 6px 12px 6px 12px;
    }}
    .cl-item--breaking::before {{ content: none; }}
    .cl-breaking {{
      display: inline-block;
      font-size: 10px;
      font-weight: 700;
      color: var(--color-danger);
      background: rgba(234,67,53,0.12);
      border-radius: 4px;
      padding: 1px 6px;
      margin-right: 6px;
      vertical-align: middle;
      letter-spacing: 0.05em;
    }}
    .cl-scope {{
      display: inline-block;
      font-size: 11px;
      color: var(--color-text-secondary);
      background: #f1f3f4;
      border-radius: 4px;
      padding: 1px 6px;
      margin-left: 8px;
      vertical-align: middle;
    }}
    .cl-empty {{
      color: var(--color-text-secondary);
      text-align: center;
      padding: 40px;
    }}

    /* ── Legend ── */
    .cl-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 24px;
      padding: 12px 16px;
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: 8px;
      font-size: 12px;
      color: var(--color-text-secondary);
    }}
    .cl-legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .cl-legend-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }}

    @media (max-width: 600px) {{
      .cl-header h1 {{ font-size: 20px; }}
      .cl-week-body {{ padding: 12px 14px; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="cl-header">
      <h1>Agent<span>IQ</span> — История изменений</h1>
      <p class="cl-subtitle">Что нового в продукте. Обновляется автоматически при каждом релизе.</p>
      <div class="cl-meta">
        <span>Обновлено: {ts}</span>
        <a href="docs-home.html">← Документация</a>
        <a href="/">← На сайт</a>
      </div>
    </div>

    <div class="cl-legend">
      <span>Условные обозначения:</span>
      <span class="cl-legend-item">
        <span class="cl-legend-dot" style="background:#1a73e8"></span>Новые возможности
      </span>
      <span class="cl-legend-item">
        <span class="cl-legend-dot" style="background:#34a853"></span>Исправления
      </span>
      <span class="cl-legend-item">
        <span class="cl-legend-dot" style="background:#f9ab00"></span>Стало быстрее
      </span>
      <span class="cl-legend-item">
        <span class="cl-scope" style="margin:0">Интерфейс</span>область изменений
      </span>
    </div>

{weeks_html}
  </div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AgentIQ CHANGELOG.html")
    parser.add_argument("--since",  default="2026-01-01", help="Show commits since date (YYYY-MM-DD)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output file path")
    args = parser.parse_args()

    print(f"Reading git log since {args.since}...")
    commits = git_log(since=args.since)
    print(f"  {len(commits)} total commits")

    weeks = group_by_week(commits)
    total_items = sum(
        len(items)
        for w in weeks.values()
        for items in w["by_cat"].values()
    )
    print(f"  {total_items} user-facing changes across {len(weeks)} weeks")

    html = render_html(weeks, generated_at=datetime.now())

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Written: {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
