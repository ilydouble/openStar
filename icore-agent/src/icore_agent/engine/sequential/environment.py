"""Execution environments for the sequential agent.

Mirrors mini-SWE-agent's environment abstraction:
  - LocalEnvironment  : subprocess.run on the host (dev / trusted)
  - DockerEnvironment : docker exec inside a named container (production)

Switching between them requires zero changes to SequentialAgent.
"""

from __future__ import annotations

import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from ...config import settings

log = structlog.get_logger()

# Truncate very long outputs to keep token costs sane
_MAX_OUTPUT_CHARS = 8_000


class BaseEnvironment(ABC):
    """Abstract execution environment."""

    @abstractmethod
    def execute(self, cmd: str, timeout: int = 60) -> str:
        """Run a bash command and return its combined stdout+stderr (truncated)."""
        ...

    def _truncate(self, text: str) -> str:
        if len(text) <= _MAX_OUTPUT_CHARS:
            return text
        half = _MAX_OUTPUT_CHARS // 2
        return text[:half] + f"\n... [truncated {len(text) - _MAX_OUTPUT_CHARS} chars] ...\n" + text[-half:]


@dataclass
class LocalEnvironment(BaseEnvironment):
    """Execute commands on the local host via subprocess.run.

    Each command is a fresh subprocess — no persistent shell state,
    exactly as mini-SWE-agent does it. Safe for development.
    """

    working_dir: str = field(default_factory=os.getcwd)

    def __post_init__(self) -> None:
        Path(self.working_dir).mkdir(parents=True, exist_ok=True)

    def execute(self, cmd: str, timeout: int = 60) -> str:
        log.debug("local_env_execute", cmd=cmd[:200], cwd=self.working_dir)
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.working_dir,
            )
            combined = result.stdout + result.stderr
            return self._truncate(combined) or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[TIMEOUT after {timeout}s]"
        except Exception as exc:
            return f"[ERROR: {exc}]"


@dataclass
class DockerEnvironment(BaseEnvironment):
    """Execute commands inside a running Docker container via `docker exec`.

    Production-safe: the agent never touches the host filesystem directly.
    """

    container_name: str = "icore-seq-sandbox"
    working_dir: str = "/workspace"

    def execute(self, cmd: str, timeout: int = 60) -> str:
        docker_cmd = (
            f"docker exec --workdir {self.working_dir} "
            f"{self.container_name} bash -c {repr(cmd)}"
        )
        log.debug("docker_env_execute", cmd=cmd[:200], container=self.container_name)
        try:
            result = subprocess.run(
                docker_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            combined = result.stdout + result.stderr
            return self._truncate(combined) or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[TIMEOUT after {timeout}s]"
        except Exception as exc:
            return f"[ERROR: {exc}]"
