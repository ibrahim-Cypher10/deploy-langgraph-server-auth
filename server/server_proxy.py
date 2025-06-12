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

This is the main entry point that assembles all the modular components.
"""

import logging
import asyncio

import uvicorn

# Import centralized configuration
from server.config import init_config

# Import server components
from server import create_proxy_app, LangGraphServerManager

logger = logging.getLogger(__name__)


async def main():
    """Main function to start the proxy server."""
    logger.info("Starting LangGraph Authentication Proxy...")

    # Initialize configuration first - this will validate all settings
    try:
        app_config = init_config()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your environment variables and try again.")
        return

    # Initialize LangGraph server manager
    langgraph_manager = LangGraphServerManager(app_config)

    # Check if LangGraph server is already running
    logger.info("Checking if LangGraph server is already running...")
    langgraph_ready = await langgraph_manager.is_running()

    if not langgraph_ready:
        logger.info("LangGraph server not detected, starting it...")
        try:
            success = await langgraph_manager.start_server()
            if not success:
                logger.error("Failed to start LangGraph server")
                return

            # Wait for LangGraph server to be ready
            langgraph_ready = await langgraph_manager.wait_for_ready()
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
        app = create_proxy_app(app_config)

        logger.info(f"Starting proxy server on port {app_config.proxy_port}...")
        uvicorn_config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=app_config.proxy_port,
            log_level=app_config.log_level.lower()
        )
        server = uvicorn.Server(uvicorn_config)
        await server.serve()

    finally:
        # Clean up LangGraph server if we started it
        await langgraph_manager.stop_server()


if __name__ == "__main__":
    asyncio.run(main())
