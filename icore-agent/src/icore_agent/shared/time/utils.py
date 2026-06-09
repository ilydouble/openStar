from datetime import datetime, UTC

def start_to_completed_duration_ms(started_at: datetime, completed_at: datetime) -> int:
    """Return elapsed milliseconds between two timestamps."""
    return max(int((completed_at - started_at).total_seconds() * 1000), 0)

def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)