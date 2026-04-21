"""Unit tests for the sequential agent (mini-SWE-agent style).

These tests use a DeterministicModel stub so no real LLM calls are made.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from icore_agent.engine.sequential.agent import SequentialAgent, SequentialResult, _CMD_PATTERN
from icore_agent.engine.sequential.environment import LocalEnvironment


# ── Fixtures ──────────────────────────────────────────────────────────────

class FakeEnvironment:
    """Echo the command back as output — no subprocess."""
    def execute(self, cmd: str, timeout: int = 60) -> str:
        return f"ran: {cmd}"


def make_agent(**kwargs) -> SequentialAgent:
    return SequentialAgent(
        model="fake/model",
        environment=FakeEnvironment(),
        **kwargs,
    )


# ── Command extraction ─────────────────────────────────────────────────────

def test_cmd_pattern_extracts_bash_block():
    text = "Some thinking...\n```bash\necho hello\n```\nmore text"
    match = _CMD_PATTERN.search(text)
    assert match is not None
    assert match.group(1).strip() == "echo hello"


def test_cmd_pattern_no_match():
    text = "No bash block here"
    assert _CMD_PATTERN.search(text) is None


# ── SequentialAgent.run ────────────────────────────────────────────────────

@patch("icore_agent.engine.sequential.agent.completion")
def test_run_completes_on_task_complete(mock_completion):
    """Agent should stop and return 'complete' when LLM outputs TASK_COMPLETE."""
    mock_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="TASK_COMPLETE: done!"))]
    )
    agent = make_agent()
    result = agent.run("echo hello")
    assert isinstance(result, SequentialResult)
    assert result.status == "complete"
    assert result.output == "done!"
    assert result.steps == 1


@patch("icore_agent.engine.sequential.agent.completion")
def test_run_fails_on_task_failed(mock_completion):
    mock_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="TASK_FAILED: no access"))]
    )
    agent = make_agent()
    result = agent.run("rm /etc/passwd")
    assert result.status == "failed"
    assert "no access" in result.output


@patch("icore_agent.engine.sequential.agent.completion")
def test_run_executes_bash_then_completes(mock_completion):
    """Simulate: step1 → bash cmd, step2 → TASK_COMPLETE."""
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content="```bash\necho hello\n```"))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content="TASK_COMPLETE: printed hello"))]),
    ]
    mock_completion.side_effect = responses
    agent = make_agent()
    result = agent.run("print hello")
    assert result.status == "complete"
    assert result.steps == 2
    # History: system + user + assistant(cmd) + user(output) + assistant(done)
    assert len(result.history) == 5


@patch("icore_agent.engine.sequential.agent.completion")
def test_run_timeout_on_max_steps(mock_completion):
    """Should return 'timeout' after max_steps without terminal condition."""
    mock_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="```bash\necho loop\n```"))]
    )
    agent = make_agent(max_steps=3)
    result = agent.run("infinite task")
    assert result.status == "timeout"
    assert result.steps == 3


# ── LocalEnvironment ──────────────────────────────────────────────────────

def test_local_environment_runs_simple_command(tmp_path):
    env = LocalEnvironment(working_dir=str(tmp_path))
    output = env.execute("echo icore-agent-test")
    assert "icore-agent-test" in output


def test_local_environment_timeout(tmp_path):
    env = LocalEnvironment(working_dir=str(tmp_path))
    output = env.execute("sleep 10", timeout=1)
    assert "TIMEOUT" in output


def test_local_environment_error_command(tmp_path):
    env = LocalEnvironment(working_dir=str(tmp_path))
    output = env.execute("exit 1")
    # Should not raise; stderr/empty is acceptable
    assert isinstance(output, str)
