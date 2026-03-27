"""V19: Add model column to sessions table."""

from __future__ import annotations

import logging

import aiosqlite

logger = logging.getLogger(__name__)


async def up(db: aiosqlite.Connection) -> None:
    await db.execute("ALTER TABLE sessions ADD COLUMN model TEXT")
    logger.info("v019: added model column to sessions table")
