# Scripts

This directory is for development support tools, such as a telemetry simulator or sample-data checks. Every script must document its use and inputs/outputs, and must not contain credentials.

## Validate the telemetry contract

Install the pinned schema and IANA timezone-data dependencies, then run this command from the repository root:

```shell
python -m pip install "jsonschema[format]==4.26.0" "tzdata==2026.5"
python scripts/validate_schema.py
```

The check validates the authoritative schema, all required valid fixtures, and
the expected schema or semantic failure for each required invalid fixture.

## Synthetic telemetry simulator

Install and preview from the repository root:

```shell
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-dev.txt
.venv/bin/python scripts/simulate_telemetry.py --dry-run --scenario quiet --interval 1 --duration 3 --start 2026-10-19T22:00:00Z --boot-id 123e4567-e89b-42d3-a456-426614174000
```

Expect three validated JSON Lines packets, sequences 0–2, with measurement
start times 22:00:00Z, 22:00:10Z, and 22:00:20Z. Logs on stderr say `SYNTHETIC`
and identify accelerated mode. Payloads retain the contract without extra
metadata. The default device ID is `simulator-synthetic-01`; keep synthetic
device identities separate from real devices.

Send to the API once issue #4 supplies it:

```shell
.venv/bin/python scripts/simulate_telemetry.py --endpoint http://127.0.0.1:8000/api/v1/telemetry --scenario quiet --duration 60
```

Defaults send one batch every ten wall seconds, first at ten seconds. Duration
is wall time, including stopped time; completed batches with deadlines through
that duration are sent. `--interval` explicitly changes wall cadence only;
each packet always represents ten measurement seconds. Live measurement time
starts at launch in UTC; accelerated runs advance synthetic time faster than
wall time. `--start` and `--boot-id` make tests repeatable; reusing boot IDs
against persisted records may cause conflicts. Features repeat fixed shared
fixtures, so no random seed is needed. Endpoint, device ID, timezone, duration,
interval, start time, and request timeout are configurable.

| Scenario | Option | Expected characteristics |
| --- | --- | --- |
| Quiet | `--scenario quiet` | Steady small values; all flags `ok` |
| Rising | `--scenario rising` | Increasing values within each batch; repeats each batch |
| Peaks | `--scenario peaks` | Two high peaks with `clipping` flags |
| Missing | `--scenario missing` | Slots 6 and 7 contain null features and `missing` flags |
| Stopped | `--scenario stopped --stop-after 20 --duration 120` | One batch at 10s, then no sends from 20s through 120s for stale/offline UI testing |

Use the endpoint command with any scenario above. Successful logs include
`SYNTHETIC sequence=0 outcome=accepted`. HTTP rejection, malformed response,
network failure, or a response packet key mismatch causes exit 1. Requests
require HTTP 202 acknowledgements conforming to the response contract.

For local credentials, copy `scripts/simulator.env.example` to `.env` (ignored),
edit locally, and export using your shell (`set -a; source .env; set +a`).
`NOISE_TELEMETRY_ENDPOINT` supplies the endpoint; `NOISE_DEVICE_KEY` supplies
the optional `X-Device-Key` header. Confirm that header with the API owner;
authentication is not defined in contract v1. Use HTTP only on the test network
and HTTPS with normal certificate verification over the Internet. Credentials
are not logged, and redirects are refused.

Append `--resend` to send each packet twice unchanged. The second HTTP 202 must
say `outcome=duplicate` or the tool fails. For real backend acceptance, also
show that the storage record count does not grow using issue #4's API/database.
Dry-run resends only print identical JSON twice; they do not verify storage.

Run tests and lint:

```shell
.venv/bin/python -m unittest discover -s scripts/tests -v
.venv/bin/ruff check scripts/simulate_telemetry.py scripts/tests
.venv/bin/python scripts/validate_schema.py
```

Tests use fixed fixtures, a fake clock, and a temporary loopback HTTP stub.
They require no external service, hardware, or real credentials. The stub
verifies transport behavior; real backend persistence evidence is still pending.
No audio is played or recorded.
