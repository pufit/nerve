"""V18: Add tags column to tasks table."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    await db.execute("ALTER TABLE tasks ADD COLUMN tags TEXT DEFAULT ''")
    logger.info("v018: added tags column to tasks table")
