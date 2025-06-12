# Server Architecture

## Overview

The LangGraph Authentication Proxy uses a modular architecture that separates concerns into focused components. This design makes the codebase maintainable, testable, and easy to understand.

## Directory Structure

```
server/
├── __init__.py                 # Package exports
├── config.py                  # Server configuration management
├── server_proxy.py            # Main entry point (simplified)
├── app.py                     # Application factory
├── proxy.py                   # LangGraph proxy middleware
├── health.py                  # Health check functionality
├── langgraph_manager.py       # LangGraph server lifecycle management
└── middleware/
    ├── __init__.py            # Middleware package exports
    ├── auth.py                # Authentication middleware
    └── cors.py                # CORS configuration helpers
```

## How the Server Works

The server acts as an authentication proxy that sits in front of a LangGraph server. Here's how requests flow through the system:

```
Client Request → CORS → Authentication → Proxy → LangGraph Server
```

### Component Responsibilities

#### **`server/config.py`** - Configuration Management
Centralizes all server configuration with validation and type safety.
- Loads environment variables with proper defaults
- Validates configuration at startup (fail-fast approach)
- Provides type-safe access to settings throughout the application

#### **`server/server_proxy.py`** - Application Entry Point
The main script that starts the entire system.
- Initializes configuration and validates environment
- Starts the internal LangGraph server if needed
- Creates and runs the proxy server with Uvicorn
- Handles graceful shutdown

#### **`server/app.py`** - Application Factory
Assembles all components into a complete Starlette application.
- Creates the base Starlette app
- Adds middleware in the correct order
- Configures CORS, authentication, and proxy layers

#### **`server/middleware/auth.py`** - Authentication Layer
Handles API key authentication for incoming requests.
- Checks for API keys in headers (`x-api-key`) or query parameters
- Allows unauthenticated access to health checks and internal endpoints
- Returns 401 errors for invalid or missing API keys

#### **`server/middleware/cors.py`** - CORS Configuration
Manages Cross-Origin Resource Sharing settings.
- Configures allowed origins from environment variables
- Provides helper functions for CORS setup
- Validates origin URLs

#### **`server/proxy.py`** - Request Forwarding
The core component that forwards authenticated requests to LangGraph.
- Handles both regular HTTP requests and streaming responses
- Manages HTTP client connections with proper timeouts
- Provides error handling when LangGraph server is unavailable

#### **`server/health.py`** - Health Monitoring
Provides health check endpoints for monitoring.
- Simple health checks (`/ok`, `/health`)
- Detailed health checks (`/health-detailed`) with configuration status
- Monitors LangGraph server availability

#### **`server/langgraph_manager.py`** - Process Management
Manages the lifecycle of the internal LangGraph server.
- Starts LangGraph server using uvicorn
- Waits for server readiness before accepting requests
- Handles graceful shutdown of managed processes

## Request Flow

Understanding how a request moves through the system:

### 1. **Client Makes Request**
A client sends an HTTP request to the proxy server (e.g., `POST /threads/thread_1/runs/stream`)

### 2. **CORS Middleware** (if configured)
- Handles preflight OPTIONS requests
- Adds appropriate CORS headers
- Allows or blocks based on origin

### 3. **Authentication Middleware**
- Extracts API key from `x-api-key` header or `api-key` query parameter
- Validates the key against the configured `ROCKET_API_KEY`
- Bypasses authentication for health check endpoints
- Returns 401 if authentication fails

### 4. **Proxy Middleware**
- Forwards authenticated requests to the internal LangGraph server
- Handles both regular requests and streaming responses
- Manages HTTP client connections and timeouts
- Returns 503 if LangGraph server is unavailable

### 5. **LangGraph Server**
- Processes the AI request using the configured agent
- Returns response (regular JSON or streaming events)

### 6. **Response Path**
The response flows back through the same middleware stack in reverse order.

## Configuration System

The server uses a centralized configuration system in `server/config.py`:

### Environment Variables
All configuration comes from environment variables:
- `PORT` - External proxy server port (default: 8000)
- `LANGGRAPH_INTERNAL_PORT` - Internal LangGraph server port (default: 8123)
- `ROCKET_API_KEY` - API key for authentication (optional)
- `CORS_ALLOWED_ORIGINS` - Comma-separated list of allowed origins
- `ENVIRONMENT` - development/staging/production
- `LOG_LEVEL` - DEBUG/INFO/WARNING/ERROR

### Configuration Loading
```python
from server.config import init_config

# Load and validate all configuration at startup
config = init_config()

# Access configuration throughout the application
from server.config import get_config
config = get_config()
print(f"Server running on port {config.proxy_port}")
```

### Validation
The configuration system validates settings at startup:
- Port conflict detection (proxy and LangGraph can't use same port)
- Environment-specific validation (production warnings)
- Type conversion with error handling

## Development Workflow

### Starting the Server
```bash
# Set environment variables
export ROCKET_API_KEY="your-api-key-here"
export CORS_ALLOWED_ORIGINS="http://localhost:3000"

# Run the server
python server/server_proxy.py
```

### Adding New Middleware
To add new middleware (e.g., rate limiting):

1. Create `server/middleware/rate_limit.py`
2. Implement middleware class
3. Add to `server/app.py` middleware stack
4. Update `server/middleware/__init__.py` exports

### Testing Components
Each component can be tested independently:
```python
# Test configuration
from server.config import ServerConfig
config = ServerConfig(proxy_port=8000, langgraph_internal_port=8123)

# Test authentication
from server.middleware.auth import APIKeyAuthMiddleware
auth = APIKeyAuthMiddleware(app, config)

# Test health checks
from server.health import handle_health_check
response = await handle_health_check(request, "http://localhost:8123")
```

## Error Handling

The server handles errors at different layers:

### Authentication Errors
- **401 Unauthorized**: Invalid or missing API key
- **403 Forbidden**: Access denied (future use)

### Proxy Errors
- **503 Service Unavailable**: LangGraph server is down or unreachable
- **500 Internal Server Error**: Unexpected proxy errors

### Health Check Responses
- **200 OK**: All systems healthy
- **503 Service Unavailable**: LangGraph server not responding

### Configuration Errors
- **Startup failure**: Invalid environment variables or port conflicts
- **Runtime warnings**: Missing optional configuration in production

## Deployment

### Docker
The included Dockerfile builds a container with:
- All server components in `/api/server/`
- Proper PYTHONPATH configuration
- Entrypoint at `/api/server/server_proxy.py`

### Environment Setup
Required for production:
```bash
export PORT=8000
export ROCKET_API_KEY="your-secure-api-key"
export ENVIRONMENT="production"
export CORS_ALLOWED_ORIGINS="https://yourdomain.com"
```

### Health Monitoring
Monitor these endpoints:
- `GET /ok` - Simple health check
- `GET /health-detailed` - Comprehensive status including configuration

This architecture provides a solid foundation for production deployment while remaining easy to understand and modify.
