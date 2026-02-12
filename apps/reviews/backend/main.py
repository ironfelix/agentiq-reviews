"""FastAPI application — AgentIQ MVP2."""
import os
import io
import json
import secrets
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Cookie, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.database import init_db, get_session, User, Task, Report, Notification, InviteCode
from backend.auth import (
    verify_telegram_auth, create_session_token,
    verify_session_token, should_refresh_token,
)
from backend.tasks import analyze_article_task

load_dotenv()

app = FastAPI(title="AgentIQ MVP2")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


# Custom Jinja2 filters
def format_number(value):
    """Format number with thousands separator."""
    try:
        return f"{int(value):,}".replace(",", " ")
    except (TypeError, ValueError):
        return value


templates.env.filters["format_number"] = format_number

# Environment variables
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SESSION_COOKIE_MAX_AGE = 2592000  # 30 days


# ============================================================================
# Startup
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    await init_db()
    print("Database initialized")


# ============================================================================
# Token Refresh Middleware
# ============================================================================

@app.middleware("http")
async def refresh_token_middleware(request: Request, call_next):
    """Auto-refresh JWT cookie if expiring within 7 days."""
    response = await call_next(request)
    new_token = getattr(request.state, "refresh_token", None)
    if new_token:
        response.set_cookie(
            key="session_token",
            value=new_token,
            httponly=True,
            secure=ENVIRONMENT != "development",  # HTTPS only in production
            samesite="lax",
            max_age=SESSION_COOKIE_MAX_AGE,
        )
    return response


# ============================================================================
# Pydantic Models
# ============================================================================

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
    # Report summary (populated for completed tasks)
    product_name: Optional[str] = None
    rating: Optional[float] = None
    feedback_count: Optional[int] = None
    quality_score: Optional[int] = None


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


class InviteCodeRequest(BaseModel):
    code: str


# ============================================================================
# Auth Dependency
# ============================================================================

async def get_current_user(
    request: Request,
    session_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Get current authenticated user from JWT session cookie."""
    # Development bypass: skip all auth, auto-create test user
    # SECURITY: Only allowed in local development, never in production!
    if ENVIRONMENT == "development":
        # Extra safeguard: check we're actually on localhost
        host = request.headers.get("host", "")
        if not any(h in host for h in ["localhost", "127.0.0.1", "0.0.0.0"]):
            raise HTTPException(
                status_code=500,
                detail="Development bypass only allowed on localhost"
            )

        result = await db.execute(
            select(User).where(User.telegram_id == 999999999)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=999999999,
                username="dev",
                first_name="Dev",
                last_name="User",
                auth_date=int(datetime.utcnow().timestamp()),
                invite_code_id=1,  # skip invite gate
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    # Production: verify JWT
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    telegram_id = verify_session_token(session_token)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Schedule token refresh if needed
    if should_refresh_token(session_token):
        request.state.refresh_token = create_session_token(telegram_id)

    return user


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
        "environment": ENVIRONMENT,
    })


@app.get("/invite", response_class=HTMLResponse)
async def invite_page(request: Request):
    """Invite code entry page (after first Telegram login)."""
    return templates.TemplateResponse("invite.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Dashboard page (requires auth)."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
    })


# ---- Report: Product Analysis ----

@app.get("/dashboard/report/{task_id}", response_class=HTMLResponse)
async def report_page(
    request: Request,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Product analysis report page."""
    data, report = await _load_report_data(task_id, user, db)

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": user,
        "task_id": task_id,
        "report": report,
        "data": data,
    })


# ---- Report: Communication Analysis ----

