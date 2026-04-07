"""Token usage tracking data access methods."""

from __future__ import annotations


class UsageStore:
    """Mixin providing per-turn token usage persistence and aggregate queries."""

    async def record_turn_usage(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation: int,
        cache_read: int,
        max_context: int,
    ) -> None:
        """Record token usage for a single agent turn."""
        await self.db.execute(
            "INSERT INTO session_usage "
            "(session_id, input_tokens, output_tokens, "
            "cache_creation_input_tokens, cache_read_input_tokens, max_context_tokens) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, input_tokens, output_tokens, cache_creation, cache_read, max_context),
        )
        await self.db.commit()

    async def get_session_usage_totals(self, session_id: str) -> dict:
        """Aggregate token usage for a session."""
        async with self.db.execute(
            """
            SELECT
                COUNT(*) as turns,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(cache_creation_input_tokens), 0) as total_cache_creation,
                COALESCE(SUM(cache_read_input_tokens), 0) as total_cache_read,
                MAX(max_context_tokens) as max_context
            FROM session_usage WHERE session_id = ?
            """,
            (session_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] == 0:
                return {"turns": 0, "total_input": 0, "total_output": 0,
                        "total_cache_creation": 0, "total_cache_read": 0,
                        "max_context": 0}
            return dict(row)

    async def get_usage_by_period(self, days: int = 7) -> list[dict]:
        """Daily aggregated usage for the past N days."""
        async with self.db.execute(
            """
            SELECT
                DATE(created_at) as date,
                COUNT(*) as turns,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens,
                SUM(cache_creation_input_tokens) as cache_creation,
                SUM(cache_read_input_tokens) as cache_read
            FROM session_usage
            WHERE created_at >= DATE('now', ?)
            GROUP BY DATE(created_at)
            ORDER BY date DESC
            """,
            (f"-{days} days",),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def get_usage_by_source(self, days: int = 7) -> list[dict]:
        """Usage aggregated by session source (web, cron, telegram, etc.)."""
        async with self.db.execute(
            """
            SELECT
                s.source,
                COUNT(DISTINCT u.session_id) as sessions,
                COUNT(*) as turns,
                SUM(u.input_tokens) as input_tokens,
                SUM(u.output_tokens) as output_tokens,
                SUM(u.cache_creation_input_tokens) as cache_creation,
                SUM(u.cache_read_input_tokens) as cache_read
            FROM session_usage u
            JOIN sessions s ON s.id = u.session_id
            WHERE u.created_at >= DATE('now', ?)
            GROUP BY s.source
            ORDER BY SUM(u.input_tokens) + SUM(u.output_tokens) DESC
            """,
            (f"-{days} days",),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def get_cache_hit_rate(
        self, session_id: str | None = None, days: int = 7,
    ) -> dict:
        """Calculate cache hit rate: cache_read / total_input."""
        if session_id:
            query = """
                SELECT
                    COALESCE(SUM(cache_read_input_tokens), 0) as total_read,
                    COALESCE(SUM(cache_creation_input_tokens), 0) as total_creation,
                    COALESCE(SUM(input_tokens), 0) as total_input
                FROM session_usage WHERE session_id = ?
            """
            params: tuple = (session_id,)
        else:
            query = """
                SELECT
                    COALESCE(SUM(cache_read_input_tokens), 0) as total_read,
                    COALESCE(SUM(cache_creation_input_tokens), 0) as total_creation,
                    COALESCE(SUM(input_tokens), 0) as total_input
                FROM session_usage WHERE created_at >= DATE('now', ?)
            """
            params = (f"-{days} days",)

        async with self.db.execute(query, params) as cursor:
            row = await cursor.fetchone()
            total_read = row[0] or 0
            total_creation = row[1] or 0
            total_input = row[2] or 0
            rate = total_read / total_input if total_input > 0 else 0.0
            return {
                "rate": round(rate, 4),
                "total_read": total_read,
                "total_creation": total_creation,
                "total_input": total_input,
            }

    async def get_usage_summary(self, days: int = 7) -> dict:
        """High-level usage summary for the past N days."""
        async with self.db.execute(
            """
            SELECT
                COUNT(*) as turns,
                COUNT(DISTINCT session_id) as sessions,
                COALESCE(SUM(input_tokens), 0) as total_input,
                COALESCE(SUM(output_tokens), 0) as total_output,
                COALESCE(SUM(cache_read_input_tokens), 0) as total_cache_read,
                COALESCE(SUM(cache_creation_input_tokens), 0) as total_cache_creation
            FROM session_usage
            WHERE created_at >= DATE('now', ?)
            """,
            (f"-{days} days",),
        ) as cursor:
            row = await cursor.fetchone()
            if not row or row[0] == 0:
                return {"turns": 0, "sessions": 0, "total_input": 0,
                        "total_output": 0, "total_cache_read": 0,
                        "total_cache_creation": 0, "est_cost_usd": 0}
            d = dict(row)
            d["est_cost_usd"] = round(estimate_cost_from_totals(d), 4)
            return d

    async def delete_session_usage(self, session_id: str) -> None:
        """Delete all usage records for a session (cascade on delete)."""
        await self.db.execute(
            "DELETE FROM session_usage WHERE session_id = ?", (session_id,),
        )
        await self.db.commit()


def estimate_turn_cost(usage: dict) -> float:
    """Estimate USD cost from a single turn's token counts.

    Uses Claude Opus 4 pricing:
    - Input: $15/M tokens
    - Output: $75/M tokens
    - Cache read: $1.50/M tokens (90% discount)
    - Cache write: $18.75/M tokens (25% premium)
    """
    input_t = usage.get("input_tokens", 0)
    output_t = usage.get("output_tokens", 0)
    cache_read = usage.get("cache_read_input_tokens", 0)
    cache_create = usage.get("cache_creation_input_tokens", 0)

    # Non-cached input = total input - cache_read - cache_create
    fresh_input = max(0, input_t - cache_read - cache_create)
    cost = (
        fresh_input * 15 / 1_000_000        # regular input
        + cache_read * 1.5 / 1_000_000      # cache read (90% off)
        + cache_create * 18.75 / 1_000_000  # cache write (25% premium)
        + output_t * 75 / 1_000_000         # output
    )
    return round(cost, 6)


def estimate_cost_from_totals(totals: dict) -> float:
    """Estimate USD cost from aggregated totals."""
    return estimate_turn_cost({
        "input_tokens": totals.get("total_input", 0),
        "output_tokens": totals.get("total_output", 0),
        "cache_read_input_tokens": totals.get("total_cache_read", 0),
        "cache_creation_input_tokens": totals.get("total_cache_creation", 0),
    })
