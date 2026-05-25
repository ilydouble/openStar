from __future__ import annotations

import ast
import re
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]


def test_gateway_and_backend_public_route_policies_do_not_drift():
    """Compare Go gateway public route policy with Python AuthMiddleware fallback policy."""
    go_policy = (
        AGENT_ROOT
        / "src"
        / "icore_agent"
        / "services"
        / "gateway"
        / "internal"
        / "application"
        / "route_policy"
        / "route_policy.go"
    ).read_text(encoding="utf-8")
    python_policy = (
        AGENT_ROOT
        / "src"
        / "icore_agent"
        / "shared"
        / "http"
        / "middleware"
        / "auth_middleware.py"
    ).read_text(encoding="utf-8")

    assert _go_string_slice(go_policy, "PublicExactPaths") == _python_literal_set(
        python_policy, "_PUBLIC_PATHS"
    )
    assert _go_string_slice(go_policy, "PublicPathPrefixes") == _python_literal_set(
        python_policy, "_PUBLIC_PREFIXES"
    )


def _go_string_slice(source: str, name: str) -> set[str]:
    pattern = rf"var\s+{name}\s*=\s*\[\]string\s*\{{(?P<body>.*?)\}}"
    match = re.search(pattern, source, flags=re.DOTALL)
    assert match is not None, f"missing Go policy slice {name}"
    return set(re.findall(r'"([^"]+)"', match.group("body")))


def _python_literal_set(source: str, name: str) -> set[str]:
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return set(ast.literal_eval(node.value))
    raise AssertionError(f"missing Python policy literal {name}")
