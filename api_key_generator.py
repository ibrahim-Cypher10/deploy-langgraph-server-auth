"""
API Key Generation Utilities for LangGraph Server Authentication

This module provides secure API key generation and validation functions
for use with the LangGraph server's authentication middleware.
"""

import secrets
import base64
from typing import Optional


def generate_api_key(
    length: int = 32,
    prefix: Optional[str] = None,
    use_base64: bool = True
) -> str:
    """
    Generate a cryptographically secure API key.
    
    Args:
        length: Length of the random part of the key in bytes (default: 32)
        prefix: Optional prefix to add to the key (e.g., "luna_", "api_")
        use_base64: If True, use URL-safe base64 encoding; if False, use hex
        
    Returns:
        str: A secure API key
    """
    # Generate cryptographically secure random bytes
    random_bytes = secrets.token_bytes(length)
    
    if use_base64:
        # Use URL-safe base64 encoding (no padding)
        key_part = base64.urlsafe_b64encode(random_bytes).decode('ascii').rstrip('=')
    else:
        # Use hexadecimal encoding
        key_part = random_bytes.hex()
    
    # Add prefix if provided
    if prefix:
        return f"{prefix}{key_part}"
    
    return key_part


if __name__ == "__main__":
    print("\nGenerating a standard API key for Rocket...")
    key = generate_api_key(prefix="rocket_")
    print(f"\n🔑 API key: \n\n{key}\n")
