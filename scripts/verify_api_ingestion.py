"""Verify synthetic API acceptance and duplicate persistence in a local SQLite DB."""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
from urllib.parse import urlsplit
from uuid import uuid4

try:
    from .simulate_telemetry import make_packet, positive, send_packet
except ImportError:
    from simulate_telemetry import make_packet, positive, send_packet


def stored_count(database, query, packet):
    # A fresh connection for each observation sees the API's committed state.
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute(query, {k: packet[k] for k in (
            "device_id", "boot_id", "sequence"
        )}).fetchall()
    if len(rows) != 1 or len(rows[0]) != 1 or type(rows[0][0]) is not int or rows[0][0] < 0:
        raise RuntimeError("Count query must return one non-negative integer")
    return rows[0][0]


def verify(endpoint, database, query, packet, key="", timeout=5, sender=send_packet):
    # Bind all three identity fields; the backend owner supplies its actual SQL.
    for name in ("device_id", "boot_id", "sequence"):
        if f":{name}" not in query:
            raise RuntimeError("Count query must bind device_id, boot_id, and sequence")
    counts = [stored_count(database, query, packet)]
    if counts != [0]:
        raise RuntimeError("Use a fresh boot ID: packet already exists before upload")
    if sender(endpoint, packet, key, timeout) != "accepted":
        raise RuntimeError("First upload must be acknowledged as accepted")
    counts.append(stored_count(database, query, packet))
    if counts[-1] != 1:
        raise RuntimeError("First upload did not persist exactly one packet")
    if sender(endpoint, packet, key, timeout) != "duplicate":
        raise RuntimeError("Identical resend must be acknowledged as duplicate")
    counts.append(stored_count(database, query, packet))
    if counts[-1] != 1:
        raise RuntimeError("Identical resend changed the stored packet count")
    return {"synthetic": True, "scenario": "quiet", "packet_key": {
        k: packet[k] for k in ("device_id", "boot_id", "sequence")
    }, "outcomes": ["accepted", "duplicate"], "stored_counts": counts}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.getenv("NOISE_TELEMETRY_ENDPOINT"))
    parser.add_argument("--database", required=True, help="existing SQLite database used by the test API")
    parser.add_argument("--count-query", required=True, help="backend-specific SELECT COUNT(*) with named identity parameters")
    parser.add_argument("--device-id", default="simulator-synthetic-acceptance")
    parser.add_argument("--timeout", type=positive, default=5)
    args = parser.parse_args(argv)
    endpoint = urlsplit(args.endpoint or "")
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
        parser.error("set an HTTP(S) endpoint without embedded credentials or fragment")
    packet = make_packet("quiet", args.device_id, str(uuid4()), 0,
                         datetime.now(timezone.utc), "UTC")
    try:
        result = verify(args.endpoint, args.database, args.count_query, packet,
                        os.getenv("NOISE_DEVICE_KEY", ""), args.timeout)
    except Exception:
        # SQL/transport exceptions can contain local paths, URLs, and credentials.
        print("SYNTHETIC verification failed; check API acknowledgement, committed storage, and count query", file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
