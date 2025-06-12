"""
CORS Configuration for LangGraph Server

This module provides CORS middleware configuration helpers to ensure
consistent CORS setup across different server implementations.
"""

import logging
from typing import List

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware

from config import ServerConfig

logger = logging.getLogger(__name__)


def add_cors_middleware(app: Starlette, config: ServerConfig) -> None:
    """
    Add CORS middleware to the application if origins are configured.

    Args:
        app: The Starlette application instance
        config: Server configuration containing CORS settings
    """
    if config.cors_allowed_origins:
        logger.info(f"CORS allowed origins: {config.cors_allowed_origins}")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=config.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        logger.info("CORS allowed origins: [] (CORS disabled)")


def get_cors_config(config: ServerConfig) -> dict:
    """
    Get CORS configuration as a dictionary.

    Args:
        config: Server configuration containing CORS settings

    Returns:
        dict: CORS configuration parameters
    """
    if not config.cors_allowed_origins:
        return {}

    return {
        "allow_origins": config.cors_allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def validate_cors_origins(origins: List[str]) -> List[str]:
    """
    Validate and clean CORS origins list.

    Args:
        origins: List of origin URLs

    Returns:
        List[str]: Validated and cleaned origins

    Raises:
        ValueError: If any origin is invalid
    """
    validated_origins = []

    for origin in origins:
        origin = origin.strip()
        if not origin:
            continue

        # Basic validation - should start with http:// or https://
        if not (origin.startswith('http://') or origin.startswith('https://')):
            raise ValueError(f"Invalid CORS origin '{origin}': must start with http:// or https://")

        # Remove trailing slash for consistency
        origin = origin.rstrip('/')
        validated_origins.append(origin)

    return validated_origins