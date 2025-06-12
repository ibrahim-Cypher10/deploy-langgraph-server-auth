"""
Authentication Middleware for LangGraph Server

This module provides API key authentication middleware that can be easily
configured and reused across different server implementations.
"""

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse
from starlette.requests import Request

from config.environment import ServerConfig

logger = logging.getLogger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for API key authentication.

    Authentication is required if an API key is set in the configuration.
    Supports both header-based and query parameter-based authentication.
    """

    def __init__(self, app, config: ServerConfig) -> None:
        super().__init__(app)
        self.api_key = config.api_key
        self.api_key_required = config.api_key_required
        logger.info(f"API Key Authentication middleware initialized. Required: {self.api_key_required}")

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process each HTTP request for authentication."""

        # Skip authentication if not required
        if not self.api_key_required:
            logger.debug("API key not required, skipping authentication")
            return await call_next(request)

        # Skip authentication for OPTIONS requests (preflight)
        if request.method == "OPTIONS":
            logger.debug("OPTIONS request, skipping authentication")
            return await call_next(request)

        # Handle root path with a simple health check response
        if request.url.path == "/":
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "service": "LangGraph Server with Auth",
                    "message": "Server is running"
                }
            )

        # Handle favicon requests
        if request.url.path == "/favicon.ico":
            return Response(status_code=204)

        # Skip authentication for internal LangGraph endpoints and health checks
        if self._is_internal_path(request.url.path):
            logger.debug(f"Internal path {request.url.path}, skipping authentication")
            return await call_next(request)

        # Get API key from header or query parameter
        request_api_key = self._extract_api_key(request)

        # Validate API key
        if not request_api_key or request_api_key != self.api_key:
            logger.warning(f"Authentication failed for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"}
            )

        logger.debug(f"Authentication successful for {request.method} {request.url.path}")
        return await call_next(request)

    def _is_internal_path(self, path: str) -> bool:
        """Check if the path should skip authentication."""
        internal_paths = [
            "/ok", "/health", "/metrics", "/docs", "/openapi.json",
            "/health-detailed",
            "/__health__", "/ready", "/startup", "/shutdown"
        ]

        internal_prefixes = [
            "/_internal/",
            "/api/v1/health",
        ]

        return (path in internal_paths or
                any(path.startswith(prefix) for prefix in internal_prefixes))

    def _extract_api_key(self, request: Request) -> Optional[str]:
        """Extract API key from request headers or query parameters."""
        # Try header first (preferred method)
        api_key = request.headers.get("x-api-key")

        # Fall back to query parameter
        if not api_key:
            api_key = request.query_params.get("api-key")

        return api_key