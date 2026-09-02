import uuid

# This app runs locally for one person and has no authentication. Rather than thread a
# nullable user through every query, the schema keeps real users/FKs and the initial
# migration seeds exactly one row with this ID.
#
# This constant is the single seam to change if multi-user ever arrives: swap the
# dependency below for one that resolves a session or token, and nothing else moves.
#
# The initial migration hard-codes the same literal. That duplication is deliberate —
# migrations must keep working as application code changes, so they don't import it.
DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_current_user_id() -> uuid.UUID:
    """FastAPI dependency resolving the acting user."""
    return DEFAULT_USER_ID
