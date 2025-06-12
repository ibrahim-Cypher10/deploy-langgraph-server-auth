#!/usr/bin/env python3
"""
Authentication Proxy Server for LangGraph

This server acts as a proxy in front of the standard LangGraph server,
adding authentication while keeping the LangGraph server completely unchanged.

Architecture:
- This proxy server handles authentication and CORS
- Standard LangGraph server runs on a different port (internal)
- All authenticated requests are forwarded to the LangGraph server
- No modifications needed to graph.py or LangGraph configuration
"""

import os
import sys
import logging
import asyncio
import subprocess
from typing import Optional

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response, JSONResponse
from starlette.requests import Request

# Import our auth middleware
try:
    # Try importing from the container location first
    from middleware.auth_middleware import APIKeyAuthMiddleware
except ImportError:
    # Fall back to local development location
    from auth_middleware import APIKeyAuthMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
PROXY_PORT = int(os.getenv("PORT", 8000))
# Use a dedicated internal port for LangGraph server
# This avoids conflicts and is predictable
LANGGRAPH_PORT = int(os.getenv("LANGGRAPH_INTERNAL_PORT", 8123))  # Use LangGraph's default
LANGGRAPH_URL = f"http://localhost:{LANGGRAPH_PORT}"

# Validate port configuration
if PROXY_PORT == LANGGRAPH_PORT:
    raise ValueError(f"Port conflict: Proxy and LangGraph cannot use the same port {PROXY_PORT}")

logger.info(f"Port configuration: Proxy={PROXY_PORT}, LangGraph={LANGGRAPH_PORT}")


