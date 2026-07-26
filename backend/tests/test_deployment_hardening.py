"""Deployment-safety regression tests."""

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.database import _engine_options
from app.runtime import (
    initialize_runtime,
    inspect_model_artifacts,
    required_artifact_names,
)
from app.security import RequestSafetyMiddleware, require_write_access


def test_database_options_are_dialect_safe():
    sqlite_options = _engine_options("sqlite:///:memory:")
    assert sqlite_options["connect_args"]["check_same_thread"] is False
    assert sqlite_options["connect_args"]["timeout"] == 30

    postgres_options = _engine_options(
        "postgresql+psycopg://user:password@database/gradelens"
    )
    assert "connect_args" not in postgres_options
    assert postgres_options["pool_pre_ping"] is True


def test_packaged_artifacts_have_valid_manifest():
    status = inspect_model_artifacts()
    assert status["ready"] is True
    assert status["missing"] == []
    assert status["manifest_error"] is None
    assert "artifact_manifest.json" in required_artifact_names()


def test_write_access_requires_secret_when_configured():
    previous_key = settings.WRITE_API_KEY
    previous_environment = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        settings.WRITE_API_KEY = "deployment-test-secret"
        try:
            require_write_access(None)
            raise AssertionError("Missing write key was accepted")
        except HTTPException as exc:
            assert exc.status_code == 401

        require_write_access("deployment-test-secret")
    finally:
        settings.WRITE_API_KEY = previous_key
        settings.ENVIRONMENT = previous_environment


def test_production_startup_rejects_short_write_secret():
    previous_key = settings.WRITE_API_KEY
    previous_environment = settings.ENVIRONMENT
    try:
        settings.ENVIRONMENT = "production"
        settings.WRITE_API_KEY = "too-short"
        with pytest.raises(RuntimeError, match="at least 32 characters"):
            initialize_runtime()
    finally:
        settings.WRITE_API_KEY = previous_key
        settings.ENVIRONMENT = previous_environment


def test_request_limit_and_security_headers():
    middleware = RequestSafetyMiddleware(lambda _scope, _receive, _send: None)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/intelligence/data/validate",
            "headers": [
                (
                    b"content-length",
                    str(settings.MAX_REQUEST_BYTES + 1).encode(),
                )
            ],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )

    async def call_next(_request):
        return Response("ok")

    oversized = asyncio.run(middleware.dispatch(request, call_next))
    assert oversized.status_code == 413

    safe_request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health/live",
            "headers": [],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )
    safe_response = asyncio.run(middleware.dispatch(safe_request, call_next))
    assert safe_response.headers["x-content-type-options"] == "nosniff"
    assert safe_response.headers["referrer-policy"] == "no-referrer"
