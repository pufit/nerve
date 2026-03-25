"""Task data access methods."""

from __future__ import annotations

from datetime import datetime, timezone


class TaskStore:
    """Mixin providing task CRUD, FTS search, and escalation operations."""

    async def upsert_task(
        self,
        task_id: str,
        file_path: str,
        title: str,
        status: str = "pending",
        source: str | None = None,
        source_url: str | None = None,
        deadline: str | None = None,
        tags: str = "",
        content: str = "",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        async with self._atomic():
            await self.db.execute(
                """INSERT INTO tasks (id, file_path, title, status, source, source_url, deadline, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       file_path=excluded.file_path, title=excluded.title, status=excluded.status,
                       source=excluded.source, source_url=excluded.source_url,
                       deadline=excluded.deadline, tags=excluded.tags, updated_at=?""",
                (task_id, file_path, title, status, source, source_url, deadline, tags, now, now, now),
            )
            # Sync FTS index — include tags so tag names are searchable
            fts_content = f"{content} {tags.replace(',', ' ')}" if tags else content
            await self.db.execute("DELETE FROM tasks_fts WHERE task_id = ?", (task_id,))
            await self.db.execute(
                "INSERT INTO tasks_fts (task_id, title, content) VALUES (?, ?, ?)",
                (task_id, title, fts_content),
            )

    async def get_task(self, task_id: str) -> dict | None:
        async with self.db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def list_tasks(self, status: str | None = None, tag: str | None = None, limit: int = 100) -> list[dict]:
        conditions: list[str] = []
        params: list = []

        if status == "all":
            pass
        elif status:
            conditions.append("status = ?")
            params.append(status)
        else:
            conditions.append("status != 'done'")

        if tag:
            # Match exact tag in comma-separated list: ,tag, within ,tags,
            conditions.append("',' || tags || ',' LIKE ?")
            params.append(f"%,{tag.strip().lower()},%")

        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        params.append(limit)
        async with self.db.execute(
            f"SELECT * FROM tasks{where} ORDER BY deadline ASC NULLS LAST, created_at DESC LIMIT ?",
            tuple(params),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def update_task_status(self, task_id: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, task_id),
        )
        await self.db.commit()

    async def update_task_tags(self, task_id: str, tags: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tasks SET tags = ?, updated_at = ? WHERE id = ?",
            (tags, now, task_id),
        )
        await self.db.commit()

    # Short words and common stop words that add noise to FTS searches.
    _FTS_STOP_WORDS = frozenset({
        "a", "an", "the", "is", "at", "by", "on", "in", "to", "of", "for",
        "and", "or", "not", "it", "be", "as", "do", "if", "so", "no", "up",
        "my", "we", "he", "me",
    })

    @classmethod
    def _build_fts_query(cls, query: str, mode: str = "and") -> str:
        """Build an FTS5 query from a user search string.

        Args:
            query: Raw search text.
            mode: 'and' — all terms must match (strict, good for user search).
                  'or'  — any term can match (permissive, good for dedup).
        """
        import re
        clean = re.sub(r'["\*\(\)\-:/\\#]', " ", query)
        words = [
            w for w in clean.split()
            if w.strip() and len(w) > 1 and w.lower() not in cls._FTS_STOP_WORDS
        ]
        if not words:
            return ""
        joiner = " OR " if mode == "or" else " "
        return joiner.join(f'"{w}"' for w in words)

    async def search_tasks(
        self, query: str, status: str | None = None, tag: str | None = None, limit: int = 20,
    ) -> list[dict]:
        """Search tasks using FTS5 full-text search on title and content.

        Args:
            query: Search words — tokenized and matched via FTS5.
            status: Filter by status. None = non-done, 'all' = everything.
            tag: Filter by exact tag name.
            limit: Max results.
        """
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        conditions = ["t.id IN (SELECT task_id FROM tasks_fts WHERE tasks_fts MATCH ?)"]
        params: list = [fts_query]
        if status == "all":
            pass  # no status filter
        elif status:
            conditions.append("t.status = ?")
            params.append(status)
        else:
            conditions.append("t.status != 'done'")
        if tag:
            conditions.append("',' || t.tags || ',' LIKE ?")
            params.append(f"%,{tag.strip().lower()},%")
        where = " AND ".join(conditions)
        params.append(limit)
        async with self.db.execute(
            f"SELECT t.* FROM tasks t WHERE {where} ORDER BY t.updated_at DESC LIMIT ?",
            tuple(params),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def search_tasks_similar(
        self, query: str, limit: int = 10,
    ) -> list[dict]:
        """Find tasks similar to query using OR semantics + FTS5 ranking.

        Unlike search_tasks (AND, strict), this uses OR (any word matches)
        and orders by BM25 relevance.  Designed for duplicate detection —
        searches all statuses including done.
        """
        fts_query = self._build_fts_query(query, mode="or")
        if not fts_query:
            return []

        async with self.db.execute(
            "SELECT t.* FROM tasks t "
            "JOIN tasks_fts f ON f.task_id = t.id "
            "WHERE tasks_fts MATCH ? "
            "ORDER BY f.rank LIMIT ?",
            (fts_query, limit),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def find_tasks_by_source_url(
        self, source_url: str, limit: int = 10,
    ) -> list[dict]:
        """Find tasks with an exact source_url match (most reliable dedup)."""
        async with self.db.execute(
            "SELECT * FROM tasks WHERE source_url = ? ORDER BY updated_at DESC LIMIT ?",
            (source_url, limit),
        ) as cursor:
            return [dict(row) async for row in cursor]

    async def rebuild_fts(self) -> None:
        """Clear the FTS index. Caller must re-populate via upsert_task()."""
        await self.db.execute("DELETE FROM tasks_fts")
        await self.db.commit()

    async def update_task_escalation(
        self, task_id: str, level: int, reminded_at: str | None = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.execute(
            "UPDATE tasks SET escalation_level = ?, last_reminded_at = ?, updated_at = ? WHERE id = ?",
            (level, reminded_at or now, now, task_id),
        )
        await self.db.commit()

    async def get_task_health_stats(self) -> dict:
        """Get task and FTS counts for diagnostics (replaces raw sqlite3 calls)."""
        try:
            async with self.db.execute("SELECT COUNT(*) FROM tasks") as cur:
                task_count = (await cur.fetchone())[0]
            async with self.db.execute("SELECT COUNT(*) FROM tasks_fts") as cur:
                fts_count = (await cur.fetchone())[0]
            async with self.db.execute("SELECT COUNT(*) FROM tasks WHERE status != 'done'") as cur:
                active_count = (await cur.fetchone())[0]
            async with self.db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'done'") as cur:
                done_count = (await cur.fetchone())[0]
            return {
                "total": task_count,
                "active": active_count,
                "done": done_count,
                "fts_indexed": fts_count,
                "fts_ok": task_count == fts_count,
            }
        except Exception:
            return {}
