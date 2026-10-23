import contextlib
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import unittest

from scripts import simulate_telemetry as sim

BOOT = "123e4567-e89b-42d3-a456-426614174000"
START = datetime(2026, 10, 19, 22, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class SimulatorTests(unittest.TestCase):
    def test_fixture_scenarios_and_time(self):
        for scenario in sim.SCENARIOS:
            with self.subTest(scenario=scenario):
                packets = [sim.make_packet(scenario, "synthetic-test", BOOT, i, START, "UTC") for i in range(3)]
                for i, packet in enumerate(packets):
                    sim.VALIDATOR.validate(packet)
                    self.assertEqual(sim.semantic_errors(packet), [])
                    self.assertEqual(packet["sequence"], i)
                    self.assertEqual(packet["boot_id"], BOOT)
                    self.assertEqual(packet["measured_at"], f"2026-10-19T22:00:{i * 10:02d}Z")
                self.assertEqual(packets[0], sim.make_packet(scenario, "synthetic-test", BOOT, 0, START, "UTC"))
        quiet = sim.make_packet("quiet", "x", BOOT, 0, START, "UTC")
        rising = sim.make_packet("rising", "x", BOOT, 0, START, "UTC")
        peaks = sim.make_packet("peaks", "x", BOOT, 0, START, "UTC")
        missing = sim.make_packet("missing", "x", BOOT, 0, START, "UTC")
        self.assertLess(max(quiet["peak_p2p"]), 100)
        self.assertEqual(rising["median_p2p"], sorted(rising["median_p2p"]))
        self.assertEqual(peaks["quality_flags"].count("clipping"), 2)
        self.assertEqual(missing["median_p2p"][6:8], [None, None])

    def run_cli(self, options, sender=None):
        clock = Clock()
        out, err = io.StringIO(), io.StringIO()
        kwargs = {"clock": clock, "sleep": clock.sleep}
        if sender:
            kwargs["sender"] = sender
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = sim.main(["--boot-id", BOOT, "--start", "2026-10-19T22:00:00Z", *options], **kwargs)
        return result, out.getvalue(), err.getvalue(), clock.now

    def test_defaults_and_accelerated_dry_run(self):
        result, out, err, elapsed = self.run_cli(["--dry-run", "--duration", "20"])
        self.assertEqual(result, 0)
        self.assertEqual(len(out.splitlines()), 2)
        self.assertEqual(elapsed, 20)
        self.assertIn("accelerated=False", err)
        result, out, err, _ = self.run_cli(["--dry-run", "--interval", "1", "--duration", "2", "--resend"])
        packets = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(result, 0)
        self.assertEqual(packets[0], packets[1])
        self.assertEqual(packets[2]["measured_at"], "2026-10-19T22:00:10Z")
        self.assertIn("accelerated=True", err)

    def test_stopped_sends_then_waits(self):
        result, out, err, elapsed = self.run_cli(["--dry-run", "--scenario", "stopped", "--duration", "60"])
        self.assertEqual(result, 0)
        self.assertEqual(len(out.splitlines()), 1)
        self.assertEqual(elapsed, 60)
        self.assertIn("transmissions stopped", err)

    def test_resend_requires_duplicate(self):
        sent = []

        def sender(endpoint, packet, key, timeout):
            sent.append(packet)
            return "accepted" if len(sent) == 1 else "duplicate"

        result, _, err, _ = self.run_cli(["--endpoint", "http://localhost/api/v1/telemetry", "--resend", "--duration", "10"], sender)
        self.assertEqual(result, 0)
        self.assertEqual(sent[0], sent[1])
        self.assertIn("resend=duplicate", err)
        result, _, _, _ = self.run_cli(["--endpoint", "http://localhost/api/v1/telemetry", "--resend", "--duration", "10"], lambda *args: "accepted")
        self.assertEqual(result, 1)

    def test_invalid_identity_and_zone_rejected(self):
        for zone, boot, device in [("Invalid/Zone", BOOT, "x"), ("UTC", "bad", "x"), ("UTC", BOOT, "")]:
            with self.assertRaises(Exception):
                sim.make_packet("quiet", device, boot, 0, START, zone)

    def test_non_finite_interval_rejected(self):
        for value in ("nan", "inf", "0", "-1"):
            with self.assertRaises(Exception):
                sim.positive(value)

    def test_scheduler_jitter_still_sends_final_batch(self):
        clock = Clock()

        def sleep(duration):
            clock.now += duration + 0.001

        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            result = sim.main(["--dry-run", "--duration", "20"], clock=clock, sleep=sleep)
        self.assertEqual(result, 0)
        self.assertEqual(len(out.getvalue().splitlines()), 2)

    def test_invalid_config_fails_before_waiting(self):
        result, _, _, elapsed = self.run_cli(["--dry-run", "--timezone", "Invalid/Zone"])
        self.assertEqual(result, 1)
        self.assertEqual(elapsed, 0)

    def test_slow_upload_does_not_burst_catchup(self):
        clock = Clock()

        def sender(*args):
            clock.now += 25
            return "accepted"

        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = sim.main(["--endpoint", "http://localhost/api/v1/telemetry"], clock=clock, sleep=clock.sleep, sender=sender)
        self.assertEqual(result, 1)
        self.assertEqual(clock.now, 35)

    def test_http_contract_and_error_handling(self):
        records = {}
        mode = ["normal"]

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                packet = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.server.seen_key = self.headers.get("X-Device-Key")
                key = tuple(packet[k] for k in ("device_id", "boot_id", "sequence"))
                outcome = "duplicate" if key in records else "accepted"
                records[key] = packet
                status = 400 if mode[0] == "reject" else 202
                body = {"outcome": outcome, "packet_key": dict(zip(("device_id", "boot_id", "sequence"), key))}
                if mode[0] == "wrong-key":
                    body["packet_key"]["sequence"] = 999
                if mode[0] == "invalid":
                    body = {}
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/api/v1/telemetry"
        packet = sim.make_packet("quiet", "synthetic", BOOT, 0, START, "UTC")
        try:
            self.assertEqual(sim.send_packet(endpoint, packet, "test-only", 2), "accepted")
            self.assertEqual(sim.send_packet(endpoint, packet, "test-only", 2), "duplicate")
            self.assertEqual(len(records), 1)
            self.assertEqual(server.seen_key, "test-only")
            for value in ("reject", "wrong-key", "invalid"):
                mode[0] = value
                with self.assertRaises(RuntimeError):
                    sim.send_packet(endpoint, packet, "test-only", 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
