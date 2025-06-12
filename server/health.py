"""
Health Check Functionality for LangGraph Server

This module provides health check endpoints and utilities for monitoring
the server and LangGraph backend status.
"""

import logging
from typing import Dict, Any

import httpx
from starlette.responses import Response, JSONResponse
from starlette.requests import Request

from config.environment import get_config

logger = logging.getLogger(__name__)


async def handle_health_check(request: Request, langgraph_url: str) -> Response:
    """
    Handle health check requests with different levels of detail.
    
    Args:
        request: The incoming request
        langgraph_url: URL of the LangGraph server to check
        
    Returns:
        Response: Health check response
    """
    if request.url.path == "/health-detailed":
        return await _detailed_health_check(langgraph_url)
    else:
        return await _simple_health_check(langgraph_url)


async def _detailed_health_check(langgraph_url: str) -> JSONResponse:
    """
    Perform a detailed health check including configuration and backend status.
    
    Args:
        langgraph_url: URL of the LangGraph server to check
        
    Returns:
        JSONResponse: Detailed health status
    """
    try:
        config = get_config()
    except RuntimeError:
        # Configuration not loaded
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": "Configuration not loaded"
            }
        )

    # Build health status
    health_status = {
        "status": "healthy",
        "service": "LangGraph Auth Proxy",
        "proxy_port": config.proxy_port,
        "langgraph_port": config.langgraph_internal_port,
        "environment": config.environment,
        "environment_variables": {
            "DATABASE_URI": "✓ Set" if config.database_uri else "✗ Missing",
            "LANGSMITH_API_KEY": "✓ Set" if config.langsmith_api_key else "✗ Missing",
            "ROCKET_API_KEY": "✓ Set" if config.api_key else "✗ Missing"
        }
    }

    # Check LangGraph server status
    langgraph_status = await _check_langgraph_server(langgraph_url)
    health_status["langgraph_server"] = langgraph_status

    # Determine overall status
    if "✗" in langgraph_status:
        health_status["status"] = "degraded"

    return JSONResponse(health_status)


async def _simple_health_check(langgraph_url: str) -> Response:
    """
    Perform a simple health check by forwarding to LangGraph server.
    
    Args:
        langgraph_url: URL of the LangGraph server to check
        
    Returns:
        Response: Simple health status
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{langgraph_url}/ok")
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers)
            )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy"}
        )


async def _check_langgraph_server(langgraph_url: str) -> str:
    """
    Check the status of the LangGraph server.
    
    Args:
        langgraph_url: URL of the LangGraph server to check
        
    Returns:
        str: Status message
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{langgraph_url}/ok")
            if response.status_code == 200:
                return "✓ Responding"
            else:
                return f"✗ Error {response.status_code}"
    except httpx.ConnectError:
        return "✗ Not responding: Connection failed"
    except httpx.TimeoutException:
        return "✗ Not responding: Timeout"
    except Exception as e:
        return f"✗ Not responding: {e}"


def get_health_summary(config) -> Dict[str, Any]:
    """
    Get a summary of system health for logging or monitoring.
    
    Args:
        config: Server configuration
        
    Returns:
        Dict[str, Any]: Health summary
    """
    return {
        "service": "LangGraph Auth Proxy",
        "environment": config.environment,
        "proxy_port": config.proxy_port,
        "langgraph_port": config.langgraph_internal_port,
        "auth_enabled": config.api_key_required,
        "cors_enabled": bool(config.cors_allowed_origins),
        "tracing_enabled": config.langsmith_tracing,
    }
