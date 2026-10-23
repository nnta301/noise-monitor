# Producer acceptance for issues #3 and #5

Use this procedure with the hardware owner and the backend owner. Compilation,
synthetic HTTP tests, and real-device/API acceptance are separate results.
Do not mark a hardware or API criterion complete without the corresponding
observations. Do not commit device credentials, databases, raw audio, or
runtime logs. Keep local evidence in ignored `runtime-data/`; share sanitized
summaries and photos through the team's review process.

## Issue #5: verify API persistence and resends

Prerequisites: issue #4's API is running against a dedicated local test SQLite
database. The current backend stores one row per packet in `packets`. The count
query returns one integer counting **packets**, filtered by `:device_id`,
`:boot_id`, and `:sequence`. Do not count per-second feature rows.

For the current project backend, run:

```shell
.venv/bin/python scripts/verify_api_ingestion.py \
  --endpoint http://127.0.0.1:8000/api/v1/telemetry \
  --database runtime-data/test-api.sqlite \
  --count-query 'SELECT COUNT(*) FROM packets WHERE device_id=:device_id AND boot_id=:boot_id AND sequence=:sequence'
```

Replace the database path with the test API's actual SQLite path. Supply the
required backend key via `NOISE_DEVICE_KEY`, never a command argument or
committed file. Register `simulator-synthetic-acceptance` (the default device ID)
in the backend configuration, or pass a registered synthetic `--device-id`.

The tool generates a fresh boot ID, checks the database is empty for that packet
identity, uploads a contract-valid synthetic quiet packet, and resends it unchanged.
It requires HTTP 202 `accepted` followed by HTTP 202 `duplicate`, with matching
packet keys, and committed packet counts `0 -> 1 -> 1`. Each query uses a fresh
read-only SQLite connection. The API must commit before acknowledging. The tool
never creates a missing database. Running it intentionally leaves one synthetic
packet in the test API database; reset test data through the backend's procedure.

A successful run prints JSON containing `synthetic: true`, the packet key,
`outcomes: ["accepted", "duplicate"]`, and `stored_counts: [0, 1, 1]`.
Save a sanitized summary with API commit, producer commit, date, and test result.
A failure exits nonzero. An API acknowledgement alone cannot pass this check.

Then run the five scenarios documented in `scripts/README.md` against the same
API, using separate generated boot IDs. Verify their expected features in API
queries and exercise stale/offline behavior with the stopped scenario once the
dashboard is available. Do not interpret accelerated synthetic time as real time.

Automated tests exercise the checker against a temporary HTTP application and
SQLite database, including an application that falsely acknowledges duplicates
while inserting extra rows. A separate integration suite runs all five
simulator scenarios, resends, this checker, and firmware-generated payloads against the actual project FastAPI
application with a temporary SQLite database; see the commands below.

## Issue #3: hardware and API observations

Before flashing, record actual values rather than the provisional examples:

| Setting | Actual value / evidence |
| --- | --- |
| ESP32 board/module and PlatformIO environment | Pending |
| Microphone model/revision | Pending |
| Microphone supply and ADC input voltage compatibility | Pending |
| Power, ground, signal wiring and photo reference | Pending |
| ADC pin, resolution, attenuation | Pending |
| Gain position and clipping thresholds | Pending |
| Sample period and observed samples per second | Pending |
| Producer/API commits and test date | Pending |

1. Confirm that the selected firmware target matches the physical board. The
   current example requires a classic dual-core ESP32, not an ESP32-C3 or an
   arbitrary ESP32 variant. Record settings in `docs/hardware.md`. Configure
   ignored `config.local.h`, then enable `NOISE_HARDWARE_CONFIRMED` locally.
2. Build, flash, and monitor using `firmware/README.md`. Record serial diagnostics
   and the selected build environment. The `esp32dev_sampling_compile` environment
   is a sanitized CI linking check; do not flash it.
3. Keep gain, placement, and distance fixed. Observe at least 30 seconds of quiet,
   30 seconds of a repeatable sound source, and 30 seconds quiet again. Record
   source, distance, room conditions, median/peak ranges, sample counts, and
   quality flags. Confirm a repeatable relative response without claiming dB SPL.
4. Check clipping under a suitable test condition within the confirmed hardware's
   electrical limits. Confirm `clipping` indicators and document gain adjustment.
   Missing windows must be null in received JSON, never fabricated zeros.
5. With the API running, observe multiple successive batches. Confirm stable
   device identity, UUID boot identity, increasing sequences, ten per-second
   feature entries, and monotonic measurement start values 10,000 ms apart.
   Compare a packet actually received by the API with the shared schema and
   semantic rules. Record `http_status=202 acknowledged=true`; the firmware
   rejects a mismatched packet key or malformed acknowledgement.
6. Disconnect Wi-Fi for at least 30 seconds, then reconnect. Repeat with a slow
   test API. Check that sensor diagnostics continue once per second while
   networking fails or times out; document actual counts and any missing windows.
   Check that network errors remain distinct from sensor quality flags. Dropped
   packets and sequence gaps are expected; offline backfill is outside Sprint 1.
7. Record the observed results and sanitized evidence references below. A reboot
   must generate a new boot ID; its sequence starts again at zero.

| Manual criterion | Observation / evidence | Result |
| --- | --- | --- |
| Confirmed board builds and flashes | Pending | Not run |
| Repeatable quiet/source/quiet response | Pending | Not run |
| Actual gain/ADC/clipping settings | Pending | Not run |
| One-second features and ten-second batches | Pending | Not run |
| Continued sampling during network faults | Pending | Not run |
| Schema-valid packet received by real API | Pending | Not run |
| Valid HTTP 202 acknowledgement | Pending | Not run |

Sprint-wide 30-minute integration, dashboard acceptance, and later alert/LED or
backfill features remain tracked by their own issues. This procedure does not
claim that those checks have passed.

## Reproduce automated project API integration

Install producer and backend dependencies from the repository root:

```shell
.venv/bin/python -m pip install -r scripts/requirements-dev.txt -e backend
```

First run the firmware serializer commands in `firmware/README.md` to produce
`/tmp/noise-telemetry.jsonl`, then:

```shell
NOISE_FIRMWARE_TEST_PACKETS=/tmp/noise-telemetry.jsonl .venv/bin/python -m unittest discover -s scripts/integration_tests -v
```

The three integration tests start the actual FastAPI application using Uvicorn
on an ephemeral loopback port, synthetic test-only credentials, and a temporary
SQLite database. They use fake wall time for simulator scheduling, so default
and stopped-transmission deadlines are exercised without a minute-long wait.
They verify nine stored packets for the five scenarios despite identical
resends, unchanged stored payloads, counts `0 -> 1 -> 1`, authentication rejection,
conflicting-content rejection, and acceptance of the C++ firmware output.
The temporary server and database are removed after each test. The suite fails
if the firmware-output path is missing; integration is not silently skipped.
These checks do not verify physical microphone input or actual sampling cadence.
