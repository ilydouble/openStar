from __future__ import annotations

import os

# Use an in-memory SQLite database for account integration tests unless overridden.
os.environ.setdefault("ICORE_TEST_SYNC_DATABASE_URL", "sqlite+pysqlite:///:memory:")

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
