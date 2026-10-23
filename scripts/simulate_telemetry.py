"""Send explicitly synthetic, fixture-based contract-v1 telemetry."""

import argparse
import copy
from datetime import datetime, timedelta, timezone
import json
import math
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID, uuid4

from jsonschema import Draft7Validator, FormatChecker

try:
    from .validate_schema import FIXTURES_DIR, SCHEMA_PATH, load_json, semantic_errors
except ImportError:
    from validate_schema import FIXTURES_DIR, SCHEMA_PATH, load_json, semantic_errors

SCENARIOS = {
    "quiet": "quiet_baseline.json",
    "rising": "rising_levels.json",
    "peaks": "brief_peaks.json",
    "missing": "missing_samples.json",
    "stopped": "quiet_baseline.json",
}
VALIDATOR = Draft7Validator(load_json(SCHEMA_PATH), format_checker=FormatChecker())


def make_packet(scenario, device_id, boot_id, sequence, start, zone):
    packet = copy.deepcopy(load_json(FIXTURES_DIR / SCENARIOS[scenario]))
    packet.update(
        device_id=device_id, boot_id=str(UUID(boot_id)), sequence=sequence,
        measured_at=(start + timedelta(seconds=10 * sequence)).astimezone(
            timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        timezone=zone, time_sync_status="synced",
    )
    VALIDATOR.validate(packet)
    if semantic_errors(packet):
        raise ValueError("Packet failed telemetry semantic validation")
    return packet


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not forward a device key to a redirected endpoint.


def send_packet(endpoint, packet, key, timeout):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Device-Key"] = key
    request = Request(endpoint, data=json.dumps(packet).encode(), headers=headers, method="POST")
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            status = response.status
            body = json.loads(response.read(16384))
    except HTTPError as error:
        status = error.code
        error.close()
        raise RuntimeError(f"API rejected packet: HTTP {status}") from None
    except (URLError, OSError, ValueError):
        raise RuntimeError("Network failure or invalid API response") from None
    if status != 202:
        raise RuntimeError(f"Expected HTTP 202; received {status}")
    schema = load_json(SCHEMA_PATH.parent / "telemetry_response_202.json")
    if not Draft7Validator(schema).is_valid(body):
        raise RuntimeError("API response does not match the 202 contract")
    expected = {name: packet[name] for name in ("device_id", "boot_id", "sequence")}
    if body["packet_key"] != expected:
        raise RuntimeError("API response has a different packet key")
    return body["outcome"]


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return number


def utc_start(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError
        return result.astimezone(timezone.utc)
    except ValueError:
        raise argparse.ArgumentTypeError("must be an ISO timestamp with a timezone") from None


def main(argv=None, *, clock=time.monotonic, sleep=time.sleep, sender=send_packet):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="quiet")
    parser.add_argument("--endpoint", default=os.getenv("NOISE_TELEMETRY_ENDPOINT"))
    parser.add_argument("--device-id", default="simulator-synthetic-01")
    parser.add_argument("--boot-id", default=str(uuid4()))
    parser.add_argument("--timezone", default="Asia/Ho_Chi_Minh")
    parser.add_argument("--interval", type=positive, default=10, help="wall seconds per synthetic 10s batch")
    parser.add_argument("--duration", type=positive, default=60, help="wall seconds, including stopped time")
    parser.add_argument("--stop-after", type=positive, default=20, help="stop sending after these wall seconds")
    parser.add_argument("--timeout", type=positive, default=5)
    parser.add_argument("--start", type=utc_start)
    parser.add_argument("--resend", action="store_true", help="resend each packet unchanged; require duplicate outcome")
    parser.add_argument("--dry-run", action="store_true", help="write JSON Lines without HTTP")
    args = parser.parse_args(argv)
    if not args.dry_run:
        endpoint = urlsplit(args.endpoint or "")
        if endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
            parser.error("set --endpoint to an HTTP(S) URL without embedded credentials or fragment")
    if args.scenario == "stopped" and args.stop_after >= args.duration:
        parser.error("--stop-after must be less than --duration for stopped transmissions")
    print(f"SYNTHETIC scenario={args.scenario} interval={args.interval:g}s "
          f"accelerated={args.interval != 10}; each batch represents 10 measurement seconds", file=sys.stderr)
    begin = clock()
    # A live packet is emitted only once its measurement window has elapsed.
    start = args.start or datetime.now(timezone.utc)
    sequence = 0
    try:
        # Fail on invalid identity/timezone before waiting for the first send.
        make_packet(args.scenario, args.device_id, args.boot_id, 0, start, args.timezone)
        while True:
            due = begin + (sequence + 1) * args.interval
            if due > begin + args.duration:
                sleep(max(0, begin + args.duration - clock()))
                break
            sleep(max(0, due - clock()))
            if args.scenario == "stopped" and due >= begin + args.stop_after:
                print("SYNTHETIC transmissions stopped; waiting to exercise stale/offline state", file=sys.stderr)
                sleep(max(0, begin + args.duration - clock()))
                break
            packet = make_packet(args.scenario, args.device_id, args.boot_id, sequence, start, args.timezone)
            if args.dry_run:
                print(json.dumps(packet), flush=True)
                if args.resend:
                    print(json.dumps(packet), flush=True)
            else:
                outcome = sender(args.endpoint, packet, os.getenv("NOISE_DEVICE_KEY", ""), args.timeout)
                print(f"SYNTHETIC sequence={sequence} outcome={outcome}", file=sys.stderr)
                if args.resend:
                    outcome = sender(args.endpoint, packet, os.getenv("NOISE_DEVICE_KEY", ""), args.timeout)
                    if outcome != "duplicate":
                        raise RuntimeError("Identical resend was not acknowledged as duplicate")
                    print(f"SYNTHETIC sequence={sequence} resend=duplicate", file=sys.stderr)
            sequence += 1
            # Never burst old packets to catch up after a slow HTTP request.
            if clock() > due + args.interval:
                raise RuntimeError("Upload exceeded the next send deadline; increase interval or reduce timeout")
    except Exception as error:
        # Never render exception text containing URLs, keys, or request headers.
        message = str(error) if isinstance(error, RuntimeError) else "Invalid configuration or packet"
        print(f"SYNTHETIC error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
