"""Runtime exceptions for active agent run control."""


class AgentRuntimeError(Exception):
    """Base exception for AgentRuntime failures."""


class AgentRunConflict(AgentRuntimeError):
    """Raised when a session already has an active run."""


class AgentRunNotActive(AgentRuntimeError):
    """Raised when a control command requires an active run."""
