from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from scripts.simulate_telemetry import make_packet
from scripts.verify_api_ingestion import stored_count, verify


class ApiVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "test.sqlite"
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("CREATE TABLE packets (device_id TEXT, boot_id TEXT, sequence INTEGER)")
        self.query = "SELECT COUNT(*) FROM packets WHERE device_id=:device_id AND boot_id=:boot_id AND sequence=:sequence"
        self.packet = make_packet("quiet", "synthetic-test", "123e4567-e89b-42d3-a456-426614174000",
                                  0, datetime(2026, 10, 19, tzinfo=timezone.utc), "UTC")

    def test_http_with_temporary_sqlite_persistence(self):
        database = self.database
        query = self.query
        duplicate_bug = [False]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                packet = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                exists = stored_count(database, query, packet) > 0
                if not exists or duplicate_bug[0]:
                    with closing(sqlite3.connect(database)) as connection, connection:
                        connection.execute("INSERT INTO packets VALUES (?, ?, ?)",
                                           tuple(packet[k] for k in ("device_id", "boot_id", "sequence")))
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"outcome": "duplicate" if exists else "accepted",
                                             "packet_key": {k: packet[k] for k in (
                                                 "device_id", "boot_id", "sequence")}}).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/api/v1/telemetry"
        try:
            result = verify(endpoint, self.database, self.query, self.packet)
            self.assertEqual(result["stored_counts"], [0, 1, 1])
            # Detect a lying API: duplicate acknowledgement, but duplicate row stored.
            self.packet["sequence"] = 1
            duplicate_bug[0] = True
            with self.assertRaisesRegex(RuntimeError, "changed the stored"):
                verify(endpoint, self.database, self.query, self.packet)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_missing_persistence_and_existing_packet_fail(self):
        with self.assertRaisesRegex(RuntimeError, "persist exactly one"):
            verify("unused", self.database, self.query, self.packet,
                   sender=lambda *args: "accepted")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("INSERT INTO packets VALUES (?, ?, ?)",
                               tuple(self.packet[k] for k in ("device_id", "boot_id", "sequence")))
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            verify("unused", self.database, self.query, self.packet,
                   sender=lambda *args: self.fail("Must not upload existing identity"))

    def test_read_only_query_and_missing_database(self):
        with self.assertRaises(sqlite3.OperationalError):
            stored_count(self.database, "DELETE FROM packets", self.packet)
        missing = Path(self.temp.name) / "missing.sqlite"
        with self.assertRaises(sqlite3.OperationalError):
            stored_count(missing, self.query, self.packet)
        self.assertFalse(missing.exists())
        with self.assertRaisesRegex(RuntimeError, "must bind"):
            verify("unused", self.database, "SELECT COUNT(*) FROM packets", self.packet)
        with self.assertRaisesRegex(RuntimeError, "one non-negative integer"):
            stored_count(self.database, "SELECT 'invalid'", self.packet)


if __name__ == "__main__":
    unittest.main()
