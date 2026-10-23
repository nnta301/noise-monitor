from __future__ import annotations

import sqlite3
import json
from pathlib import Path

from .timestamps import timestamp_sort_key

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
    if connection.execute("PRAGMA user_version").fetchone()[0] < 2:
        try:
            connection.execute("BEGIN IMMEDIATE")
            last_rowid = 0
            while True:
                rows = connection.execute(
                    "SELECT rowid AS migration_id, payload_json FROM packets "
                    "WHERE rowid > ? AND time_sync_status != 'monotonic' "
                    "ORDER BY rowid LIMIT 128", (last_rowid,),
                ).fetchall()
                if not rows:
                    break
                for row in rows:
                    normalized = timestamp_sort_key(json.loads(row["payload_json"])["measured_at"])
                    connection.execute(
                        "UPDATE packets SET measurement_sort_value=? WHERE rowid=?",
                        (normalized, row["migration_id"]),
                    )
                last_rowid = rows[-1]["migration_id"]
            connection.execute("PRAGMA user_version = 2")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            connection.close()
            raise
    return connection
