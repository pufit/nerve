"""Tests for nerve.agent.engine — pure helpers (no SDK state)."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nerve.agent.engine import AgentEngine


@pytest.mark.parametrize(
    "value, model, expected",
    [
        # Opus 4.7 supports every level
        ("max",    "claude-opus-4-7",           "max"),
        ("xhigh",  "claude-opus-4-7",           "xhigh"),
        ("high",   "claude-opus-4-7",           "high"),
        # Dated alias resolves via substring match
        ("max",    "claude-opus-4-7-20260416",  "max"),
        # Opus 4.6: max OK, xhigh caps to high (not registered)
        ("max",    "claude-opus-4-6",           "max"),
        ("xhigh",  "claude-opus-4-6",           "high"),
        # Sonnet 4.6 tops out at high
        ("max",    "claude-sonnet-4-6",         "high"),
        ("xhigh",  "claude-sonnet-4-6",         "high"),
        ("high",   "claude-sonnet-4-6",         "high"),
        ("medium", "claude-sonnet-4-6",         "medium"),
        ("low",    "claude-sonnet-4-6",         "low"),
        # Unknown models (including Haiku which uses budget_tokens, not levels)
        # pass through unchanged — capping is a no-op for non-level-based thinking
        ("max",    "claude-haiku-4-5-20251001", "max"),
        ("max",    "some-future-model",         "max"),
        ("max",    None,                        "max"),
        ("max",    "",                          "max"),
        # Invalid effort string → None (same as the pre-existing behaviour)
        ("invalid", "claude-opus-4-7",          None),
        ("",        "claude-sonnet-4-6",        None),
    ],
)
def test_effective_effort(value, model, expected):
    assert AgentEngine._effective_effort(value, model) == expected


def test_effective_effort_model_default_none():
    # Signature symmetry with _parse_thinking_config
    assert AgentEngine._effective_effort("max") == "max"


# ---------------------------------------------------------------------------
# _sdk_resume_file_exists
# ---------------------------------------------------------------------------

def _make_engine(workspace: str = "/root/nerve-workspace") -> AgentEngine:
    """Minimal AgentEngine stub (only config.workspace is needed)."""
    engine = AgentEngine.__new__(AgentEngine)
    engine.config = SimpleNamespace(workspace=Path(workspace))
    return engine


class TestSdkResumeFileExists:
    def test_returns_true_when_file_present(self):
        engine = _make_engine()
        with patch("nerve.agent.engine.os.path.isfile", return_value=True):
            assert engine._sdk_resume_file_exists("some-session-id") is True

    def test_returns_false_when_file_missing(self):
        engine = _make_engine()
        with patch("nerve.agent.engine.os.path.isfile", return_value=False):
            assert engine._sdk_resume_file_exists("some-session-id") is False

    def test_fail_open_on_exception(self):
        """Any unexpected error returns True rather than crashing the turn."""
        engine = _make_engine()
        with patch("nerve.agent.engine.os.path.isfile", side_effect=OSError("denied")):
            assert engine._sdk_resume_file_exists("some-session-id") is True

    def test_path_encodes_workspace_slashes(self):
        """'/' in the workspace path are replaced with '-' in the projects subdir."""
        engine = _make_engine("/root/nerve-workspace")
        captured: dict = {}

        def _capture(path: str) -> bool:
            captured["path"] = path
            return True

        with patch("nerve.agent.engine.os.path.isfile", side_effect=_capture):
            engine._sdk_resume_file_exists("sid-abc")

        assert "-root-nerve-workspace" in captured["path"]
        assert "sid-abc.jsonl" in captured["path"]

    def test_path_ends_with_jsonl(self):
        """The constructed path always ends with <session_id>.jsonl."""
        engine = _make_engine("/workspace")
        captured: dict = {}

        def _capture(path: str) -> bool:
            captured["path"] = path
            return True

        with patch("nerve.agent.engine.os.path.isfile", side_effect=_capture):
            engine._sdk_resume_file_exists("myid")

        assert captured["path"].endswith("myid.jsonl")
