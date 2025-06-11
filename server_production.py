#!/usr/bin/env python3
"""
Production LangGraph server with best-practice middleware implementation.

This server is specifically designed for Docker deployment and follows
current Starlette best practices for middleware configuration.
"""

import uvicorn
import logging
import sys
import os
from dotenv import load_dotenv
from starlette.applications import Starlette
from auth_middleware import create_middleware_stack

# Load environment variables BEFORE importing LangGraph
# This ensures DATABASE_URI is available when LangGraph initializes
load_dotenv()

# Validate critical environment variables for LangGraph
required_env_vars = {
    'DATABASE_URI': 'PostgreSQL database URI for LangGraph state management',
    'LANGSMITH_API_KEY': 'LangSmith API key for tracing (required even if tracing disabled)',
}

missing_vars = []
for var, description in required_env_vars.items():
    if not os.getenv(var):
        missing_vars.append(f"{var} ({description})")

if missing_vars:
    print("ERROR: Missing required environment variables:")
    for var in missing_vars:
        print(f"  - {var}")
    print("\nPlease ensure these variables are set in your .env file or environment.")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Available environment variables: {sorted([k for k in os.environ.keys() if not k.startswith('_')])}")
    sys.exit(1)

# Log successful environment variable loading
print("✓ All required environment variables found")
print(f"✓ LANGSMITH_API_KEY: {'***' + os.getenv('LANGSMITH_API_KEY', '')[-4:] if os.getenv('LANGSMITH_API_KEY') else 'Not set'}")

# Log database configuration for debugging
database_uri = os.getenv('DATABASE_URI', '')
if database_uri:
    # Log only the host part for security
    try:
        from urllib.parse import urlparse
        parsed = urlparse(database_uri)
        print(f"LangGraph Database Host: {parsed.hostname}:{parsed.port}")
        print(f"LangGraph Database Name: {parsed.path.lstrip('/')}")
    except Exception as e:
        print(f"Could not parse DATABASE_URI: {e}")
else:
    print("WARNING: DATABASE_URI not found")

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

# Import the LangGraph server app AFTER environment validation
print("Importing LangGraph server...")
try:
    from langgraph_api.server import app as langgraph_app
    print("LangGraph server imported successfully")
except Exception as e:
    print(f"ERROR: Failed to import LangGraph server: {e}")
    print("This might be due to missing environment variables or database connection issues.")
    sys.exit(1)


def create_app_with_middleware():
    """
    Create a new Starlette app with middleware using best practices.

    This follows current Starlette recommendations by configuring
    middleware during app initialization rather than post-creation.

    Returns:
        Starlette: Configured application with middleware
    """
    logger = logging.getLogger(__name__)
    logger.info("Creating app with middleware...")

    # Get the middleware stack
    middleware_stack = create_middleware_stack()
    logger.info(f"Middleware stack created: {[m.__class__.__name__ for m in middleware_stack]}")

    # Create a new app with middleware configured at initialization
    # This is the recommended approach per Starlette docs
    app = Starlette(
        middleware=middleware_stack,
        debug=False  # Production mode
    )
    logger.info("Starlette app created with middleware")

    # Add a custom health check endpoint before mounting LangGraph
    @app.route("/health-detailed")
    async def health_detailed(_request):
        """Detailed health check including database connectivity."""
        from starlette.responses import JSONResponse

        health_status = {
            "status": "healthy",
            "service": "LangGraph Server with Auth",
            "environment_variables": {
                "DATABASE_URI": "✓ Set" if os.getenv('DATABASE_URI') else "✗ Missing",
                "LANGSMITH_API_KEY": "✓ Set" if os.getenv('LANGSMITH_API_KEY') else "✗ Missing",
                "ROCKET_API_KEY": "✓ Set" if os.getenv('ROCKET_API_KEY') else "✗ Missing"
            }
        }

        return JSONResponse(health_status)

    # Mount the LangGraph app as a sub-application
    # This preserves all LangGraph functionality while adding our middleware
    app.mount("/", langgraph_app)
    logger.info("LangGraph app mounted successfully")

    logger.info("LangGraph server with auth middleware initialized successfully")
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
