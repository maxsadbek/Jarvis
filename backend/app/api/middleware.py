"""API Middleware.

Provides CORS, authentication, request logging, and rate limiting.
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import settings


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the FastAPI application."""

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Request-ID",
            "X-Client-ID",
        ],
    )

    # --- Request Logging ---
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        """Log all API requests."""
        start_time = time.time()

        response = await call_next(request)

        elapsed = (time.time() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} "
            f"({elapsed:.0f}ms)"
        )
        return response

    logger.info("Middleware configured")
