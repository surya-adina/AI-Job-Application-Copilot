"""Shared-secret authentication between the backend and the AI service.

Every route except /health requires the X-Service-Token header to match
AI_SERVICE_TOKEN. The service fails closed: when the token is not configured,
protected routes return 503 rather than running unauthenticated.
"""

import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

HEADER = "X-Service-Token"
PUBLIC_PATHS = {"/health"}
MIN_TOKEN_LENGTH = 32


def configured_token() -> str | None:
    token = os.getenv("AI_SERVICE_TOKEN", "").strip()
    return token or None


async def require_service_token(request: Request, call_next):
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    expected = configured_token()
    if expected is None or len(expected) < MIN_TOKEN_LENGTH:
        return JSONResponse(
            status_code=503,
            content={"detail": {"message": f"AI_SERVICE_TOKEN must be set (at least {MIN_TOKEN_LENGTH} characters)"}},
        )

    provided = request.headers.get(HEADER, "")
    if not hmac.compare_digest(provided.encode(), expected.encode()):
        return JSONResponse(status_code=401, content={"detail": {"message": "Invalid or missing service token"}})

    return await call_next(request)
