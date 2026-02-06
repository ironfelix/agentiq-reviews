"""Celery tasks for background processing."""
import os
import sys
import json
import time
import requests
import subprocess
import tempfile
from datetime import datetime
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import Task, Report, Notification
from backend.telegram_bot import send_telegram_notification

load_dotenv()

# Celery setup
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("agentiq", broker=REDIS_URL, backend=REDIS_URL)

# Synchronous database connection for Celery workers
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentiq.db")
# Convert async URL to sync for Celery
DATABASE_URL_SYNC = DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
engine = create_engine(DATABASE_URL_SYNC)
SessionLocal = sessionmaker(bind=engine)

# WBCON API credentials
WBCON_EMAIL = os.getenv("WBCON_EMAIL", "")
WBCON_PASS = os.getenv("WBCON_PASS", "")
WBCON_FB_BASE = os.getenv("WBCON_FB_BASE", "https://01-fb.wbcon.su")


def update_task_progress(task_id: int, progress: int, status: str = None, wbcon_task_id: int = None):
    """Update task progress in database."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.progress = progress
            if status:
                task.status = status
            if wbcon_task_id:
                task.wbcon_task_id = wbcon_task_id
            db.commit()
    finally:
        db.close()


def create_wbcon_task(article_id: int) -> int:
    """Create WBCON task via API."""
    url = f"{WBCON_FB_BASE}/create_task_fb?email={WBCON_EMAIL}&password={WBCON_PASS}"
    try:
        print(f"[WBCON] Creating task for article {article_id}")
        print(f"[WBCON] URL: {url}")

        response = requests.post(
            url,
            json={"article": article_id},
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        print(f"[WBCON] Response status: {response.status_code}")
        print(f"[WBCON] Response text: {response.text}")

        response.raise_for_status()
        data = response.json()

        print(f"[WBCON] Parsed JSON: {data}")

        if not data or "task_id" not in data:
            raise ValueError(f"WBCON API returned invalid response: {data}")

        print(f"[WBCON] Task created successfully with ID: {data['task_id']}")
        return data["task_id"]
    except requests.exceptions.RequestException as e:
        print(f"[WBCON] Request exception: {str(e)}")
        raise Exception(f"WBCON API request failed: {str(e)}")
    except (KeyError, TypeError, ValueError) as e:
        print(f"[WBCON] Parsing exception: {str(e)}")
        raise Exception(f"WBCON API response parsing failed: {str(e)}")


def check_wbcon_status(wbcon_task_id: int) -> dict:
    """Check WBCON task status."""
    url = f"{WBCON_FB_BASE}/task_status?task_id={wbcon_task_id}&email={WBCON_EMAIL}&password={WBCON_PASS}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def fetch_all_feedbacks(wbcon_task_id: int, feedback_count: int = 0) -> list:
    """Fetch all feedbacks with pagination and deduplication."""
    all_feedbacks = []
    seen_ids = set()
    offset = 0
    max_iterations = 50  # Safety limit: max 5000 feedbacks

    while offset < max_iterations * 100:
        # Stop early if we already have all feedbacks
        if feedback_count > 0 and len(all_feedbacks) >= feedback_count:
            print(f"[DEBUG] Already collected {len(all_feedbacks)} >= {feedback_count} feedbacks, stopping")
            break

        print(f"[DEBUG] Fetching feedbacks at offset {offset}...")
        url = f"{WBCON_FB_BASE}/get_results_fb?task_id={wbcon_task_id}&offset={offset}&email={WBCON_EMAIL}&password={WBCON_PASS}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        print(f"[DEBUG] Got response, type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")

        if not data or not isinstance(data, list) or len(data) == 0:
            print(f"[DEBUG] No more data, breaking pagination loop")
            break

        feedbacks = data[0].get("feedbacks", [])
        print(f"[DEBUG] Got {len(feedbacks)} feedbacks in this batch")

        if not feedbacks or len(feedbacks) == 0:
            print(f"[DEBUG] No feedbacks in batch, breaking pagination loop")
            break

        # Deduplicate by feedback ID
        new_count = 0
        for fb in feedbacks:
            fb_id = fb.get("fb_id") or fb.get("id")
            if fb_id and fb_id in seen_ids:
                continue
            if fb_id:
                seen_ids.add(fb_id)
            all_feedbacks.append(fb)
            new_count += 1

        print(f"[DEBUG] New unique: {new_count}, total unique: {len(all_feedbacks)}")

        offset += 100

        # If we got less than 100, it's the last page
        if len(feedbacks) < 100:
            print(f"[DEBUG] Last batch had <100 feedbacks, done with pagination")
            break

        # Stop if we've reached feedback_count
        if feedback_count > 0 and offset >= feedback_count:
            print(f"[DEBUG] offset {offset} >= feedback_count {feedback_count}, done")
            break

        # If all duplicates and past expected count, stop
        if new_count == 0 and (feedback_count == 0 or len(all_feedbacks) >= feedback_count):
            print(f"[DEBUG] No new feedbacks and collected enough, stopping")
            break

        # Rate limit
        time.sleep(0.5)

    print(f"[DEBUG] Total unique feedbacks collected: {len(all_feedbacks)}")
    return all_feedbacks


def run_analysis(article_id: int, feedbacks_data: dict) -> dict:
    """
    Run wbcon-task-to-card-v2.py analysis.
    Returns parsed JSON result.
    """
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as input_file:
        json.dump(feedbacks_data, input_file)
        input_path = input_file.name

    output_path = tempfile.mktemp(suffix='.json')

    try:
        # Path to analysis script
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..",
            "wbcon-task-to-card-v2.py"
        )

        print(f"[DEBUG] Running analysis script: {script_path}")
        print(f"[DEBUG] Input: {input_path}, Output: {output_path}")

        # Run analysis script with timeout
        result_proc = subprocess.run(
            ["python3", script_path, input_path, output_path],
            check=True,
            capture_output=True,
            timeout=120  # 2 minutes max
        )

        print(f"[DEBUG] Analysis script completed. Return code: {result_proc.returncode}")
        if result_proc.stdout:
            print(f"[DEBUG] Script stdout: {result_proc.stdout.decode()[:500]}")
        if result_proc.stderr:
            print(f"[DEBUG] Script stderr: {result_proc.stderr.decode()[:500]}")

        # Read result
        print(f"[DEBUG] Reading output file: {output_path}")
        with open(output_path, 'r') as f:
            result = json.load(f)
        print(f"[DEBUG] Successfully parsed result JSON")

        return result

    except subprocess.TimeoutExpired as e:
        print(f"[ERROR] Analysis script timeout after 120s")
        raise Exception(f"Analysis timeout: script took too long")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Analysis script failed with code {e.returncode}")
        print(f"[ERROR] stderr: {e.stderr.decode() if e.stderr else 'N/A'}")
        print(f"[ERROR] stdout: {e.stdout.decode() if e.stdout else 'N/A'}")
        raise Exception(f"Analysis failed: {e.stderr.decode() if e.stderr else 'Unknown error'}")
    except Exception as e:
        print(f"[ERROR] Unexpected error in run_analysis: {e}")
        raise
    finally:
        # Cleanup
        if os.path.exists(input_path):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)


@celery_app.task(name="analyze_article")
def analyze_article_task(task_id: int, article_id: int, user_telegram_id: int):
    """
    Background task to analyze article reviews.

    Steps:
    1. Create WBCON task
    2. Wait for WBCON task to complete (polling)
    3. Fetch all feedbacks (with pagination)
    4. Run analysis (wbcon-task-to-card-v2.py)
    5. Save report to database
    6. Send Telegram notification
    """
    db = SessionLocal()

    try:
        # Step 1: Create WBCON task
        update_task_progress(task_id, 10, "processing")
        wbcon_task_id = create_wbcon_task(article_id)
        update_task_progress(task_id, 20, wbcon_task_id=wbcon_task_id)

        # Step 2: Wait for WBCON task to complete (polling)
        max_attempts = 60  # 5 minutes max
        attempt = 0
        while attempt < max_attempts:
            status_data = check_wbcon_status(wbcon_task_id)
            if status_data.get("is_ready"):
                break
            time.sleep(5)
            attempt += 1
            progress = min(20 + (attempt * 2), 40)
            update_task_progress(task_id, progress)

        if attempt >= max_attempts:
            raise Exception("WBCON task timeout")

        update_task_progress(task_id, 50)

        # Step 3: Fetch all feedbacks
        print(f"[DEBUG] Fetching feedbacks for WBCON task {wbcon_task_id}...")
        url = f"{WBCON_FB_BASE}/get_results_fb?task_id={wbcon_task_id}&offset=0&email={WBCON_EMAIL}&password={WBCON_PASS}"
        print(f"[DEBUG] URL: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        feedbacks_data = response.json()

        # feedbacks_data is a list, first element contains the data
        if not feedbacks_data or not isinstance(feedbacks_data, list):
            raise ValueError(f"Invalid feedbacks response format: {feedbacks_data}")

        print(f"[DEBUG] Received feedbacks data: {len(feedbacks_data[0].get('feedbacks', []))} feedbacks")

        # Get first batch to check feedback count
        if feedbacks_data and isinstance(feedbacks_data, list) and len(feedbacks_data) > 0:
            feedback_count = feedbacks_data[0].get("feedback_count", 0)
            print(f"[DEBUG] Total feedback_count: {feedback_count}")

            # If more than 100, fetch all with pagination
            if feedback_count > 100:
                print(f"[DEBUG] Fetching all feedbacks with pagination (expected: {feedback_count})...")
                all_feedbacks = fetch_all_feedbacks(wbcon_task_id, feedback_count=feedback_count)
                print(f"[DEBUG] Fetched {len(all_feedbacks)} feedbacks total")
                feedbacks_data[0]["feedbacks"] = all_feedbacks
        else:
            feedback_count = 0

        print(f"[DEBUG] Proceeding to analysis step...")
        update_task_progress(task_id, 70)

        # Step 4: Run analysis
        print(f"[DEBUG] Starting analysis for article {article_id} with {len(feedbacks_data[0].get('feedbacks', []))} feedbacks...")
        result = run_analysis(article_id, feedbacks_data[0])
        print(f"[DEBUG] Analysis completed!")
        update_task_progress(task_id, 90)

        # Step 5: Save report
        report = Report(
            task_id=task_id,
            article_id=article_id,
            category=result.get("header", {}).get("category"),
            rating=result.get("header", {}).get("rating"),
            feedback_count=feedback_count if feedbacks_data else 0,
            target_variant=result.get("signal", {}).get("scores", [{}])[0].get("label"),
            data=json.dumps(result, ensure_ascii=False),
        )
        db.add(report)

        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.utcnow()

        db.commit()

        # Step 6: Send Telegram notification
        message = (
            f"✅ Анализ артикула {article_id} готов!\n\n"
            f"Рейтинг: {result.get('header', {}).get('rating', 'N/A')}\n"
            f"Отзывов: {feedback_count}\n\n"
            f"👉 Открыть отчёт: {os.getenv('FRONTEND_URL')}/dashboard/report/{task_id}"
        )

        send_telegram_notification(user_telegram_id, message)

        # Save notification to DB
        notification = Notification(
            user_id=task.user_id,
            task_id=task_id,
            message=message,
        )
        db.add(notification)
        db.commit()

    except Exception as e:
        # Mark task as failed
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "failed"
            task.error_message = str(e)
            db.commit()

        # Send error notification
        error_message = (
            f"❌ Ошибка при анализе артикула {article_id}\n\n"
            f"Причина: {str(e)}\n\n"
            f"Попробуйте создать задачу снова."
        )
        send_telegram_notification(user_telegram_id, error_message)

        raise

    finally:
        db.close()
