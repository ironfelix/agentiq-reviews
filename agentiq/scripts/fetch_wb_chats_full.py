#!/usr/bin/env python3
"""
Скрипт для загрузки полной истории чатов через WB Chat API.

Endpoints:
  - GET /api/v1/seller/chats — список чатов
  - GET /api/v1/seller/events — все сообщения (cursor-пагинация)

Результат: /tmp/wb_chats_full.json — полные данные для chat-center-real-data.html
"""

import requests
import json
import time
import os
from datetime import datetime, timezone
from collections import defaultdict

# === CONFIG ===
BASE_URL = "https://buyer-chat-api.wildberries.ru"

# Загружаем токен из .env.wb-tokens
ENV_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "apps", "chat-center", "backend", ".env.wb-tokens"
)

def load_token():
    """Читаем WB_TOKEN_PRODUCTION из .env.wb-tokens"""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line.startswith("WB_TOKEN_PRODUCTION="):
                    return line.split("=", 1)[1]
    # Fallback: env variable
    return os.environ.get("WB_TOKEN_PRODUCTION", "")


TOKEN = load_token()
if not TOKEN:
    print("ERROR: WB_TOKEN_PRODUCTION not found!")
    print(f"Checked: {os.path.abspath(ENV_PATH)}")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

OUTPUT_FILE = "/tmp/wb_chats_full.json"
RATE_LIMIT_DELAY = 2.0  # секунды между запросами (rate limit ~1 req/sec)


# === STEP 1: Fetch chats ===
def fetch_chats():
    """GET /api/v1/seller/chats"""
    print("=" * 60)
    print("STEP 1: Fetching chat list...")
    print("=" * 60)

    resp = requests.get(
        f"{BASE_URL}/api/v1/seller/chats",
        headers=HEADERS,
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    chats = data.get("chats", [])
    print(f"  Chats found: {len(chats)}")

    for c in chats:
        print(f"  - {c.get('clientName', '?')} (ID: {c.get('chatID', '?')[:20]}...)")

    return chats


# === STEP 2: Fetch ALL events with cursor pagination ===
def fetch_all_events():
    """GET /api/v1/seller/events with cursor pagination"""
    print("\n" + "=" * 60)
    print("STEP 2: Fetching all events (messages)...")
    print("=" * 60)

    all_events = []
    cursor = None
    iteration = 0
    max_iterations = 200  # safety limit
    seen_event_ids = set()  # dedup

    while iteration < max_iterations:
        iteration += 1
        params = {"next": cursor} if cursor else {}

        # Retry logic for timeouts
        resp = None
        for attempt in range(3):
            try:
                resp = requests.get(
                    f"{BASE_URL}/api/v1/seller/events",
                    headers=HEADERS,
                    params=params,
                    timeout=30
                )
                resp.raise_for_status()
                break
            except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError) as e:
                print(f"  [Iter {iteration}] Attempt {attempt+1}/3 failed: {e}")
                if attempt < 2:
                    time.sleep(3)
                else:
                    print("  -> All retries failed, saving partial results.")
                    return all_events, cursor

        data = resp.json()
        result = data.get("result", {})
        events = result.get("events", [])
        new_cursor = result.get("next")
        total_in_response = result.get("totalEvents", 0)

        # Dedup
        new_events = []
        for e in events:
            eid = e.get("eventID", "")
            if eid and eid not in seen_event_ids:
                seen_event_ids.add(eid)
                new_events.append(e)

        all_events.extend(new_events)
        print(f"  [Iter {iteration}] Got {len(events)} events "
              f"({len(new_events)} new), total: {len(all_events)}, cursor: {new_cursor}")

        # Stop conditions
        if not events or total_in_response == 0:
            print("  -> No more events, stopping.")
            break

        if new_cursor == cursor:
            print("  -> Cursor unchanged, stopping.")
            break

        cursor = new_cursor
        time.sleep(RATE_LIMIT_DELAY)

    print(f"\n  Total unique events: {len(all_events)}")
    return all_events, cursor