class LangGraphProxyMiddleware(BaseHTTPMiddleware):
    """Middleware that forwards authenticated requests to the LangGraph server."""
    
    def __init__(self, app, langgraph_url: str):
        super().__init__(app)
        self.langgraph_url = langgraph_url
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 minute timeout for long requests
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Forward the request to LangGraph server."""
        
        # Handle health checks locally (don't forward to LangGraph)
        if request.url.path in ["/ok", "/health", "/health-detailed"]:
            return await self._handle_health_check(request)
        
        # Forward all other requests to LangGraph server
        try:
            # Build the target URL
            target_url = f"{self.langgraph_url}{request.url.path}"
            if request.url.query:
                target_url += f"?{request.url.query}"
            
            # Get request body if present
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
            
            # Forward headers (excluding host)
            headers = dict(request.headers)
            headers.pop("host", None)  # Remove host header to avoid conflicts
            
            # Make the request to LangGraph server
            response = await self.client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True
            )
            
            # Return the response from LangGraph server
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
            
        except httpx.ConnectError:
            logger.error(f"Failed to connect to LangGraph server at {self.langgraph_url}")
            return JSONResponse(
                status_code=503,
                content={
                    "error": "LangGraph server unavailable",
                    "detail": f"Could not connect to internal LangGraph server at {self.langgraph_url}"
                }
            )
        except Exception as e:
            logger.error(f"Error forwarding request to LangGraph server: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Proxy error",
                    "detail": str(e)
                }
            )
    
    async def _handle_health_check(self, request: Request) -> Response:
        """Handle health check requests locally."""
        if request.url.path == "/health-detailed":
            # Detailed health check
            health_status = {
                "status": "healthy",
                "service": "LangGraph Auth Proxy",
                "proxy_port": PROXY_PORT,
                "langgraph_port": LANGGRAPH_PORT,
                "environment_variables": {
                    "DATABASE_URI": "✓ Set" if os.getenv('DATABASE_URI') else "✗ Missing",
                    "LANGSMITH_API_KEY": "✓ Set" if os.getenv('LANGSMITH_API_KEY') else "✗ Missing",
                    "ROCKET_API_KEY": "✓ Set" if os.getenv('ROCKET_API_KEY') else "✗ Missing"
                }
            }
            
            # Check if LangGraph server is responding
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.langgraph_url}/ok")
                    health_status["langgraph_server"] = "✓ Responding" if response.status_code == 200 else f"✗ Error {response.status_code}"
            except Exception as e:
                health_status["langgraph_server"] = f"✗ Not responding: {e}"
            
            return JSONResponse(health_status)
        else:
            # Simple health check - forward to LangGraph server
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{self.langgraph_url}/ok")
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )
            except Exception:
                return JSONResponse(status_code=503, content={"status": "unhealthy"})


def create_proxy_app() -> Starlette:
    """Create the proxy application with authentication middleware."""
    logger.info("Creating proxy application...")
    
    # Create the base app
    app = Starlette()
    
    # Add middleware in reverse order (last added runs first)
    # Order: Request → CORS → Auth → Proxy → LangGraph Server

    # 1. Add proxy middleware first (runs last - forwards to LangGraph)
    app.add_middleware(LangGraphProxyMiddleware, langgraph_url=LANGGRAPH_URL)

    # 2. Add authentication middleware second (runs second - validates API keys)
    app.add_middleware(APIKeyAuthMiddleware)

    # 3. Add CORS middleware last (runs first - handles preflight requests)
    cors_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]

    if cors_origins:
        logger.info(f"CORS allowed origins: {cors_origins}")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        logger.info("CORS allowed origins: []")
    
    logger.info("Proxy application created successfully")
    return app


async def start_langgraph_server():
    """Start the internal LangGraph server using uvicorn."""
    logger.info(f"Starting internal LangGraph server on port {LANGGRAPH_PORT}...")

    # Set up environment for LangGraph API server
    env = os.environ.copy()
    env["PORT"] = str(LANGGRAPH_PORT)
    env["HOST"] = "127.0.0.1"  # Only bind to localhost for security

    # Use the correct command for LangGraph API server
    cmd = ["uvicorn", "langgraph_api.server:app", "--host", "127.0.0.1", "--port", str(LANGGRAPH_PORT)]

    try:
        logger.info(f"Starting LangGraph server: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Give it a moment to start
        await asyncio.sleep(2)

        # Check if process is still running
        if process.returncode is None:
            logger.info(f"LangGraph server started successfully with PID {process.pid} on port {LANGGRAPH_PORT}")
            return process
        else:
            logger.error(f"LangGraph server failed to start with return code {process.returncode}")
            raise RuntimeError(f"LangGraph server process exited with code {process.returncode}")

    except FileNotFoundError as e:
        logger.error(f"uvicorn command not found: {e}")
        raise RuntimeError("uvicorn not available in container")
    except Exception as e:
        logger.error(f"Failed to start LangGraph server: {e}")
        raise


async def wait_for_langgraph_server(max_wait: int = 60):
    """Wait for the LangGraph server to be ready."""
    logger.info("Waiting for LangGraph server to be ready...")
    
    for _ in range(max_wait):
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get(f"{LANGGRAPH_URL}/ok")
                if response.status_code == 200:
                    logger.info("LangGraph server is ready!")
                    return True
        except Exception:
            pass
        
        await asyncio.sleep(1)
    
    logger.error(f"LangGraph server did not become ready within {max_wait} seconds")
    return False


async def main():
    """Main function to start the proxy server."""
    logger.info("Starting LangGraph Authentication Proxy...")

    # Check if LangGraph server is already running
    logger.info("Checking if LangGraph server is already running...")
    langgraph_ready = await wait_for_langgraph_server(max_wait=30)

    langgraph_process = None
    if not langgraph_ready:
        logger.info("LangGraph server not detected, starting it...")
        try:
            langgraph_process = await start_langgraph_server()

            # Wait for LangGraph server to be ready
            langgraph_ready = await wait_for_langgraph_server()
            if not langgraph_ready:
                logger.error("LangGraph server failed to start properly")
                return

        except Exception as e:
            logger.error(f"Failed to start LangGraph server: {e}")
            return
    else:
        logger.info("LangGraph server is already running!")

    try:
        # Create and start the proxy server
        app = create_proxy_app()

        logger.info(f"Starting proxy server on port {PROXY_PORT}...")
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=PROXY_PORT,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()

    finally:
        # Clean up LangGraph server if we started it
        if langgraph_process:
            logger.info("Shutting down LangGraph server...")
            try:
                langgraph_process.terminate()
                await langgraph_process.wait()
            except Exception as e:
                logger.warning(f"Error shutting down LangGraph server: {e}")


if __name__ == "__main__":
    asyncio.run(main())
