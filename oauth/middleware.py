"""OAuth middleware for MCP endpoints.

Validates Bearer tokens and enforces creator-only access control.
Uses JWT for stateless token validation - tokens survive server restarts.
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import load_config
from oauth.jwt_utils import verify_access_token

logger = logging.getLogger(__name__)

# Load config for creator-only access check
_config = load_config()


def get_server_url() -> str:
    """Get the server URL for OAuth metadata."""
    import os
    return _config.tunnel_url or os.getenv("SERVER_URL", "https://simplemcpserver-production-e610.up.railway.app")


class MCPOAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate OAuth Bearer tokens for Streamable HTTP MCP endpoint."""

    async def dispatch(self, request: Request, call_next):
        server_url = get_server_url()

        # Check Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.info("[AUTH] Request rejected: no Bearer token")
            return JSONResponse(
                {"error": "unauthorized", "error_description": "Missing or invalid Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{server_url}/.well-known/oauth-protected-resource"'}
            )

        token = auth_header[7:]

        # Verify JWT token (stateless - no storage lookup needed)
        token_data = verify_access_token(token, issuer=server_url)

        if not token_data:
            logger.info("[AUTH] Request rejected: invalid or expired token")
            return JSONResponse(
                {"error": "unauthorized", "error_description": "Invalid or expired token"},
                status_code=401,
                headers={"WWW-Authenticate": f'Bearer resource_metadata="{server_url}/.well-known/oauth-protected-resource"'}
            )

        # Check authorization (creator-only access)
        creator_user_id = _config.user_id
        connecting_user_id = token_data.get("sub")  # JWT uses 'sub' for user ID

        if creator_user_id and connecting_user_id != creator_user_id:
            logger.warning(f"[AUTH] Access denied: user {connecting_user_id} is not the server creator")
            return JSONResponse(
                {"error": "forbidden", "error_description": "Access denied: not authorized for this server"},
                status_code=403
            )

        logger.info(f"[AUTH] Request authorized: {token_data.get('email')}")
        return await call_next(request)
