"""Tests for houseofagents integration — config, service, runner, pipelines, streaming."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from nerve.houseofagents.config import HouseOfAgentsConfig
from nerve.houseofagents.pipelines import PipelineManager
from nerve.agent.streaming import StreamBroadcaster

# Detect whether the real binary is available for integration tests
HOA_BINARY = Path("~/.nerve/bin/houseofagents").expanduser()
HOA_CONFIG = Path("~/.config/houseofagents/config.toml").expanduser()
HAS_BINARY = HOA_BINARY.exists() and os.access(HOA_BINARY, os.X_OK)
HAS_CONFIG = HOA_CONFIG.exists()

requires_binary = pytest.mark.skipif(
    not HAS_BINARY, reason="houseofagents binary not installed"
)
requires_binary_and_config = pytest.mark.skipif(
    not (HAS_BINARY and HAS_CONFIG),
    reason="houseofagents binary or config not available",
)


# ------------------------------------------------------------------ #
#  HouseOfAgentsConfig                                                #
# ------------------------------------------------------------------ #


class TestHouseOfAgentsConfig:

    def test_defaults(self) -> None:
        cfg = HouseOfAgentsConfig()
        assert cfg.enabled is False
        assert cfg.default_mode == "relay"
        assert cfg.default_agents == ["Claude"]
        assert cfg.default_iterations == 3
        assert cfg.use_cli is True

    def test_from_dict_empty(self) -> None:
        cfg = HouseOfAgentsConfig.from_dict({})
        assert cfg.enabled is False
        assert cfg.default_mode == "relay"
        assert cfg.default_agents == ["Claude"]

    def test_from_dict_custom(self) -> None:
        cfg = HouseOfAgentsConfig.from_dict({
            "enabled": True,
            "default_mode": "swarm",
            "default_agents": ["Claude", "OpenAI"],
            "default_iterations": 5,
            "use_cli": False,
            "binary_path": "/opt/hoa",
        })
        assert cfg.enabled is True
        assert cfg.default_mode == "swarm"
        assert cfg.default_agents == ["Claude", "OpenAI"]
        assert cfg.default_iterations == 5
        assert cfg.use_cli is False
        assert cfg.binary_path == Path("/opt/hoa")

    def test_from_dict_agents_as_csv_string(self) -> None:
        cfg = HouseOfAgentsConfig.from_dict({
            "default_agents": "Claude, OpenAI, Gemini",
        })
        assert cfg.default_agents == ["Claude", "OpenAI", "Gemini"]

    def test_from_dict_path_expansion(self) -> None:
        cfg = HouseOfAgentsConfig.from_dict({
            "binary_path": "~/my-bin/hoa",
            "pipelines_dir": "~/pipelines",
        })
        assert "~" not in str(cfg.binary_path)
        assert "~" not in str(cfg.pipelines_dir)

    def test_wired_into_nerve_config(self) -> None:
        from nerve.config import NerveConfig
        nc = NerveConfig.from_dict({"houseofagents": {"enabled": True, "default_mode": "swarm"}})
        assert nc.houseofagents.enabled is True
        assert nc.houseofagents.default_mode == "swarm"

    def test_nerve_config_defaults_when_missing(self) -> None:
        from nerve.config import NerveConfig
        nc = NerveConfig.from_dict({})
        assert nc.houseofagents.enabled is False


# ------------------------------------------------------------------ #
#  PipelineManager                                                     #
# ------------------------------------------------------------------ #


class TestPipelineManager:

    def test_list_empty(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        assert pm.list_pipelines() == []

    def test_save_and_list(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        pm.save_pipeline("test-pipe", "# Test pipeline\ninitial_prompt = 'hello'\n")
        pipelines = pm.list_pipelines()
        assert len(pipelines) == 1
        assert pipelines[0]["id"] == "test-pipe"
        assert pipelines[0]["description"] == "Test pipeline"

    def test_get_pipeline(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        pm.save_pipeline("my-pipe", "# My pipe\ninitial_prompt = 'task'\n")
        p = pm.get_pipeline("my-pipe")
        assert p is not None
        assert p["id"] == "my-pipe"
        assert "initial_prompt" in p["content"]

    def test_get_nonexistent(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        assert pm.get_pipeline("nope") is None

    def test_get_path(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        pm.save_pipeline("x", "content")
        assert pm.get_path("x") is not None
        assert pm.get_path("y") is None

    def test_delete_pipeline(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        pm.save_pipeline("del-me", "content")
        assert pm.delete_pipeline("del-me") is True
        assert pm.delete_pipeline("del-me") is False
        assert pm.list_pipelines() == []

    def test_sanitise_id(self, tmp_path: Path) -> None:
        pm = PipelineManager(tmp_path / "pipelines")
        path = pm.save_pipeline("my pipe/test", "content")
        assert "my-pipe-test" in path.name

    def test_creates_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "dir"
        pm = PipelineManager(target)
        assert target.exists()


# ------------------------------------------------------------------ #
#  HoAService                                                          #
# ------------------------------------------------------------------ #


class TestHoAService:

    def _make_config(self, tmp_path: Path, enabled: bool = True) -> "NerveConfig":
        from nerve.config import NerveConfig
        return NerveConfig.from_dict({
            "houseofagents": {
                "enabled": enabled,
                "binary_path": str(tmp_path / "bin" / "houseofagents"),
                "config_path": str(tmp_path / "hoa-config.toml"),
                "pipelines_dir": str(tmp_path / "pipelines"),
            },
        })

    def test_is_available_false_when_missing(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        svc = HoAService(cfg)
        assert svc.is_available() is False

    def test_is_available_true_when_present(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        # Create a fake binary
        bin_path = tmp_path / "bin" / "houseofagents"
        bin_path.parent.mkdir(parents=True)
        bin_path.write_text("#!/bin/sh\necho test")
        bin_path.chmod(bin_path.stat().st_mode | stat.S_IXUSR)
        svc = HoAService(cfg)
        assert svc.is_available() is True

    def test_generate_config_creates_toml(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        cfg.anthropic_api_key = "sk-test-key"
        svc = HoAService(cfg)
        path = svc.generate_config()
        assert path.exists()
        content = path.read_text()
        assert "sk-test-key" in content
        assert "[[agents]]" in content
        assert 'name = "Claude"' in content

    def test_generate_config_includes_openai_when_present(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        cfg.anthropic_api_key = "sk-ant"
        cfg.openai_api_key = "sk-oai"
        svc = HoAService(cfg)
        path = svc.generate_config()
        content = path.read_text()
        assert 'name = "OpenAI"' in content
        assert "sk-oai" in content

    def test_generate_config_skips_openai_when_empty(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        cfg.anthropic_api_key = "sk-ant"
        cfg.openai_api_key = ""
        svc = HoAService(cfg)
        path = svc.generate_config()
        content = path.read_text()
        assert 'name = "OpenAI"' not in content

    def test_generate_config_idempotent(self, tmp_path: Path) -> None:
        from nerve.houseofagents.service import HoAService
        cfg = self._make_config(tmp_path)
        cfg.anthropic_api_key = "sk-first"
        svc = HoAService(cfg)
        svc.generate_config()
        # Second call should not overwrite
        cfg.anthropic_api_key = "sk-second"
        svc2 = HoAService(cfg)
        path = svc2.generate_config()
        content = path.read_text()
        assert "sk-first" in content
        assert "sk-second" not in content


# ------------------------------------------------------------------ #
#  HoARunner — unit tests with mock subprocess                        #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
class TestHoARunnerUnit:

    def _make_runner(self, tmp_path: Path) -> "HoARunner":
        from nerve.config import NerveConfig
        from nerve.houseofagents.service import HoAService
        from nerve.houseofagents.runner import HoARunner

        cfg = NerveConfig.from_dict({
            "workspace": str(tmp_path),
            "houseofagents": {
                "enabled": True,
                "binary_path": str(tmp_path / "bin" / "houseofagents"),
                "config_path": str(tmp_path / "hoa.toml"),
                "pipelines_dir": str(tmp_path / "pipelines"),
            },
        })
        # Create fake binary + config
        (tmp_path / "bin").mkdir(parents=True, exist_ok=True)
        fake_bin = tmp_path / "bin" / "houseofagents"
        fake_bin.write_text("#!/bin/sh\n")
        fake_bin.chmod(0o755)
        (tmp_path / "hoa.toml").write_text("")

        svc = HoAService(cfg)
        return HoARunner(svc)

    async def test_parses_ndjson_events(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)

        ndjson_lines = [
            b'{"event":"run_info","agents":["Claude"]}\n',
            b'{"event":"agent_started","agent":"Claude","provider":"anthropic","iteration":1}\n',
            b'{"event":"agent_log","agent":"Claude","iteration":1,"message":"Sending request..."}\n',
        ]
        stdout_data = b'{"output_dir":"/tmp/test"}\n'

        mock_proc = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.__aiter__ = lambda self: self
        mock_proc.stderr.__anext__ = AsyncMock(side_effect=list(ndjson_lines) + [StopAsyncIteration()])
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.read = AsyncMock(return_value=stdout_data)
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.execute(prompt="test", mode="relay")

        assert result.success
        assert len(result.events) == 3
        assert result.events[0]["event"] == "run_info"
        assert result.events[1]["agent"] == "Claude"
        assert result.events[1]["provider"] == "anthropic"
        assert result.stdout_json == {"output_dir": "/tmp/test"}

    async def test_broadcasts_to_session(self, tmp_path: Path) -> None:
        """Events should be broadcast to the session's WebSocket listeners."""
        runner = self._make_runner(tmp_path)

        ndjson_lines = [
            b'{"event":"agent_started","agent":"Claude","provider":"anthropic","iteration":1}\n',
            b'{"event":"agent_log","agent":"Claude","iteration":1,"message":"Working..."}\n',
        ]
        stdout_data = b'""'

        mock_proc = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.__aiter__ = lambda self: self
        mock_proc.stderr.__anext__ = AsyncMock(side_effect=list(ndjson_lines) + [StopAsyncIteration()])
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.read = AsyncMock(return_value=stdout_data)
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        # Set up a real broadcaster with a listener
        received: list[dict] = []

        async def listener(sid: str, msg: dict):
            received.append(msg)

        bc = StreamBroadcaster()
        await bc.register("test-session", "test-listener", listener)

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("nerve.houseofagents.runner.broadcaster", bc, create=True), \
             patch.dict("sys.modules", {}):
            # Patch the import inside runner
            import nerve.agent.streaming
            original = nerve.agent.streaming.broadcaster
            nerve.agent.streaming.broadcaster = bc
            try:
                result = await runner.execute(
                    prompt="test", mode="relay", session_id="test-session",
                )
            finally:
                nerve.agent.streaming.broadcaster = original

        assert len(received) == 2
        assert received[0]["type"] == "hoa_progress"
        assert received[0]["session_id"] == "test-session"
        assert received[0]["event"]["event"] == "agent_started"
        assert received[1]["event"]["message"] == "Working..."

    async def test_handles_non_json_stderr(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)

        ndjson_lines = [
            b'Some non-JSON warning text\n',
            b'{"event":"agent_started","agent":"Claude"}\n',
            b'Another warning\n',
        ]

        mock_proc = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.__aiter__ = lambda self: self
        mock_proc.stderr.__anext__ = AsyncMock(side_effect=list(ndjson_lines) + [StopAsyncIteration()])
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.read = AsyncMock(return_value=b'""')
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.execute(prompt="test")

        # Only JSON lines should be in events
        assert len(result.events) == 1
        assert result.events[0]["agent"] == "Claude"
        # But all lines should be in stderr_log
        assert "non-JSON warning" in result.stderr_log

    async def test_nonzero_exit_code(self, tmp_path: Path) -> None:
        runner = self._make_runner(tmp_path)

        mock_proc = AsyncMock()
        mock_proc.stderr = AsyncMock()
        mock_proc.stderr.__aiter__ = lambda self: self
        mock_proc.stderr.__anext__ = AsyncMock(side_effect=[
            b'{"event":"error","message":"provider failed"}\n',
            StopAsyncIteration(),
        ])
        mock_proc.stdout = AsyncMock()
        mock_proc.stdout.read = AsyncMock(return_value=b'')
        mock_proc.wait = AsyncMock(return_value=None)
        mock_proc.returncode = 2

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await runner.execute(prompt="test")

        assert not result.success
        assert result.exit_code == 2


