"""FastAPI dependency injection utilities.

Provides shared dependencies for API routes, configured by app factory.
"""

from titrack.db.repository import Repository


def get_repository() -> Repository:
    """Dependency injection for repository - set by app factory.

    This function is replaced by app.py's create_app() with an actual
    repository instance via dependency_overrides.

    Raises:
        NotImplementedError: If not configured (should never happen in production)
    """
    raise NotImplementedError("Repository not configured")
