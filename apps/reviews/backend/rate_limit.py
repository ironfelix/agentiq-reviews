"""
Rate limiting middleware using slowapi.

Install: pip install slowapi

Usage in main.py:
    from backend.rate_limit import limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.post("/api/tasks/create")
    @limiter.limit("5/minute")  # 5 requests per minute
    async def create_task(...):
        ...
"""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, Response
from fastapi.responses import JSONResponse


def get_identifier(request: Request) -> str:
    """
    Get rate limit identifier.
    Uses user ID if authenticated, otherwise IP address.
    """
    # Try to get user from request state (set by get_current_user)
    user = getattr(request.state, "user", None)
    if user and hasattr(user, "id"):
        return f"user:{user.id}"

    # Fallback to IP address
    return get_remote_address(request)


# Initialize limiter
limiter = Limiter(
    key_func=get_identifier,
    default_limits=["100/hour"],  # Global limit: 100 requests per hour per user/IP
    storage_uri="memory://",  # Use Redis in production: redis://localhost:6379
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom error response for rate limit exceeded."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please try again later.",
            "retry_after": exc.detail.split("in ")[1] if "in " in exc.detail else "60 seconds",
        },
        headers={"Retry-After": "60"},
    )