# ------------------------------------------------------------------ #
#  Integration tests — require real binary                            #
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
class TestHoARunnerIntegration:

    @requires_binary_and_config
    async def test_real_binary_streams_ndjson(self) -> None:
        """Verify the real binary emits NDJSON on stderr without --quiet."""
        proc = await asyncio.create_subprocess_exec(
            str(HOA_BINARY),
            "--prompt", "say hello in one word",
            "--mode", "relay",
            "--agents", "Claude",
            "--iterations", "1",
            "--output-format", "json",
            "--config", str(HOA_CONFIG),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        events: list[dict] = []
        try:
            assert proc.stderr is not None
            for _ in range(20):
                line = await asyncio.wait_for(proc.stderr.readline(), timeout=10.0)
                if not line:
                    break
                text = line.decode().strip()
                if text:
                    try:
                        events.append(json.loads(text))
                    except json.JSONDecodeError:
                        pass
        except asyncio.TimeoutError:
            pass
        finally:
            proc.kill()
            await proc.wait()

        # Should have at least run_info and agent_started
        event_types = [e.get("event") for e in events]
        assert "run_info" in event_types, f"Expected run_info, got: {event_types}"
        assert "agent_started" in event_types, f"Expected agent_started, got: {event_types}"

    @requires_binary_and_config
    async def test_real_broadcast_streaming(self) -> None:
        """Verify events actually reach a broadcaster listener in real-time."""
        received: list[dict] = []

        async def listener(sid: str, msg: dict):
            received.append(msg)

        bc = StreamBroadcaster()
        await bc.register("int-test", "listener", listener)

        from nerve.config import NerveConfig
        from nerve.houseofagents.service import HoAService
        from nerve.houseofagents.runner import HoARunner
        import nerve.agent.streaming

        cfg = NerveConfig.from_dict({
            "houseofagents": {
                "enabled": True,
                "binary_path": str(HOA_BINARY),
                "config_path": str(HOA_CONFIG),
            },
        })
        svc = HoAService(cfg)
        runner = HoARunner(svc)

        original = nerve.agent.streaming.broadcaster
        nerve.agent.streaming.broadcaster = bc
        try:
            # Use a task with timeout so we don't wait forever
            async def run_with_timeout():
                return await runner.execute(
                    prompt="say hello in one word",
                    mode="relay",
                    agents=["Claude"],
                    iterations=1,
                    session_id="int-test",
                )

            result = await asyncio.wait_for(run_with_timeout(), timeout=120.0)
        except asyncio.TimeoutError:
            pytest.skip("HoA execution timed out (expected in CI)")
        finally:
            nerve.agent.streaming.broadcaster = original

        # Verify events were broadcast
        hoa_events = [m for m in received if m.get("type") == "hoa_progress"]
        assert len(hoa_events) > 0, f"No hoa_progress events received. Total messages: {len(received)}"
        assert hoa_events[0]["session_id"] == "int-test"
        assert "event" in hoa_events[0]


# ------------------------------------------------------------------ #
#  Singleton service                                                   #
# ------------------------------------------------------------------ #


class TestSingleton:

    def test_init_returns_none_when_disabled(self) -> None:
        from nerve.config import NerveConfig
        from nerve.houseofagents import init_hoa_service
        cfg = NerveConfig.from_dict({"houseofagents": {"enabled": False}})
        assert init_hoa_service(cfg) is None

    def test_init_returns_service_when_enabled(self, tmp_path: Path) -> None:
        from nerve.config import NerveConfig
        from nerve.houseofagents import init_hoa_service
        cfg = NerveConfig.from_dict({
            "houseofagents": {
                "enabled": True,
                "binary_path": str(tmp_path / "fake"),
            },
        })
        svc = init_hoa_service(cfg)
        assert svc is not None

    def test_get_raises_when_not_initialized(self) -> None:
        import nerve.houseofagents as hoa_mod
        old = hoa_mod._service
        hoa_mod._service = None
        try:
            with pytest.raises(RuntimeError, match="not initialised"):
                hoa_mod.get_hoa_service()
        finally:
            hoa_mod._service = old
