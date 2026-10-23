from __future__ import annotations

import sqlite3
from datetime import timezone
from pathlib import Path

from .timestamps import parse_rfc3339

SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
  device_id TEXT NOT NULL,
  boot_id TEXT NOT NULL,
  sequence INTEGER NOT NULL,
  time_sync_status TEXT NOT NULL,
  measured_at_json TEXT NOT NULL,
  measurement_sort_value TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  received_at TEXT NOT NULL,
  PRIMARY KEY (device_id, boot_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_packets_device_time
  ON packets (device_id, time_sync_status, measurement_sort_value DESC, boot_id ASC, sequence DESC);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    # Upgrade legacy variable-width timestamp keys atomically, preserving payloads.
    if connection.execute("PRAGMA user_version").fetchone()[0] < 1:
        try:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT device_id, boot_id, sequence, measurement_sort_value FROM packets "
                "WHERE time_sync_status != 'monotonic'"
            ).fetchall()
            for row in rows:
                value = parse_rfc3339(row["measurement_sort_value"])
                normalized = value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
                connection.execute(
                    "UPDATE packets SET measurement_sort_value=? "
                    "WHERE device_id=? AND boot_id=? AND sequence=?",
                    (normalized, row["device_id"], row["boot_id"], row["sequence"]),
                )
            connection.execute("PRAGMA user_version = 1")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            connection.close()
            raise
    return connection
