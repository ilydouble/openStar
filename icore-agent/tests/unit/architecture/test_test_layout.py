"""Architecture constraints for ownership-first Python test placement."""

from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[2]
UNIT_ROOT = TEST_ROOT / "unit"
INTEGRATION_ROOT = TEST_ROOT / "integration"
UNIT_OWNERS = frozenset({
    "architecture",
    "config",
    "contexts",
    "infrastructure",
    "interfaces",
    "shared",
})


def test_python_tests_are_nested_under_an_owner_boundary() -> None:
    """Test modules must not return to the tests or tests/unit roots."""
    assert list(TEST_ROOT.glob("test_*.py")) == []
    assert list(UNIT_ROOT.glob("test_*.py")) == []

    unexpected_unit_roots = {
        path.relative_to(UNIT_ROOT).parts[0]
        for path in UNIT_ROOT.rglob("test_*.py")
        if path.relative_to(UNIT_ROOT).parts[0] not in UNIT_OWNERS
    }
    assert unexpected_unit_roots == set()


def test_integration_tests_are_owned_by_external_interfaces() -> None:
    """Current cross-layer tests must remain under the HTTP interface owner."""
    misplaced = [
        path
        for path in INTEGRATION_ROOT.rglob("test_*.py")
        if path.relative_to(INTEGRATION_ROOT).parts[:3]
        != ("interfaces", "http", "v1")
    ]
    assert misplaced == []
