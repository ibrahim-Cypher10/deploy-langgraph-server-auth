# Server Architecture - Modular Design

## Overview

The server has been refactored from a monolithic `server_proxy.py` file into a clean, modular architecture that follows production best practices for maintainability, testability, and scalability.

## New Directory Structure

```
server/
├── __init__.py                 # Package exports
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

## Component Responsibilities

### 1. **`server/server_proxy.py`** - Main Entry Point
- **Purpose**: Application startup and orchestration
- **Responsibilities**:
  - Configuration initialization
  - LangGraph server lifecycle management
  - Uvicorn server startup
  - Graceful shutdown handling

### 2. **`server/app.py`** - Application Factory
- **Purpose**: Assembles the complete application
- **Responsibilities**:
  - Creates Starlette application
  - Configures middleware stack in correct order
  - Provides middleware configuration summary

### 3. **`server/middleware/auth.py`** - Authentication
- **Purpose**: API key authentication
- **Responsibilities**:
  - Validates API keys from headers or query params
  - Handles authentication bypass for internal paths
  - Provides clear authentication error responses

### 4. **`server/middleware/cors.py`** - CORS Configuration
- **Purpose**: Cross-Origin Resource Sharing setup
- **Responsibilities**:
  - Configures CORS middleware
  - Validates CORS origins
  - Provides CORS configuration helpers

### 5. **`server/proxy.py`** - Request Forwarding
- **Purpose**: Forwards requests to LangGraph server
- **Responsibilities**:
  - Handles both streaming and regular requests
  - Manages HTTP client connections
  - Provides error handling for backend failures

### 6. **`server/health.py`** - Health Monitoring
- **Purpose**: Health check endpoints
- **Responsibilities**:
  - Simple and detailed health checks
  - Backend server status monitoring
  - Configuration status reporting

### 7. **`server/langgraph_manager.py`** - Process Management
- **Purpose**: LangGraph server lifecycle
- **Responsibilities**:
  - Starts/stops LangGraph server process
  - Monitors server readiness
  - Handles graceful shutdown

## Benefits of Modular Architecture

### ✅ **Separation of Concerns**
Each module has a single, well-defined responsibility:
- Authentication logic is isolated in `auth.py`
- Proxy logic is isolated in `proxy.py`
- Health checks are isolated in `health.py`

### ✅ **Testability**
Each component can be tested independently:
```python
# Test authentication middleware in isolation
from server.middleware.auth import APIKeyAuthMiddleware

# Test proxy logic without authentication
from server.proxy import LangGraphProxyMiddleware

# Test health checks without full server
from server.health import handle_health_check
```

### ✅ **Reusability**
Components can be reused in different contexts:
- Use `APIKeyAuthMiddleware` in other applications
- Use `LangGraphProxyMiddleware` without authentication
- Use health check functions in monitoring scripts

### ✅ **Maintainability**
- Easy to locate and modify specific functionality
- Clear dependencies between components
- Reduced risk of breaking changes

### ✅ **Scalability**
- Easy to add new middleware components
- Simple to extend existing functionality
- Clear patterns for future development

## Middleware Stack Order

The middleware is applied in this order (request flows top to bottom):

```
1. CORS Middleware (handles preflight requests)
   ↓
2. Authentication Middleware (validates API keys)
   ↓
3. LangGraph Proxy Middleware (forwards to backend)
   ↓
4. LangGraph Server (actual AI agent)
```

## Import Patterns

### Using Individual Components
```python
from server.middleware.auth import APIKeyAuthMiddleware
from server.middleware.cors import add_cors_middleware
from server.proxy import LangGraphProxyMiddleware
```

### Using Package Exports
```python
from server import create_proxy_app, LangGraphServerManager
from server.middleware import APIKeyAuthMiddleware, add_cors_middleware
```

## Configuration Integration

All components use the centralized configuration system:

```python
from config import get_config

def some_function():
    config = get_config()
    # Use config.api_key, config.cors_allowed_origins, etc.
```

## Error Handling Strategy

Each component handles errors at its level:
- **Authentication**: Returns 401 for invalid API keys
- **Proxy**: Returns 503 for backend connection failures
- **Health**: Returns 503 for unhealthy status
- **Manager**: Logs errors and provides status information

## Future Extensions

This architecture makes it easy to add:
- **Rate limiting middleware** in `server/middleware/rate_limit.py`
- **Logging middleware** in `server/middleware/logging.py`
- **Metrics collection** in `server/middleware/metrics.py`
- **Request validation** in `server/middleware/validation.py`

## Migration Benefits

The refactoring provides:
1. **Better code organization** - Easy to find and modify specific functionality
2. **Improved testing** - Each component can be tested in isolation
3. **Enhanced reusability** - Components can be used in other projects
4. **Clearer dependencies** - Explicit imports show component relationships
5. **Easier debugging** - Issues can be isolated to specific components
6. **Production readiness** - Follows industry best practices for server architecture

This modular design sets a solid foundation for scaling the server as requirements grow.
