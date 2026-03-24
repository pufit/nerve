"""houseofagents configuration dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


def _expand(p: str | Path, default: str) -> Path:
    val = str(p) if p else default
    return Path(val).expanduser()


@dataclass
class HouseOfAgentsConfig:
    """Optional houseofagents multi-agent runtime.

    When *enabled* is ``True`` the ``hoa_execute`` MCP tool becomes available
    inside agent sessions, allowing multi-agent relay / swarm / pipeline
    execution via the houseofagents CLI binary.
    """

    enabled: bool = False
    binary_path: Path = field(default_factory=lambda: Path("~/.nerve/bin/houseofagents"))
    config_path: Path = field(default_factory=lambda: Path("~/.config/houseofagents/config.toml"))
    pipelines_dir: Path = field(default_factory=lambda: Path("~/.nerve/houseofagents/pipelines"))
    default_mode: str = "relay"          # relay | swarm | pipeline
    default_agents: list[str] = field(default_factory=lambda: ["Claude"])
    default_iterations: int = 3
    use_cli: bool = True                 # CLI mode → agents get full tool access
    log_file: Path = field(default_factory=lambda: Path("~/.nerve/houseofagents.log"))

    @classmethod
    def from_dict(cls, d: dict) -> HouseOfAgentsConfig:
        agents_raw = d.get("default_agents", ["Claude"])
        if isinstance(agents_raw, str):
            agents_raw = [a.strip() for a in agents_raw.split(",") if a.strip()]
        return cls(
            enabled=d.get("enabled", False),
            binary_path=_expand(d.get("binary_path", ""), "~/.nerve/bin/houseofagents"),
            config_path=_expand(d.get("config_path", ""), "~/.config/houseofagents/config.toml"),
            pipelines_dir=_expand(d.get("pipelines_dir", ""), "~/.nerve/houseofagents/pipelines"),
            default_mode=d.get("default_mode", "relay"),
            default_agents=agents_raw,
            default_iterations=int(d.get("default_iterations", 3)),
            use_cli=d.get("use_cli", True),
            log_file=_expand(d.get("log_file", ""), "~/.nerve/houseofagents.log"),
        )
