"""Real project API over loopback HTTP with temporary SQLite, never physical hardware."""

import contextlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from noise_monitor.app import create_app
from noise_monitor.config import Settings
import uvicorn

from scripts import simulate_telemetry as sim
from scripts.tests.test_simulator import Clock
from scripts.verify_api_ingestion import verify

COUNT_QUERY = "SELECT COUNT(*) FROM packets WHERE device_id=:device_id AND boot_id=:boot_id AND sequence=:sequence"
DEVICE = "synthetic-integration"
KEY = "synthetic-test-only"


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = Path(self.temp.name) / "api.sqlite"
        self.device_keys = {DEVICE: KEY, "synthetic-firmware-contract-test": KEY}
        settings = Settings(self.database, self.device_keys, {}, [], 30)
        self.app = create_app(settings)
        self.socket = socket.socket()
        self.socket.bind(("127.0.0.1", 0))
        self.addCleanup(self.socket.close)
        self.endpoint = f"http://127.0.0.1:{self.socket.getsockname()[1]}/api/v1/telemetry"
        self.server = uvicorn.Server(uvicorn.Config(
            self.app, log_level="error", access_log=False, lifespan="on",
        ))
        self.thread = threading.Thread(target=self.server.run,
                                       kwargs={"sockets": [self.socket]}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        deadline = time.monotonic() + 5
        while not self.server.started and self.thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(self.server.started, "Temporary project API failed to start")

    def stop_server(self):
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.assertFalse(self.thread.is_alive(), "Temporary API did not stop")

    def test_all_scenarios_and_resends_persist_expected_packets(self):
        expected = []
        with patch.dict(os.environ, {"NOISE_DEVICE_KEY": KEY}):
            for index, scenario in enumerate(sim.SCENARIOS):
                clock = Clock()
                boot = f"123e4567-e89b-42d3-a456-{index:012d}"
                options = ["--endpoint", self.endpoint, "--device-id", DEVICE,
                           "--boot-id", boot, "--start", "2026-10-19T22:00:00Z",
                           "--scenario", scenario, "--resend", "--duration", "20"]
                if scenario == "stopped":
                    options += ["--duration", "60"]
                with contextlib.redirect_stderr(io.StringIO()):
                    result = sim.main(options, clock=clock, sleep=clock.sleep)
                self.assertEqual(result, 0, scenario)
                count = 1 if scenario == "stopped" else 2
                expected.extend(sim.make_packet(scenario, DEVICE, boot, seq,
                                               datetime(2026, 10, 19, 22, tzinfo=timezone.utc),
                                               "Asia/Ho_Chi_Minh") for seq in range(count))
        with contextlib.closing(sqlite3.connect(self.database)) as db:
            rows = db.execute("SELECT payload_json FROM packets ORDER BY boot_id, sequence").fetchall()
        self.assertEqual([json.loads(row[0]) for row in rows], expected)
        self.assertEqual(len(rows), 9)  # Resends did not create another nine records.

    def test_api_verifier_checks_actual_committed_database(self):
        packet = sim.make_packet("quiet", DEVICE, "123e4567-e89b-42d3-a456-426614174000",
                                 0, datetime(2026, 10, 19, tzinfo=timezone.utc), "UTC")
        result = verify(self.endpoint, self.database, COUNT_QUERY, packet, KEY)
        self.assertEqual(result["stored_counts"], [0, 1, 1])
        with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
            sim.send_packet(self.endpoint, {**packet, "sequence": 1}, "wrong-test-key", 2)
        changed = {**packet, "peak_p2p": [4095] * 10}
        with self.assertRaisesRegex(RuntimeError, "HTTP 409"):
            sim.send_packet(self.endpoint, changed, KEY, 2)

    def test_firmware_packets_are_accepted_by_actual_api(self):
        # The documented command and CI must supply the host C++ serializer output.
        path = os.environ["NOISE_FIRMWARE_TEST_PACKETS"]
        packets = [json.loads(line) for line in Path(path).read_text().splitlines()]
        self.assertEqual(len(packets), 2)
        for packet in packets:
            self.assertEqual(sim.send_packet(self.endpoint, packet, KEY, 2), "accepted")
            self.assertEqual(sim.send_packet(self.endpoint, packet, KEY, 2), "duplicate")
        with contextlib.closing(sqlite3.connect(self.database)) as db:
            stored = [json.loads(row[0]) for row in db.execute(
                "SELECT payload_json FROM packets ORDER BY sequence")]
        self.assertEqual(stored, packets)
