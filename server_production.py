#!/usr/bin/env python3
"""
Production LangGraph server with best-practice middleware implementation.

This server is specifically designed for Docker deployment and follows
current Starlette best practices for middleware configuration.
"""

import uvicorn
import logging
import sys
from starlette.applications import Starlette
from auth_middleware import create_middleware_stack

# Configure logging to ensure all LangGraph logs are visible
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific loggers to INFO level to capture LangGraph API logs
logging.getLogger("langgraph_api").setLevel(logging.INFO)
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# Import the LangGraph server app
from langgraph_api.server import app as langgraph_app


def create_app_with_middleware():
    """
    Create a new Starlette app with middleware using best practices.

    This follows current Starlette recommendations by configuring
    middleware during app initialization rather than post-creation.

    Returns:
        Starlette: Configured application with middleware
    """
    # Get the middleware stack
    middleware_stack = create_middleware_stack()

    # Create a new app with middleware configured at initialization
    # This is the recommended approach per Starlette docs
    app = Starlette(
        middleware=middleware_stack,
        debug=False  # Production mode
    )

    # Mount the LangGraph app as a sub-application
    # This preserves all LangGraph functionality while adding our middleware
    app.mount("/", langgraph_app)

    # Log that the app has been created with middleware
    logger = logging.getLogger(__name__)
    logger.info("LangGraph server with auth middleware initialized successfully")
    logger.info(f"Middleware stack: {[m.__class__.__name__ for m in middleware_stack]}")

    return app


# Create the app using the modern approach
app = create_app_with_middleware()


if __name__ == "__main__":
    # Run the server in production mode
    uvicorn.run(
        "server_production:app",  # Direct reference to this module
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )
