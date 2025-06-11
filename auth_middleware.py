import os
import logging
from typing import List, Optional
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Set up logger for this module
logger = logging.getLogger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for API key authentication.

    This middleware validates API keys from either headers or query parameters
    and allows configuration through environment variables.
    """

    def __init__(self, app: ASGIApp, api_key: Optional[str] = None) -> None:
        super().__init__(app)
        # Get API key from parameter or environment variable
        self.api_key = api_key or os.getenv("ROCKET_API_KEY", "")
        self.api_key_required = bool(self.api_key.strip())

        print(f"API Key Authentication middleware initialized. Required: {self.api_key_required}")

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process each HTTP request for authentication.

        Args:
            request: The incoming HTTP request
            call_next: Function to continue to next middleware/handler

        Returns:
            Response object (either error or from next handler)
        """
        # Log incoming request for debugging
        logger.debug(f"Processing request: {request.method} {request.url.path}")

        # Skip authentication if not required
        if not self.api_key_required:
            logger.debug("API key not required, skipping authentication")
            return await call_next(request)

        # Skip authentication for OPTIONS requests (preflight)
        if request.method == "OPTIONS":
            logger.debug("OPTIONS request, skipping authentication")
            return await call_next(request)

        # Skip authentication for internal LangGraph endpoints and health checks
        internal_paths = ["/", "/ok", "/health", "/metrics"]
        if request.url.path in internal_paths:
            logger.debug(f"Internal path {request.url.path}, skipping authentication")
            return await call_next(request)

        # Get API key from header or query parameter (for streaming endpoints)
        request_api_key = request.headers.get("x-api-key")
        if not request_api_key:
            # Check query parameters for streaming endpoints
            request_api_key = request.query_params.get("api-key")

        # Validate API key
        if not request_api_key or request_api_key != self.api_key:
            logger.warning(f"Authentication failed for {request.method} {request.url.path}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"}
            )

        logger.debug(f"Authentication successful for {request.method} {request.url.path}")
        # Continue processing the request
        return await call_next(request)


def create_middleware_stack() -> List[Middleware]:
    """
    Create the middleware stack for the application.

    Returns:
        List of Middleware instances in the order they should be applied
    """
    # Get CORS configuration from environment variables
    allowed_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "")
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

    print(f"CORS allowed origins: {allowed_origins}")

    # Create middleware stack - order matters!
    # CORS first, then authentication
    middleware_stack = [
        Middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(APIKeyAuthMiddleware),
    ]

    return middleware_stack
