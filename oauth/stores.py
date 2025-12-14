"""In-memory stores for OAuth tokens and sessions.

These stores are shared between the OAuth middleware and endpoints.
In production, replace with Redis or a database.
"""

# OAuth client registration
registered_clients: dict[str, dict] = {}

# Authorization codes (short-lived, used in code exchange)
authorization_codes: dict[str, dict] = {}

# Access tokens (validated by middleware)
access_tokens: dict[str, dict] = {}

# Pending OAuth authorization requests (session_id -> oauth params)
pending_authorizations: dict[str, dict] = {}

# Authenticated user sessions (session_id -> user info)
authenticated_sessions: dict[str, dict] = {}
