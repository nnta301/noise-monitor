from __future__ import annotations

import sqlite3
from pathlib import Path


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
    return connection
