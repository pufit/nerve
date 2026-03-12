"""SourceRunner — pure ingestion pipeline.

Reads cursor from DB, calls source.fetch(), persists records to the
source_messages inbox, optionally condenses long content via LLM,
and advances the cursor. No processing (agent/memorize/notify) —
consumption is handled separately by consumer tools.

Pipeline: fetch → source.preprocess → persist → LLM condense → advance cursor
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from nerve.sources.models import IngestResult, SourceRecord

if TYPE_CHECKING:
    from nerve.db import Database
    from nerve.sources.base import Source

logger = logging.getLogger(__name__)

# Records with content longer than this (after source.preprocess) are sent
# to a fast LLM for extraction/condensation.
_CONDENSE_THRESHOLD = 800  # chars

_CONDENSE_PROMPT = (
    "Extract the essential information from this source record content.\n"
    "Rules:\n"
    "- Keep: key facts, amounts, dates, names, identifiers, action items, deadlines\n"
    "- Remove: legal disclaimers, marketing copy, boilerplate, footer text, "
    "tracking links, unsubscribe text\n"
    "- Preserve the original structure and key details\n"
    "- Return ONLY the cleaned content, no preamble or commentary\n"
    "- If the message is mostly noise, return just the 1-2 core facts"
)


class SourceRunner:
    """Fetches records from a source and persists them to the inbox.

    Pure ingestion — no agent processing. Consumption happens via
    consumer tools (poll_source, read_source).

    Args:
        source: The data source to fetch from.
        db: Database for cursor persistence and logging.
        batch_size: Max records per fetch.
        job_id: Cron job ID for logging (default: "source:<name>").
        condense: Enable LLM condensation for long records.
        condense_config: Dict with 'api_key' and 'model' for Haiku condensation.
        ttl_days: TTL for persisted source messages.
    """

    def __init__(
        self,
        source: Source,
        db: Database,
        batch_size: int = 50,
        job_id: str = "",
        condense: bool = False,
        condense_config: dict[str, str] | None = None,
        ttl_days: int = 7,
    ):
        self.source = source
        self.db = db
        self.batch_size = batch_size
        self.job_id = job_id or f"source:{source.source_name}"
        self.condense = condense
        self.condense_config = condense_config or {}
        self.ttl_days = ttl_days
        self._lock = asyncio.Lock()
        self._condense_client: Any | None = None  # Lazy AsyncAnthropic

    async def run(self) -> IngestResult:
        """Full ingestion cycle: fetch → preprocess → persist → condense → advance cursor.

        Uses a per-runner lock to prevent concurrent execution (e.g. cron
        firing while a manual sync is in progress).  If the lock is already
        held, the call returns immediately with 0 records.
        """
        if self._lock.locked():
            logger.info("Source %s: sync already in progress, skipping", self.source.source_name)
            return IngestResult(records_ingested=0)

        async with self._lock:
            return await self._run_locked()

    async def _run_locked(self) -> IngestResult:
        """Actual run logic, called under lock."""
        cursor = await self.db.get_sync_cursor(self.source.source_name)
        logger.info(
            "Source %s: fetching (cursor=%s, batch_size=%d)",
            self.source.source_name, cursor, self.batch_size,
        )

        try:
            result = await self.source.fetch(cursor, limit=self.batch_size)
        except Exception as e:
            logger.error("Source %s fetch failed: %s", self.source.source_name, e, exc_info=True)
            return IngestResult(records_ingested=0, error=str(e))

        if not result.records:
            # Even with 0 records, advance cursor if it changed
            # (e.g., Telegram baseline establishing a cursor with no records)
            if result.next_cursor and result.next_cursor != cursor:
                await self.db.set_sync_cursor(self.source.source_name, result.next_cursor)
                logger.info(
                    "Source %s: no records, cursor advanced to %s",
                    self.source.source_name, result.next_cursor,
                )
            else:
                logger.info("Source %s: no new records", self.source.source_name)
            return IngestResult(records_ingested=0)

        # Ingestion pipeline:
        # 1. Source-specific cleanup (e.g., Gmail boilerplate stripping)
        records = await self.source.preprocess(result.records)

        # 2. Persist to inbox (post-preprocess, pre-condense — human-readable)
        await self._persist_to_inbox(records)

        # 3. LLM-based condensation for still-long records (configurable per source)
        if self.condense:
            pre_condense = {r.id: r.content for r in records}
            records = await self._condense_long_content(records)
            # Track which records were actually condensed (for debug view)
            processed_map = {
                r.id: r.content for r in records
                if r.content != pre_condense.get(r.id)
            }
            if processed_map:
                await self._update_processed_content(processed_map)

        # 4. Advance source cursor (ingestion complete)
        if result.next_cursor is not None:
            await self.db.set_sync_cursor(self.source.source_name, result.next_cursor)
            logger.info(
                "Source %s: %d records ingested, cursor -> %s",
                self.source.source_name, len(records), result.next_cursor,
            )

        return IngestResult(records_ingested=len(records))

    # ------------------------------------------------------------------
    # Inbox persistence
    # ------------------------------------------------------------------

    async def _persist_to_inbox(self, records: list[SourceRecord]) -> None:
        """Save records to the source_messages table for inbox display."""
        try:
            await self.db.insert_source_messages(
                records, source=self.source.source_name, ttl_days=self.ttl_days,
            )
        except Exception as e:
            logger.warning(
                "Failed to persist %d records to inbox: %s", len(records), e,
            )

    async def _update_processed_content(self, processed_map: dict[str, str]) -> None:
        """Update processed_content on inbox messages after condensation."""
        try:
            await self.db.update_source_messages_processed(
                self.source.source_name, list(processed_map.keys()), processed_map,
            )
        except Exception as e:
            logger.warning("Failed to update processed content: %s", e)

    # ------------------------------------------------------------------
    # Condensation
    # ------------------------------------------------------------------

    async def _get_condense_client(self) -> Any | None:
        """Get or create the shared AsyncAnthropic client for condensation."""
        if self._condense_client is not None:
            return self._condense_client
        api_key = self.condense_config.get("api_key")
        if not api_key:
            return None
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic package not available for content condensation")
            return None
        base_url = self.condense_config.get("base_url")
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url.rstrip("/")
        self._condense_client = anthropic.AsyncAnthropic(**kwargs)
        return self._condense_client

    async def _condense_long_content(
        self, records: list[SourceRecord],
    ) -> list[SourceRecord]:
        """Use a fast LLM to condense records with long content.

        Applies to ALL source types — any record whose content exceeds
        _CONDENSE_THRESHOLD after source.preprocess() gets sent to Haiku
        for extraction of essential information.

        On failure (import error, API error, timeout), the original content
        is preserved — this step never blocks the pipeline.
        """
        model = self.condense_config.get("model")
        if not model:
            return records

        long_records = [r for r in records if len(r.content) > _CONDENSE_THRESHOLD]
        if not long_records:
            return records

        client = await self._get_condense_client()
        if not client:
            return records

        logger.info(
            "Source %s: condensing %d/%d records with %s",
            self.source.source_name, len(long_records), len(records), model,
        )
        sem = asyncio.Semaphore(5)

        async def condense_one(record: SourceRecord) -> None:
            async with sem:
                original_len = len(record.content)
                try:
                    response = await asyncio.wait_for(
                        client.messages.create(
                            model=model,
                            max_tokens=1024,
                            messages=[{
                                "role": "user",
                                "content": (
                                    f"{_CONDENSE_PROMPT}\n\n"
                                    f"---\n\n"
                                    f"{record.content}"
                                ),
                            }],
                        ),
                        timeout=30,
                    )
                    condensed = response.content[0].text
                    record.content = condensed
                    logger.debug(
                        "Condensed %s: %d → %d chars",
                        record.id, original_len, len(condensed),
                    )
                except Exception as e:
                    logger.warning(
                        "LLM condense failed for record %s (%d chars), keeping original: %s",
                        record.id, original_len, e,
                    )

        await asyncio.gather(*[condense_one(r) for r in long_records])
        return records
