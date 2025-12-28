"""In-memory stores for OAuth sessions.

These stores are shared between the OAuth endpoints.
Note: Access tokens and refresh tokens are now JWT-based (stateless)
and don't require storage - they're validated via signature verification.
"""

# OAuth client registration (dynamic client registration)
registered_clients: dict[str, dict] = {}

# Authorization codes (short-lived, used in code exchange)
authorization_codes: dict[str, dict] = {}

# Pending OAuth authorization requests (session_id -> oauth params)
pending_authorizations: dict[str, dict] = {}

# Authenticated user sessions (session_id -> user info)
authenticated_sessions: dict[str, dict] = {}
