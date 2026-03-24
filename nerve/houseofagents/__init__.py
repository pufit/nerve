"""houseofagents — optional multi-agent execution runtime.

Provides relay, swarm, and pipeline (DAG) orchestration of Claude, OpenAI,
and Gemini agents via the houseofagents CLI binary.  Disabled by default;
enable in config.yaml under ``houseofagents.enabled: true``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nerve.config import NerveConfig
    from nerve.houseofagents.service import HoAService

_service: HoAService | None = None


def init_hoa_service(config: NerveConfig) -> HoAService | None:
    """Initialise the singleton HoA service.  Returns *None* when disabled."""
    global _service
    if not config.houseofagents.enabled:
        return None
    from nerve.houseofagents.service import HoAService as _Cls
    _service = _Cls(config)
    return _service


def get_hoa_service() -> HoAService:
    """Return the initialised service or raise if not available."""
    if _service is None:
        raise RuntimeError(
            "houseofagents service not initialised.  "
            "Is houseofagents.enabled set to true in config?"
        )
    return _service
