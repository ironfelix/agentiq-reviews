#!/usr/bin/env python3
"""
check-docs-freshness.py

Проверяет актуальность ключевых документов AgentIQ:
  - Дата в docs-home.html не старше WARN_AFTER_DAYS дней
  - Дата в MVP_READINESS_STATUS.md не старше WARN_AFTER_DAYS дней
  - Запрещённые устаревшие цифры (win rate 40-60%, 58%) отсутствуют
  - INBOX.md и BACKLOG обновлялись недавно (предупреждение)

Использование:
  python scripts/check-docs-freshness.py          # обычная проверка
  python scripts/check-docs-freshness.py --strict  # fail если дата != сегодня

Выход 0 = всё ок, 1 = есть проблемы.
"""

from __future__ import annotations

import re
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WARN_AFTER_DAYS = 7   # предупреждать если документ не обновлялся N дней

# ── ANSI цвета ────────────────────────────────────────────────────────────────
OK   = "\033[32m✓\033[0m"
WARN = "\033[33m⚠\033[0m"
FAIL = "\033[31m✗\033[0m"

issues: list[str] = []
warnings: list[str] = []


def ok(label: str) -> None:
    print(f"  {OK}  {label}")


def fail(label: str, msg: str) -> None:
    print(f"  {FAIL}  {label}: {msg}")
    issues.append(label)


def warn(label: str, msg: str) -> None:
    print(f"  {WARN}  {label}: {msg}")
    warnings.append(label)


def extract_first_date(text: str, pattern: str = r"(\d{4}-\d{2}-\d{2})") -> date | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except ValueError:
        return None


def check_date(label: str, d: date | None, strict: bool) -> None:
    today = date.today()
    if d is None:
        fail(label, "дата не найдена")
        return
    age = (today - d).days
    threshold = 0 if strict else WARN_AFTER_DAYS
    if age > threshold:
        fail(label, f"{d} ({age}d назад, порог: {threshold}d)")
    else:
        ok(f"{label}: {d} ({age}d назад)")


# ── Запрещённые устаревшие цифры ─────────────────────────────────────────────
BANNED_PATTERNS: list[tuple[str, str, str]] = [
    # (описание, паттерн для re.search, объяснение)
    ("win rate 40-60%", r"40-60%\s*win rate|win rate.*?40-60%", "должно быть 15-30%"),
    ("win rate 58%",    r"58%\s*win rate|win rate.*?58%",       "должно быть 15-30%"),
    ("passlib import",  r"from passlib",                        "passlib удалён, используй bcrypt напрямую"),
    ("create_all()",    r"metadata\.create_all",                "create_all() убран из startup, схема через Alembic"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentIQ docs freshness check")
    parser.add_argument("--strict", action="store_true",
                        help="Fail if any date is not today (не только старше 7 дней)")
    args = parser.parse_args()

    today = date.today()
    print(f"\nAgentIQ Docs Freshness Check — {today}\n")

    # ── 1. docs-home.html ─────────────────────────────────────────────────────
    print("1. docs/docs-home.html")
    path = ROOT / "docs/docs-home.html"
    if not path.exists():
        fail("docs-home.html существует", "файл не найден")
    else:
        text = path.read_text(encoding="utf-8")
        d = extract_first_date(text, r"Last updated:\s*(\d{4}-\d{2}-\d{2})")
        check_date("Last updated", d, args.strict)

        # Запрещённые цифры именно в этом файле
        for label, pattern, hint in BANNED_PATTERNS[:2]:
            found = bool(re.search(pattern, text, re.IGNORECASE))
            if found:
                fail(f'Нет устаревшей цифры "{label}"', hint)
            else:
                ok(f'Нет устаревшей цифры "{label}"')

    # ── 2. MVP_READINESS_STATUS.md ────────────────────────────────────────────
    print("\n2. docs/product/MVP_READINESS_STATUS.md")
    path = ROOT / "docs/product/MVP_READINESS_STATUS.md"
    if not path.exists():
        fail("MVP_READINESS_STATUS.md существует", "файл не найден")
    else:
        text = path.read_text(encoding="utf-8")
        d = extract_first_date(text, r"\*\*Дата:\*\*\s*(\d{4}-\d{2}-\d{2})")
        check_date("Дата", d, args.strict)

    # ── 3. INBOX.md ───────────────────────────────────────────────────────────
    print("\n3. docs/bugs/INBOX.md")
    path = ROOT / "docs/bugs/INBOX.md"
    if not path.exists():
        warn("INBOX.md существует", "файл не найден")
    else:
        text = path.read_text(encoding="utf-8")
        d = extract_first_date(text)
        if d:
            age = (today - d).days
            if age > WARN_AFTER_DAYS:
                warn("INBOX последняя запись", f"{d} ({age}d назад) — возможно стоит обновить")
            else:
                ok(f"INBOX последняя запись: {d} ({age}d назад)")
        else:
            warn("INBOX дата", "дата не найдена")

    # ── 4. BACKLOG ────────────────────────────────────────────────────────────
    print("\n4. docs/product/BACKLOG_UNIFIED_COMM_V3.md")
    path = ROOT / "docs/product/BACKLOG_UNIFIED_COMM_V3.md"
    if not path.exists():
        warn("BACKLOG_UNIFIED_COMM_V3.md существует", "файл не найден")
    else:
        text = path.read_text(encoding="utf-8")
        d = extract_first_date(text)
        if d:
            age = (today - d).days
            if age > WARN_AFTER_DAYS:
                warn("BACKLOG последняя запись", f"{d} ({age}d назад)")
            else:
                ok(f"BACKLOG последняя запись: {d} ({age}d назад)")
        else:
            warn("BACKLOG дата", "дата не найдена")

    # ── 5. Запрещённые цифры во всех docs/ ───────────────────────────────────
    print("\n5. Fact-check (запрещённые устаревшие цифры во всех docs/)")
    def _py_files(base: Path) -> list[Path]:
        """Python files, excluding venv and __pycache__."""
        return [
            p for p in base.rglob("*.py")
            if "venv" not in p.parts and "__pycache__" not in p.parts
        ]

    docs_files    = list((ROOT / "docs").rglob("*.html")) + \
                    list((ROOT / "docs").rglob("*.md"))
    # Only our application code, not venv or test fixtures
    app_code      = _py_files(ROOT / "apps/chat-center/backend/app") + \
                    _py_files(ROOT / "apps/reviews/backend")

    all_files_by_check = {
        "win rate 40-60%": docs_files,
        "win rate 58%":    docs_files,
        "passlib import":  app_code,   # venv excluded
        "create_all()":    [           # only main.py — the risky call site
            ROOT / "apps/chat-center/backend/app/main.py",
        ],
    }

    for label, pattern, hint in BANNED_PATTERNS:
        target_files = all_files_by_check.get(label, docs_files)
        hits: list[str] = []
        for p in target_files:
            try:
                t = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if re.search(pattern, t, re.IGNORECASE):
                hits.append(str(p.relative_to(ROOT)))
        if hits:
            fail(f'Нет "{label}"', hint + "\n         " + "\n         ".join(hits))
        else:
            ok(f'Нет "{label}" ни в одном файле')

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    if warnings:
        for w in warnings:
            print(f"  {WARN}  {w}")

    if issues:
        print(f"\n{FAIL}  FAIL — {len(issues)} проблема(ы):\n")
        for i in issues:
            print(f"     • {i}")
        print(f"\n  Подсказка: запусти с --strict для строгой проверки дат.\n")
        sys.exit(1)
    else:
        print(f"{OK}  Документация актуальна ({len(warnings)} предупреждений)\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
