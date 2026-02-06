"""FastAPI application."""
import os
import json
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Cookie, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.database import init_db, get_session, User, Task, Report
from backend.auth import verify_telegram_auth, create_session_token, verify_session_token
from backend.tasks import analyze_article_task

load_dotenv()

app = FastAPI(title="AgentIQ MVP")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Environment variables
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")


# ============================================================================
# Startup / Shutdown
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await init_db()
    print("✅ Database initialized")


# ============================================================================
# Pydantic Models
# ============================================================================

class TelegramAuthData(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class CreateTaskRequest(BaseModel):
    article_id: int


class TaskResponse(BaseModel):
    id: int
    article_id: int
    status: str
    progress: int
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]


class ReportResponse(BaseModel):
    id: int
    task_id: int
    article_id: int
    category: Optional[str]
    rating: Optional[float]
    feedback_count: Optional[int]
    target_variant: Optional[str]
    data: dict
    created_at: datetime


# ============================================================================
# Auth Dependency
# ============================================================================

async def get_current_user(
    session_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_session)
) -> User:
    """Get current authenticated user from session cookie."""
    # TEMPORARY: Skip auth for local testing without Telegram Login Widget
    # TODO: Remove this when deploying to production with ngrok/domain

    # Create or get a test user
    result = await db.execute(
        select(User).where(User.telegram_id == 999999999)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            telegram_id=999999999,
            username="testuser",
            first_name="Test",
            last_name="User",
            auth_date=int(datetime.utcnow().timestamp())
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return user

    # ORIGINAL CODE (commented out for local testing):
    # if not session_token:
    #     raise HTTPException(status_code=401, detail="Not authenticated")
    #
    # telegram_id = verify_session_token(session_token)
    # if not telegram_id:
    #     raise HTTPException(status_code=401, detail="Invalid or expired session")
    #
    # result = await db.execute(
    #     select(User).where(User.telegram_id == telegram_id)
    # )
    # user = result.scalar_one_or_none()
    #
    # if not user:
    #     raise HTTPException(status_code=401, detail="User not found")
    #
    # return user


# ============================================================================
# Frontend Routes
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Landing page with Telegram Login Widget."""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "bot_username": TELEGRAM_BOT_USERNAME,
        "frontend_url": FRONTEND_URL,
    })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user)
):
    """Dashboard page (requires auth)."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
    })


@app.get("/dashboard/report/{task_id}", response_class=HTMLResponse)
async def report_page(
    request: Request,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Report detail page."""
    # Check if task belongs to user
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get report data
    report_result = await db.execute(
        select(Report).where(Report.task_id == task_id)
    )
    report = report_result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Parse JSON data
    import json
    data = json.loads(report.data)

    # Ensure header has all required fields
    if "header" not in data:
        data["header"] = {}

    # Add missing fields from report model
    data["header"]["feedback_count"] = report.feedback_count or 0
    data["header"]["rating"] = report.rating or 0
    data["header"]["unanswered_count"] = 0  # TODO: calculate from feedbacks

    # Add product name from title if not present
    if "product_name" not in data["header"]:
        data["header"]["product_name"] = f"Артикул {report.article_id}"

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": user,
        "task_id": task_id,
        "report": report,
        "data": data,
    })


@app.get("/preview/report", response_class=HTMLResponse)
async def preview_report(request: Request):
    """Public preview — renders report from /tmp/result-370907224.json (no auth)."""
    import json as _json
    path = "/tmp/result-370907224.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Preview file not found")
    with open(path, "r") as f:
        data = _json.load(f)
    # Ensure required fields
    if "header" not in data:
        data["header"] = {}
    data["header"].setdefault("feedback_count", 0)
    data["header"].setdefault("rating", 0)
    data["header"].setdefault("unanswered_count", 0)
    data["header"].setdefault("product_name", "Артикул 370907224")

    class FakeUser:
        first_name = "Preview"
        username = "preview"
        photo_url = None

    class FakeReport:
        id = 0
        article_id = 370907224
        category = data["header"].get("category", "")

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": FakeUser(),
        "task_id": 0,
        "report": FakeReport(),
        "data": data,
    })


# ============================================================================
# API Routes - Auth
# ============================================================================

@app.get("/api/auth/telegram/callback")
async def telegram_auth_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session)
):
    """
    Telegram Login Widget callback.
    Query params: id, first_name, last_name, username, photo_url, auth_date, hash
    """
    params = dict(request.query_params)

    # Verify auth data
    if not verify_telegram_auth(params):
        raise HTTPException(status_code=403, detail="Invalid authentication data")

    telegram_id = int(params["id"])
    auth_date = int(params["auth_date"])

    # Create or update user
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.username = params.get("username")
        user.first_name = params.get("first_name")
        user.last_name = params.get("last_name")
        user.photo_url = params.get("photo_url")
        user.auth_date = auth_date
    else:
        # Create new user
        user = User(
            telegram_id=telegram_id,
            username=params.get("username"),
            first_name=params.get("first_name"),
            last_name=params.get("last_name"),
            photo_url=params.get("photo_url"),
            auth_date=auth_date,
        )
        db.add(user)

    await db.commit()

    # Create session token
    token = create_session_token(telegram_id)

    # Set cookie and redirect to dashboard
    redirect_response = RedirectResponse(url="/dashboard", status_code=302)
    redirect_response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=604800,  # 7 days
        samesite="lax"
    )

    return redirect_response


@app.post("/api/auth/logout")
async def logout(response: Response):
    """Logout (clear cookie)."""
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("session_token")
    return response


# ============================================================================
# API Routes - Tasks
# ============================================================================

@app.post("/api/tasks/create", response_model=TaskResponse)
async def create_task(
    req: CreateTaskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Create a new analysis task."""
    # Create task in DB
    task = Task(
        user_id=user.id,
        article_id=req.article_id,
        status="pending",
        progress=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # Trigger Celery task
    analyze_article_task.delay(
        task_id=task.id,
        article_id=req.article_id,
        user_telegram_id=user.telegram_id
    )

    return TaskResponse(
        id=task.id,
        article_id=task.article_id,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
    )


@app.get("/api/tasks/list", response_model=List[TaskResponse])
async def list_tasks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """List user's tasks."""
    result = await db.execute(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(desc(Task.created_at))
        .limit(50)
    )
    tasks = result.scalars().all()

    return [
        TaskResponse(
            id=task.id,
            article_id=task.article_id,
            status=task.status,
            progress=task.progress,
            created_at=task.created_at,
            completed_at=task.completed_at,
            error_message=task.error_message,
        )
        for task in tasks
    ]


@app.get("/api/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Get task status."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        id=task.id,
        article_id=task.article_id,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
    )


@app.get("/api/tasks/{task_id}/report", response_model=ReportResponse)
async def get_task_report(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session)
):
    """Get task report."""
    # Check task belongs to user
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    # Get report
    result = await db.execute(
        select(Report).where(Report.task_id == task_id)
    )
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return ReportResponse(
        id=report.id,
        task_id=report.task_id,
        article_id=report.article_id,
        category=report.category,
        rating=report.rating,
        feedback_count=report.feedback_count,
        target_variant=report.target_variant,
        data=json.loads(report.data),
        created_at=report.created_at,
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