@app.get("/dashboard/report/{task_id}/communication", response_class=HTMLResponse)
async def comm_report_page(
    request: Request,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Communication analysis report page."""
    data, report = await _load_report_data(task_id, user, db)

    return templates.TemplateResponse("comm-report.html", {
        "request": request,
        "user": user,
        "task_id": task_id,
        "report": report,
        "data": data,
    })


async def _load_report_data(task_id: int, user: User, db: AsyncSession):
    """Load and prepare report data for rendering. Shared by both report routes."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    report_result = await db.execute(
        select(Report).where(Report.task_id == task_id)
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    data = json.loads(report.data)

    # Ensure header defaults
    if "header" not in data:
        data["header"] = {}
    data["header"].setdefault("feedback_count", report.feedback_count or 0)
    data["header"].setdefault("rating", report.rating or 0)
    data["header"].setdefault("unanswered_count", 0)
    data["header"].setdefault("product_name", f"Артикул {report.article_id}")

    return data, report


# ============================================================================
# Public Share Routes (no auth — accessed via share token)
# ============================================================================

async def _load_shared_report(token: str, db: AsyncSession):
    """Load report by share token (no auth required)."""
    result = await db.execute(
        select(Report).where(Report.share_token == token)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Shared report not found")

    data = json.loads(report.data)
    if "header" not in data:
        data["header"] = {}
    data["header"].setdefault("feedback_count", report.feedback_count or 0)
    data["header"].setdefault("rating", report.rating or 0)
    data["header"].setdefault("unanswered_count", 0)
    data["header"].setdefault("product_name", f"Артикул {report.article_id}")

    return data, report


@app.get("/share/{token}", response_class=HTMLResponse)
async def shared_report_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_session),
):
    """Public product report — no authentication required."""
    data, report = await _load_shared_report(token, db)

    class SharedUser:
        first_name = "Гость"
        username = None
        photo_url = None

    return templates.TemplateResponse("report.html", {
        "request": request,
        "user": SharedUser(),
        "task_id": report.task_id,
        "report": report,
        "data": data,
        "is_shared": True,
    })


@app.get("/share/{token}/communication", response_class=HTMLResponse)
async def shared_comm_report_page(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_session),
):
    """Public communication report — no authentication required."""
    data, report = await _load_shared_report(token, db)

    class SharedUser:
        first_name = "Гость"
        username = None
        photo_url = None

    return templates.TemplateResponse("comm-report.html", {
        "request": request,
        "user": SharedUser(),
        "task_id": report.task_id,
        "report": report,
        "data": data,
        "is_shared": True,
    })


# ---- Preview (no auth, for testing) ----

@app.get("/preview/report", response_class=HTMLResponse)
async def preview_report(request: Request):
    """DEVELOPMENT ONLY: Public preview — renders report from /tmp/result-370907224.json (no auth)."""
    # Security: Only allow in development
    if ENVIRONMENT != "development":
        raise HTTPException(status_code=404, detail="Not found")

    path = "/tmp/result-370907224.json"
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Preview file not found")
    with open(path, "r") as f:
        data = json.load(f)
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
# API Routes — Auth
# ============================================================================

@app.get("/api/auth/telegram/callback")
async def telegram_auth_callback(
    request: Request,
    db: AsyncSession = Depends(get_session),
):
    """Telegram Login Widget callback. Creates/updates user, sets JWT cookie."""
    params = dict(request.query_params)

    if not verify_telegram_auth(params):
        raise HTTPException(status_code=403, detail="Invalid authentication data")

    # Security: Validate and parse integer parameters
    try:
        telegram_id = int(params.get("id", 0))
        auth_date = int(params.get("auth_date", 0))
    except (ValueError, TypeError):
        raise HTTPException(status_code=403, detail="Invalid parameter format")

    # Security: Validate telegram_id is positive
    if telegram_id <= 0:
        raise HTTPException(status_code=403, detail="Invalid telegram ID")

    # Security: Validate auth_date is reasonable (not in future, not too old)
    if auth_date <= 0:
        raise HTTPException(status_code=403, detail="Invalid auth date")

    # Create or update user
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()

    if user:
        user.username = params.get("username")
        user.first_name = params.get("first_name")
        user.last_name = params.get("last_name")
        user.photo_url = params.get("photo_url")
        user.auth_date = auth_date
    else:
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
    await db.refresh(user)

    # JWT cookie
    token = create_session_token(telegram_id)

    # Redirect: new user without invite → /invite, otherwise → /dashboard
    redirect_url = "/dashboard" if user.invite_code_id else "/invite"
    redirect_response = RedirectResponse(url=redirect_url, status_code=302)
    redirect_response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        secure=ENVIRONMENT != "development",  # HTTPS only in production
        max_age=SESSION_COOKIE_MAX_AGE,
        samesite="lax",
    )

    return redirect_response