# === STEP 3: Group events by chat ===
def group_by_chat(events, chats_list):
    """Group events by chatID, enrich with chat metadata"""
    print("\n" + "=" * 60)
    print("STEP 3: Grouping messages by chat...")
    print("=" * 60)

    # Chat metadata from /chats endpoint
    chat_meta = {}
    for c in chats_list:
        chat_meta[c["chatID"]] = {
            "clientName": c.get("clientName", ""),
            "clientID": c.get("clientID", ""),
            "lastMessageTime": c.get("lastMessageTime", "")
        }

    # Group events
    messages_by_chat = defaultdict(list)
    for e in events:
        chat_id = e.get("chatID", "")
        if not chat_id:
            continue

        msg = {
            "eventID": e.get("eventID", ""),
            "sender": e.get("sender", ""),
            "text": e.get("message", {}).get("text", ""),
            "files": e.get("message", {}).get("files", []),
            "addTimestamp": e.get("addTimestamp", 0),
            "addTime": e.get("addTime", ""),
            "clientName": e.get("clientName", ""),
            "clientID": e.get("clientID", ""),
            "isNewChat": e.get("isNewChat", False),
        }
        messages_by_chat[chat_id].append(msg)

    # Sort messages within each chat by timestamp
    for chat_id in messages_by_chat:
        messages_by_chat[chat_id].sort(key=lambda m: m.get("addTimestamp", 0))

    # Build final structure
    chats_full = []
    for chat_id, messages in messages_by_chat.items():
        meta = chat_meta.get(chat_id, {})
        client_name = meta.get("clientName", "") or (
            messages[0].get("clientName", "") if messages else ""
        )

        # Determine last message
        last_msg = messages[-1] if messages else {}
        last_sender = last_msg.get("sender", "")
        last_text = last_msg.get("text", "")

        # Count unread (messages from client after last seller message)
        unread = 0
        for m in reversed(messages):
            if m["sender"] == "client":
                unread += 1
            else:
                break

        chats_full.append({
            "chat_id": chat_id,
            "client_name": client_name or "Клиент",
            "client_id": meta.get("clientID", ""),
            "last_message_time": meta.get("lastMessageTime", "") or last_msg.get("addTime", ""),
            "last_sender": last_sender,
            "last_text": last_text,
            "unread_count": unread,
            "total_messages": len(messages),
            "messages": messages
        })

    # Sort chats by last message time (newest first)
    chats_full.sort(
        key=lambda c: c["messages"][-1]["addTimestamp"] if c["messages"] else 0,
        reverse=True
    )

    print(f"  Chats with messages: {len(chats_full)}")
    for c in chats_full:
        print(f"  - {c['client_name']}: {c['total_messages']} msgs, "
              f"unread: {c['unread_count']}, chat_id: {c['chat_id'][:25]}...")

    return chats_full


# === STEP 4: Save ===
def save_result(chats_full, final_cursor):
    """Save full data to JSON"""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_base": BASE_URL,
        "final_cursor": final_cursor,
        "total_chats": len(chats_full),
        "total_messages": sum(c["total_messages"] for c in chats_full),
        "chats": chats_full
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  Saved to: {OUTPUT_FILE}")
    print(f"  Total chats: {result['total_chats']}")
    print(f"  Total messages: {result['total_messages']}")

    return result


# === MAIN ===
if __name__ == "__main__":
    print(f"WB Chat API Full History Fetcher")
    print(f"Base URL: {BASE_URL}")
    print(f"Token: ...{TOKEN[-20:]}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    # 1. Get chat list
    chats_list = fetch_chats()

    # 2. Get ALL events
    all_events, final_cursor = fetch_all_events()

    # 3. Group by chat
    chats_full = group_by_chat(all_events, chats_list)

    # 4. Save
    save_result(chats_full, final_cursor)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
