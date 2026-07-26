"""Small, dependency-free safety controls for the public demo API."""

from __future__ import annotations

from collections import defaultdict, deque
from secrets import compare_digest
from threading import Lock
from time import monotonic
from typing import Annotated

from fastapi import Header, HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

WRITE_KEY_HEADER = "X-GradeLens-API-Key"


def require_write_access(
    supplied_key: Annotated[
        str | None,
        Header(alias=WRITE_KEY_HEADER),
    ] = None,
) -> None:
    """Protect endpoints that persist recommendations or operator feedback."""
    configured_key = settings.WRITE_API_KEY
    if not configured_key and settings.ENVIRONMENT != "production":
        return
    if (
        not configured_key
        or not supplied_key
        or not compare_digest(supplied_key, configured_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid GradeLens write credential is required.",
        )


class RequestSafetyMiddleware(BaseHTTPMiddleware):
    """Enforce body limits, bounded per-client rates, and API headers."""

    def __init__(self, app):
        super().__init__(app)
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def _is_mutation(request: Request) -> bool:
        path = request.url.path
        return request.method == "POST" and (
            path == "/recommendations/generate"
            or (
                path.startswith("/recommendations/")
                and path.rsplit("/", 1)[-1]
                in {"accept", "reject", "modify"}
            )
        )

    def _rate_limited(self, key: str, limit: int) -> bool:
        now = monotonic()
        cutoff = now - 60.0
        with self._lock:
            bucket = self._requests[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return True
            bucket.append(now)

            # Bound memory if the service is scanned from many addresses.
            if len(self._requests) > 10_000:
                expired = [
                    bucket_key
                    for bucket_key, values in self._requests.items()
                    if not values or values[-1] <= cutoff
                ]
                for bucket_key in expired:
                    self._requests.pop(bucket_key, None)
                while len(self._requests) > 10_000:
                    oldest_key = next(iter(self._requests))
                    self._requests.pop(oldest_key, None)
        return False

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > settings.MAX_REQUEST_BYTES
            except ValueError:
                too_large = True
            if too_large:
                return JSONResponse(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    content={"detail": "Request body exceeds the configured limit."},
                )

        client = request.client.host if request.client else "unknown"
        mutation = self._is_mutation(request)
        category = "mutation" if mutation else "general"
        limit = (
            settings.MUTATION_RATE_LIMIT_PER_MINUTE
            if mutation
            else settings.RATE_LIMIT_PER_MINUTE
        )
        if self._rate_limited(f"{client}:{category}", limit):
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Request rate limit exceeded."},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response