@app.post("/api/auth/verify-invite")
async def verify_invite(
    req: InviteCodeRequest,
    session_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_session),
):
    """Verify invite code and bind to user."""
    # Get current user from token
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    telegram_id = verify_session_token(session_token)
    if not telegram_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Already has invite
    if user.invite_code_id:
        return {"message": "Already activated"}

    # Look up invite code
    code_result = await db.execute(
        select(InviteCode).where(InviteCode.code == req.code.strip().upper())
    )
    invite = code_result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=400, detail="Неверный инвайт-код")
    if invite.used_count >= invite.max_uses:
        raise HTTPException(status_code=400, detail="Код уже использован максимальное число раз")

    # Bind
    invite.used_count += 1
    user.invite_code_id = invite.id
    await db.commit()

    return {"message": "Invite code accepted"}


@app.post("/api/auth/logout")
async def logout():
    """Logout (clear cookie)."""
    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("session_token")
    return response


# ============================================================================
# API Routes — Tasks
# ============================================================================

@app.post("/api/tasks/create", response_model=TaskResponse)
async def create_task(
    req: CreateTaskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Create a new analysis task."""
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
        user_telegram_id=user.telegram_id,
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
    db: AsyncSession = Depends(get_session),
):
    """List user's tasks with report summary."""
    result = await db.execute(
        select(Task)
        .where(Task.user_id == user.id)
        .order_by(desc(Task.created_at))
        .limit(50)
    )
    tasks = result.scalars().all()

    responses = []
    for t in tasks:
        product_name = None
        rating = None
        feedback_count = None
        quality_score = None

        if t.status == "completed":
            report_result = await db.execute(
                select(Report).where(Report.task_id == t.id)
            )
            report = report_result.scalar_one_or_none()
            if report:
                rating = report.rating
                feedback_count = report.feedback_count
                try:
                    data = json.loads(report.data)
                    product_name = data.get("header", {}).get("product_name")
                    comm = data.get("communication")
                    if comm:
                        quality_score = comm.get("quality_score")
                except (json.JSONDecodeError, AttributeError):
                    pass

        responses.append(TaskResponse(
            id=t.id,
            article_id=t.article_id,
            status=t.status,
            progress=t.progress,
            created_at=t.created_at,
            completed_at=t.completed_at,
            error_message=t.error_message,
            product_name=product_name,
            rating=rating,
            feedback_count=feedback_count,
            quality_score=quality_score,
        ))

    return responses


@app.get("/api/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
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


@app.delete("/api/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Delete task and its report/notifications."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Cascade delete related records
    await db.execute(delete(Report).where(Report.task_id == task_id))
    await db.execute(delete(Notification).where(Notification.task_id == task_id))
    await db.delete(task)
    await db.commit()

    return {"message": "Task deleted"}


@app.get("/api/tasks/{task_id}/report", response_model=ReportResponse)
async def get_task_report(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get task report as JSON."""
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != "completed":
        raise HTTPException(status_code=400, detail="Task not completed yet")

    report_result = await db.execute(
        select(Report).where(Report.task_id == task_id)
    )
    report = report_result.scalar_one_or_none()
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
# Share Links
# ============================================================================

@app.post("/api/reports/{task_id}/share")
async def create_share_link(
    request: Request,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate a public share link for a report."""
    # Verify ownership
    result = await db.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    report_result = await db.execute(
        select(Report).where(Report.task_id == task_id)
    )
    report = report_result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    # Generate token if not exists
    if not report.share_token:
        report.share_token = secrets.token_urlsafe(32)
        await db.commit()

    # Build share URL from request origin (works for both localhost and production)
    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/share/{report.share_token}"

    return {"share_url": share_url, "token": report.share_token}


# ============================================================================
# PDF Export
# ============================================================================

@app.get("/api/reports/{task_id}/pdf")
async def download_pdf(
    request: Request,
    task_id: int,
    type: str = "product",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate and download PDF report."""
    try:
        from backend.pdf_export import html_to_pdf
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="PDF export unavailable — Playwright not installed. Install with: pip install playwright && playwright install chromium",
        )

    data, report = await _load_report_data(task_id, user, db)

    template_name = "comm-report.html" if type == "communication" else "report.html"
    html = templates.env.get_template(template_name).render(
        request=request,
        user=user,
        task_id=task_id,
        report=report,
        data=data,
        is_shared=False,
    )

    try:
        pdf_bytes = await html_to_pdf(html)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"PDF generation failed: {e}. Ensure Chromium is installed: playwright install chromium",
        )

    filename = f"agentiq-{type}-{report.article_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "version": "mvp2"}
