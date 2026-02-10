#!/usr/bin/env python3
"""
Chat AI analyzer — takes chat conversations and generates proper AI analysis.
Uses DeepSeek API (OpenAI-compatible), same pattern as llm_analyzer.py.

Usage:
    python scripts/analyze_chats.py [--html path/to/chat-center-real-data.html] [--dry-run]

Reads chatHistory from contextData in HTML, sends each chat to LLM,
writes updated AI fields back into the HTML.
"""

import json
import os
import re
import sys
import time
from typing import Optional

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

MODEL = "deepseek-chat"
MAX_RETRIES = 2

_client = None


def _get_client():
    global _client
    if _client is None:
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package not installed. Run: pip install openai")
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not set")
        _client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    return _client


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> Optional[str]:
    try:
        cl = _get_client()
    except RuntimeError as e:
        print(f"[LLM] Client init failed: {e}")
        return None

    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = cl.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            print(f"[LLM] Attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
    return None


# ── Prompt ──────────────────────────────────────────────────────

CHAT_SYSTEM = """Ты — эксперт по коммуникации продавца с покупателями на Wildberries.

Задача: проанализировать ПЕРЕПИСКУ В ЧАТЕ между покупателем и продавцом, и дать рекомендацию.

ПРАВИЛА АНАЛИЗА:
1. Читай ВСЮ переписку целиком, учитывай контекст КАЖДОГО сообщения.
2. Определи РЕАЛЬНУЮ проблему клиента (не цепляйся за ключевые слова).
3. Sentiment определяй по ТОНУ клиента: "!!!", "где товар???", "имейте совесть" = Негативная.
4. Urgency = Высокая если: клиент злится, много непрочитанных, проблема критичная (брак, пересорт, деньги).
5. AI Рекомендация — ГОТОВЫЙ ТЕКСТ ответа от лица продавца (2-3 предложения).
6. Рекомендация должна ТОЧНО соответствовать проблеме клиента.

КРИТИЧЕСКИ ВАЖНО:
- НИКОГДА не обещать: возврат денег, замену, компенсацию, конкретные сроки доставки.
- Предлагать возврат через ЛК WB ТОЛЬКО если покупатель сам просит вернуть/обменять.
- Если клиент спрашивает про доставку — НЕ обещать сроки, сказать что проверили статус.
- Если клиент жалуется на пересорт/несоответствие — признать проблему, НЕ игнорировать.
- Если чат уже обработан (продавец ответил адекватно) — так и напиши.
- НИКОГДА не упоминать: «ИИ», «бот», «нейросеть», «автоматический ответ».

ТИПЫ ПРОБЛЕМ (categories):
- "Доставка" — задержка, статус, где товар
- "Брак / дефект" — сломано, не работает
- "Пересорт" — прислали не тот товар
- "Не подошёл товар" — размер, модель не та
- "Возврат" — клиент хочет вернуть
- "Отмена заказа" — клиент хочет отменить
- "Гарантия" — вопросы по гарантии
- "Вопрос о товаре" — характеристики, совместимость
- "Помощь с использованием" — как установить, настроить
- "Благодарность" — клиент доволен
- "Ошибочный заказ" — клиент не заказывал"""

CHAT_USER = """Проанализируй чат-переписку.

Клиент: {client_name}
Товар: {product_name}
Непрочитанных: {unread}

Переписка:
{chat_text}

Верни СТРОГО JSON (без markdown, без ```):
{{
  "sentiment": {{
    "label": "Позитивная|Нейтральная|Негативная",
    "negative": true/false
  }},
  "categories": ["категория1", "категория2"],
  "urgency": {{
    "label": "Высокая · причина|Средняя · причина|Низкая · причина",
    "urgent": true/false
  }},
  "recommendation": "Что делать продавцу (кратко)",
  "aiSuggestion": "ГОТОВЫЙ ТЕКСТ ответа от лица продавца. 2-3 предложения. Если чат уже обработан и ответ продавца адекватный — напиши 'Чат обработан. Мониторинг.'"
}}"""


# ── Guardrails ──────────────────────────────────────────────────

BANNED_PHRASES = [
    "вернём деньги", "вернем деньги", "гарантируем возврат",
    "гарантируем замену", "полный возврат", "бесплатную замену",
    "вы неправильно", "вы не так", "ваша вина", "сами виноваты",
    "ИИ", "бот", "нейросет", "GPT", "ChatGPT", "автоматический ответ",
]


def sanitize(text: str) -> str:
    if not text:
        return text
    for phrase in BANNED_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    return text.strip()


# ── Extract chats from HTML ─────────────────────────────────────

def extract_context_data(html_path: str) -> dict:
    """Extract contextData JS object from HTML file."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Find contextData block
    match = re.search(r"const\s+contextData\s*=\s*\{", content)
    if not match:
        raise ValueError("contextData not found in HTML")

    start = match.start()
    # Find matching closing brace
    brace_count = 0
    i = match.end() - 1  # position of opening {
    for i in range(match.end() - 1, len(content)):
        if content[i] == '{':
            brace_count += 1
        elif content[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                break

    js_block = content[match.end()-1:i+1]

    # Convert JS object to valid JSON-ish — we'll parse it differently
    # Since it's complex JS with single quotes, we parse key fields manually
    return _parse_chats_from_js(js_block, content, start, i+1)


def _parse_chats_from_js(js_block: str, full_content: str, ctx_start: int, ctx_end: int):
    """Parse chat data from JS contextData block."""
    chats = {}

    # Find each chat ID block: '1': { ... }
    chat_pattern = re.compile(r"'(\d+)':\s*\{")
    for m in chat_pattern.finditer(js_block):
        chat_id = m.group(1)

        # Find this chat's data boundaries
        start_pos = m.end() - 1
        brace_count = 0
        end_pos = start_pos
        for j in range(start_pos, len(js_block)):
            if js_block[j] == '{':
                brace_count += 1
            elif js_block[j] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = j
                    break

        chat_block = js_block[start_pos:end_pos+1]

        # Extract fields
        chat = {
            'id': chat_id,
            'client_name': _extract_field(chat_block, 'title'),
            'product_name': _extract_field(chat_block, 'name') or 'Не определён',
            'article': _extract_field(chat_block, 'article'),
            'unread': _extract_field(chat_block, 'unread') or '0',
            'messages': _extract_messages(chat_block),
            'has_seller_reply': 'seller' in chat_block and "'type': 'seller'" in chat_block.replace('"', "'"),
        }
        chats[chat_id] = chat

    return chats, full_content, ctx_start, ctx_end


def _extract_field(block: str, field_name: str) -> Optional[str]:
    """Extract a simple string field from JS object."""
    patterns = [
        rf"{field_name}:\s*'([^']*)'",
        rf"{field_name}:\s*\"([^\"]*)\"",
    ]
    for p in patterns:
        m = re.search(p, block)
        if m:
            val = m.group(1)
            return val if val != 'null' else None
    return None


def _extract_messages(block: str) -> list:
    """Extract chatHistory messages from JS block."""
    messages = []

    # Find chatHistory array
    hist_match = re.search(r"chatHistory:\s*\[", block)
    if not hist_match:
        return messages

    # Find matching ]
    bracket_start = hist_match.end() - 1
    bracket_count = 0
    bracket_end = bracket_start
    for j in range(bracket_start, len(block)):
        if block[j] == '[':
            bracket_count += 1
        elif block[j] == ']':
            bracket_count -= 1
            if bracket_count == 0:
                bracket_end = j
                break

    hist_block = block[bracket_start+1:bracket_end]

    # Extract each message object
    msg_pattern = re.compile(r"\{\s*type:\s*'(\w+)'")
    for m in msg_pattern.finditer(hist_block):
        msg_type = m.group(1)
        # Find this message's closing brace
        msg_start = m.start()
        bc = 0
        msg_end = msg_start
        for j in range(msg_start, len(hist_block)):
            if hist_block[j] == '{':
                bc += 1
            elif hist_block[j] == '}':
                bc -= 1
                if bc == 0:
                    msg_end = j
                    break

        msg_block = hist_block[msg_start:msg_end+1]

        if msg_type == 'date':
            text = _extract_field(msg_block, 'text') or ''
            messages.append(f"[{text}]")
        elif msg_type in ('customer', 'seller'):
            author = _extract_field(msg_block, 'author') or msg_type
            text = _extract_field(msg_block, 'text') or ''
            time_val = _extract_field(msg_block, 'time') or ''
            if text:
                messages.append(f"{author} ({time_val}): {text}")

    return messages


# ── Analyze single chat ─────────────────────────────────────────

def analyze_chat(chat: dict) -> Optional[dict]:
    """Send chat to LLM, get structured analysis."""
    chat_text = "\n".join(chat['messages']) if chat['messages'] else "(пустой чат)"

    user_prompt = CHAT_USER.format(
        client_name=chat['client_name'] or 'Клиент',
        product_name=chat['product_name'],
        unread=chat['unread'],
        chat_text=chat_text,
    )

    raw = _call_llm(CHAT_SYSTEM, user_prompt, max_tokens=512)
    if not raw:
        return None

    # Clean markdown wrappers
    raw = re.sub(r'^```json\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                print(f"  [WARN] Failed to parse JSON for chat {chat['id']}")
                return None
        else:
            print(f"  [WARN] No JSON found for chat {chat['id']}")
            return None

    # Sanitize
    if 'aiSuggestion' in result:
        result['aiSuggestion'] = sanitize(result['aiSuggestion'])

    return result


# ── Update HTML ─────────────────────────────────────────────────

def update_html(html_path: str, results: dict, dry_run: bool = False):
    """Update AI fields in contextData within the HTML file."""
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()

    for chat_id, analysis in results.items():
        if not analysis:
            continue

        # Update aiSuggestion
        ai_suggestion = analysis.get('aiSuggestion', '')
        content = _replace_field_in_chat(content, chat_id, 'aiSuggestion', f"'{_escape_js(ai_suggestion)}'")

        # Update ai object fields
        sentiment = analysis.get('sentiment', {})
        categories = analysis.get('categories', [])
        urgency = analysis.get('urgency', {})
        recommendation = analysis.get('recommendation', '')

        # Build new ai object
        sentiment_label = sentiment.get('label', 'Нейтральная')
        sentiment_negative = 'true' if sentiment.get('negative', False) else 'false'
        cats_str = ', '.join(f"'{c}'" for c in categories)
        urgency_label = urgency.get('label', 'Средняя')
        urgency_urgent = 'true' if urgency.get('urgent', False) else 'false'

        new_ai = (
            f"{{ sentiment: {{ label: '{_escape_js(sentiment_label)}', negative: {sentiment_negative} }}, "
            f"categories: [{cats_str}], "
            f"urgency: {{ label: '{_escape_js(urgency_label)}', urgent: {urgency_urgent} }}, "
            f"recommendation: '{_escape_js(recommendation)}' }}"
        )

        content = _replace_field_in_chat(content, chat_id, 'ai', new_ai)

    if dry_run:
        print("\n[DRY RUN] Would write updated HTML. Showing first result as sample.")
        first_id = next(iter(results))
        if results[first_id]:
            print(json.dumps(results[first_id], indent=2, ensure_ascii=False))
    else:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n[OK] Updated {html_path}")


def _escape_js(s: str) -> str:
    """Escape string for JS single-quoted string."""
    return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _replace_field_in_chat(content: str, chat_id: str, field: str, new_value: str) -> str:
    """Replace a field value in a specific chat's contextData entry."""
    # Find the chat block by its ID
    chat_start_pattern = rf"'{chat_id}':\s*\{{"
    chat_match = re.search(chat_start_pattern, content)
    if not chat_match:
        return content

    # Search for the field within this chat block (limited scope)
    search_start = chat_match.end()

    if field == 'aiSuggestion':
        # aiSuggestion: 'text here',
        field_pattern = rf"(aiSuggestion:\s*)'(?:[^'\\]|\\.)*'"
        m = re.search(field_pattern, content[search_start:search_start+2000])
        if m:
            old = content[search_start + m.start():search_start + m.end()]
            new = f"{m.group(1)}{new_value}"
            content = content[:search_start + m.start()] + new + content[search_start + m.end():]
    elif field == 'ai':
        # ai: { ... }
        field_pattern = r"ai:\s*\{"
        m = re.search(field_pattern, content[search_start:search_start+3000])
        if m:
            # Find matching closing brace
            pos = search_start + m.end() - 1
            bc = 0
            end_pos = pos
            for j in range(pos, min(pos + 1000, len(content))):
                if content[j] == '{':
                    bc += 1
                elif content[j] == '}':
                    bc -= 1
                    if bc == 0:
                        end_pos = j
                        break
            old_ai_start = search_start + m.start()
            content = content[:old_ai_start] + f"ai: {new_value}" + content[end_pos+1:]

    return content


# ── Main ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Analyze chat conversations with LLM")
    parser.add_argument("--html", default="docs/chat-center/chat-center-real-data.html",
                        help="Path to HTML file with contextData")
    parser.add_argument("--dry-run", action="store_true", help="Don't modify HTML, just print results")
    parser.add_argument("--chat-id", type=str, help="Analyze only specific chat ID")
    args = parser.parse_args()

    # Resolve path
    html_path = args.html
    if not os.path.isabs(html_path):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        html_path = os.path.join(project_dir, html_path)

    print(f"[*] Reading chats from: {html_path}")
    chats, full_content, ctx_start, ctx_end = extract_context_data(html_path)
    print(f"[*] Found {len(chats)} chats")

    if args.chat_id:
        if args.chat_id not in chats:
            print(f"[ERROR] Chat ID {args.chat_id} not found")
            sys.exit(1)
        chats = {args.chat_id: chats[args.chat_id]}

    results = {}
    for chat_id, chat in sorted(chats.items(), key=lambda x: int(x[0])):
        msgs_count = len([m for m in chat['messages'] if not m.startswith('[')])
        print(f"  Chat #{chat_id}: {chat['client_name']} — {msgs_count} msgs, product: {chat['product_name']}")

        analysis = analyze_chat(chat)
        if analysis:
            sent = analysis.get('sentiment', {}).get('label', '?')
            cats = ', '.join(analysis.get('categories', []))
            urgent = '🔴' if analysis.get('urgency', {}).get('urgent') else '⚪'
            suggestion_preview = (analysis.get('aiSuggestion', '')[:80] + '...') if len(analysis.get('aiSuggestion', '')) > 80 else analysis.get('aiSuggestion', '')
            print(f"    {urgent} Sentiment: {sent} | Categories: {cats}")
            print(f"    → {suggestion_preview}")
        else:
            print(f"    [SKIP] LLM returned no result")

        results[chat_id] = analysis
        time.sleep(0.5)  # rate limit

    success = sum(1 for v in results.values() if v)
    print(f"\n[*] Analyzed: {success}/{len(chats)} chats")

    if success > 0:
        update_html(html_path, results, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
