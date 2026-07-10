"""Tests for shared public identifier generation."""

from icore_agent.contexts.files.domain.uuid import uuid7
from icore_agent.shared.identifiers import uuid7 as shared_uuid7


def test_uuid7_returns_parseable_time_ordered_values() -> None:
    """UUIDv7 generation should be parseable and roughly time ordered."""
    first = uuid7()
    second = uuid7()

    assert first.version == 7
    assert second.version == 7
    assert first.int < second.int


def test_file_uuid7_uses_shared_domain_identifier() -> None:
    """The file-domain UUID helper should preserve the shared UUIDv7 export."""
    assert uuid7 is shared_uuid7
