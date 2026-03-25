"""Task dataclass, status enum, frontmatter parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DEFERRED = "deferred"


@dataclass
class Task:
    """Represents a task."""
    id: str
    title: str
    file_path: str
    status: TaskStatus = TaskStatus.PENDING
    source: str = "manual"
    source_url: str = ""
    deadline: str = ""
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    escalation_level: int = 0
    last_reminded_at: str = ""
    content: str = ""

    @classmethod
    def from_db_row(cls, row: dict) -> Task:
        raw_tags = row.get("tags", "") or ""
        return cls(
            id=row["id"],
            title=row["title"],
            file_path=row["file_path"],
            status=TaskStatus(row.get("status", "pending")),
            source=row.get("source", "manual"),
            source_url=row.get("source_url", ""),
            deadline=row.get("deadline", ""),
            tags=parse_tags_string(raw_tags),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            escalation_level=row.get("escalation_level", 0),
            last_reminded_at=row.get("last_reminded_at", ""),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "file_path": self.file_path,
            "status": self.status.value,
            "source": self.source,
            "source_url": self.source_url,
            "deadline": self.deadline,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "escalation_level": self.escalation_level,
            "last_reminded_at": self.last_reminded_at,
        }


def parse_tags_string(raw: str) -> list[str]:
    """Parse a comma-separated tags string into a sorted, deduplicated list."""
    if not raw:
        return []
    return sorted({t.strip().lower() for t in raw.split(",") if t.strip()})


def tags_to_string(tags: list[str]) -> str:
    """Convert a list of tags to a comma-separated string for DB storage."""
    return ",".join(sorted({t.strip().lower() for t in tags if t.strip()}))


def parse_task_frontmatter(content: str) -> dict[str, str]:
    """Parse frontmatter fields from a task markdown file.

    Looks for **Key:** Value patterns.
    """
    fields = {}
    for match in re.finditer(r"\*\*(\w+):\*\*\s*(.+)", content):
        key = match.group(1).lower()
        value = match.group(2).strip()
        fields[key] = value
    return fields


def parse_task_title(content: str) -> str:
    """Extract the title from a task markdown file (first H1)."""
    match = re.match(r"#\s+(.+)", content)
    return match.group(1).strip() if match else "Untitled"
