"""Pipeline TOML management — filesystem-backed CRUD."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PipelineManager:
    """Manage pipeline TOML files on the filesystem."""

    def __init__(self, pipelines_dir: Path) -> None:
        self.dir = pipelines_dir.expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)

    def list_pipelines(self) -> list[dict[str, Any]]:
        """List all pipeline configs with basic metadata."""
        result: list[dict[str, Any]] = []
        for f in sorted(self.dir.glob("*.toml")):
            try:
                content = f.read_text(encoding="utf-8")
                # Extract description from first comment line
                description = ""
                for line in content.splitlines():
                    if line.startswith("#"):
                        description = line.lstrip("#").strip()
                        break

                result.append({
                    "id": f.stem,
                    "name": f.stem.replace("-", " ").replace("_", " ").title(),
                    "description": description,
                    "path": str(f),
                })
            except Exception:
                logger.warning("Failed to read pipeline %s", f)
        return result

    def get_pipeline(self, pipeline_id: str) -> dict[str, Any] | None:
        """Read a pipeline by ID.  Returns dict with id, name, content, path."""
        path = self.dir / f"{pipeline_id}.toml"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")

        description = ""
        for line in content.splitlines():
            if line.startswith("#"):
                description = line.lstrip("#").strip()
                break

        return {
            "id": pipeline_id,
            "name": pipeline_id.replace("-", " ").replace("_", " ").title(),
            "description": description,
            "content": content,
            "path": str(path),
        }

    def get_path(self, pipeline_id: str) -> Path | None:
        """Return filesystem path for a pipeline, or None."""
        path = self.dir / f"{pipeline_id}.toml"
        return path if path.exists() else None

    def save_pipeline(self, pipeline_id: str, content: str) -> Path:
        """Save or update a pipeline TOML."""
        # Sanitise ID
        safe_id = pipeline_id.replace(" ", "-").replace("/", "-")
        path = self.dir / f"{safe_id}.toml"
        path.write_text(content, encoding="utf-8")
        logger.info("Saved pipeline %s → %s", safe_id, path)
        return path

    def delete_pipeline(self, pipeline_id: str) -> bool:
        """Delete a pipeline file.  Returns True if it existed."""
        path = self.dir / f"{pipeline_id}.toml"
        if path.exists():
            path.unlink()
            logger.info("Deleted pipeline %s", pipeline_id)
            return True
        return False
