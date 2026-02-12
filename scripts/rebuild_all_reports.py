#!/usr/bin/env python3
"""
Rebuild all existing reports with 12-month date filter.
Uses existing WBCON task IDs to re-fetch feedbacks and regenerate reports.
"""
import sys
import os
import sqlite3
import json
import requests
import subprocess
import tempfile
from datetime import datetime

# Add apps/reviews to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'reviews'))

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'apps', 'reviews', '.env'))
except ImportError:
    pass

WBCON_FB_BASE = "https://19-fb.wbcon.su"
WBCON_TOKEN = os.getenv("WBCON_TOKEN")
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'apps', 'reviews', 'agentiq.db')
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), 'wbcon-task-to-card-v2.py')


def fetch_wbcon_feedbacks(wbcon_task_id: str) -> dict:
    """Fetch all feedbacks from WBCON API."""
    print(f"  Fetching feedbacks from WBCON task {wbcon_task_id}...")

    all_feedbacks = []
    seen_ids = set()
    offset = 0

    while offset < 5000:  # Max 50 iterations
        url = f"{WBCON_FB_BASE}/get_results_fb"
        response = requests.get(
            url,
            params={"task_id": wbcon_task_id, "offset": offset},
            headers={"token": WBCON_TOKEN},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if not data or not isinstance(data, list) or len(data) == 0:
            break

        feedbacks = data[0].get("feedbacks", [])
        if not feedbacks:
            break

        # Dedup
        new_count = 0
        for fb in feedbacks:
            fb_id = fb.get("fb_id") or fb.get("id")
            if fb_id and fb_id in seen_ids:
                continue
            if fb_id:
                seen_ids.add(fb_id)
            all_feedbacks.append(fb)
            new_count += 1

        print(f"    Offset {offset}: +{new_count} feedbacks (total: {len(all_feedbacks)})")

        if len(feedbacks) < 100:
            break

        offset += 100

    print(f"  Total feedbacks: {len(all_feedbacks)}")
    return {"feedbacks": all_feedbacks}


def run_analysis_script(article_id: int, feedbacks_data: dict) -> dict:
    """Run wbcon-task-to-card-v2.py analysis."""
    print(f"  Running analysis script...")

    # Add article to feedbacks
    for fb in feedbacks_data.get("feedbacks", []):
        if "article" not in fb:
            fb["article"] = article_id

    # Create temp files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(feedbacks_data, f)
        input_path = f.name

    output_path = tempfile.mktemp(suffix='.json')

    try:
        result = subprocess.run(
            ['python3', SCRIPT_PATH, input_path, output_path],
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            print(f"  ERROR: Script failed!")
            print(f"  STDOUT: {result.stdout}")
            print(f"  STDERR: {result.stderr}")
            return None

        # Print filter info from stdout
        for line in result.stdout.split('\n'):
            if '12-month filter' in line or 'filter:' in line.lower():
                print(f"  {line}")

        with open(output_path) as f:
            return json.load(f)

    finally:
        if os.path.exists(input_path):
            os.unlink(input_path)
        if os.path.exists(output_path):
            os.unlink(output_path)


def update_report_in_db(task_id: int, report_data: dict):
    """Update report in database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get existing report
    cur.execute("SELECT share_token FROM reports WHERE task_id = ?", (task_id,))
    row = cur.fetchone()
    share_token = row[0] if row else None

    # Update or insert
    if row:
        cur.execute("""
            UPDATE reports
            SET data = ?
            WHERE task_id = ?
        """, (json.dumps(report_data), task_id))
    else:
        cur.execute("""
            INSERT INTO reports (task_id, data, share_token, created_at)
            VALUES (?, ?, ?, ?)
        """, (task_id, json.dumps(report_data), share_token,
              datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()
    print(f"  Updated report in database")


def rebuild_task(task_id: int, article_id: int, wbcon_task_id: str):
    """Rebuild single task report."""
    print(f"\n{'='*60}")
    print(f"Task {task_id}: Article {article_id} (WBCON task {wbcon_task_id})")
    print(f"{'='*60}")

    try:
        # 1. Fetch feedbacks
        feedbacks_data = fetch_wbcon_feedbacks(wbcon_task_id)

        if not feedbacks_data or not feedbacks_data.get("feedbacks"):
            print(f"  ERROR: No feedbacks returned from WBCON API")
            return False

        # 2. Run analysis
        report_data = run_analysis_script(article_id, feedbacks_data)

        if not report_data:
            print(f"  ERROR: Analysis script failed")
            return False

        # 3. Update DB
        update_report_in_db(task_id, report_data)

        # 4. Print summary
        header = report_data.get("header", {})
        comm = report_data.get("communication", {})
        print(f"\n  ✅ SUCCESS!")
        print(f"     Feedback count: {header.get('feedback_count')} (12-month filtered)")
        print(f"     Analyzed: {header.get('analyzed_count')}")
        print(f"     Quality score: {comm.get('quality_score')}/10")

        return True

    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Rebuild all completed tasks."""
    print("="*60)
    print("REBUILD ALL REPORTS WITH 12-MONTH FILTER")
    print("="*60)

    # Get all completed tasks
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, article_id, wbcon_task_id
        FROM tasks
        WHERE status = 'completed' AND wbcon_task_id IS NOT NULL AND wbcon_task_id != ''
        ORDER BY id
    """)
    tasks = cur.fetchall()
    conn.close()

    print(f"\nFound {len(tasks)} completed tasks to rebuild\n")

    if not tasks:
        print("No tasks to rebuild!")
        return

    success_count = 0
    for task_id, article_id, wbcon_task_id in tasks:
        if rebuild_task(task_id, article_id, wbcon_task_id):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"DONE: {success_count}/{len(tasks)} tasks rebuilt successfully")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
