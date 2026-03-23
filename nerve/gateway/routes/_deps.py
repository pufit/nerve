"""Centralized dependency container for route modules.

Replaces the module-level globals (_engine, _db, _notification_service)
that were previously scattered across routes.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nerve.agent.engine import AgentEngine
    from nerve.db import Database
    from nerve.notifications.service import NotificationService


@dataclass
class RouteDeps:
    engine: AgentEngine
    db: Database
    notification_service: NotificationService | None = None


_deps: RouteDeps | None = None


def init_deps(engine: AgentEngine, db: Database) -> None:
    """Initialize route dependencies. Called once during server startup."""
    global _deps
    _deps = RouteDeps(engine=engine, db=db)


def set_notification_service(service: NotificationService) -> None:
    """Wire notification service after it's created."""
    if _deps is None:
        raise RuntimeError("init_deps() must be called before set_notification_service()")
    _deps.notification_service = service


def get_deps() -> RouteDeps:
    """Get the dependency container. Raises if not initialized."""
    if _deps is None:
        raise RuntimeError("Route dependencies not initialized. Call init_deps() first.")
    return _deps
