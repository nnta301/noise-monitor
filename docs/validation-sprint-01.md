# Sprint 1 producer validation

This record distinguishes host/synthetic tests from physical-device acceptance.

## Local results — 2026-10-22

Validated on macOS with Python 3.14.7 and Apple Clang:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s scripts/tests -v` | All 10 tests passed, including temporary loopback HTTP requests |
| `.venv/bin/ruff check scripts/simulate_telemetry.py scripts/tests` | Passed |
| `.venv/bin/python scripts/validate_schema.py` | All 29 shared fixtures passed their expected valid/invalid checks |
| `clang++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/include firmware/test/test_features.cpp -o /tmp/noise-features-test` then `/tmp/noise-features-test` | Passed |
| `PLATFORMIO_CORE_DIR=/tmp/noise-monitor-platformio .venv/bin/pio run -d firmware -e esp32dev_example` | Passed with pinned ESP32 platform and sanitized hardware-disabled example configuration |
| `/tmp/noise-actionlint/actionlint -shellcheck= -pyflakes=` | Passed using actionlint 1.7.12, archive SHA-256 verified against official release checksums |
| `git diff --check` | Passed |

The PlatformIO core cache and actionlint executable were kept outside the
repository. A dry run of `missing` with `--interval 0.01 --duration 0.02`,
fixed start `2026-10-19T22:00:00Z`, and fixed boot UUID emitted two valid packets
with sequences 0/1, timestamps ten measurement seconds apart, and null features
at missing slots 6/7. No physical board, real credentials, or project API was
used. CI jobs were added and validated locally; no hosted CI run is claimed.

## Issue #5

Tests cover fixed scenarios, schema and semantic constraints, identity,
sequence and ten-second timestamps, accelerated cadence, stopped transmissions,
unchanged resends, and HTTP acknowledgements/errors using a local stub.
See `scripts/README.md` for exact commands and expected output.

Actual API storage/deduplication evidence is pending issue #4. Stub acknowledgements
do not prove that the project's API persists only one record.

## Issue #3

`esp32dev_example` is a provisional compile target, not confirmed hardware.
Host tests cover median/peak aggregation, clipping, invalid readings, and
missing windows. See `firmware/README.md` for build/test/flash commands.

Pending hardware evidence:

- Confirmed board, microphone, supply, ADC pin/voltage, attenuation, gain,
  sample period, and wiring photos.
- Quiet/reference-source feature logs with actual counts and timing.
- Continued sampling during Wi-Fi loss and slow API requests.
- Real API HTTP 202 and a received packet matching telemetry v1.

Do not close #3 or claim hardware acceptance before this evidence exists.
Issue #5 also needs real API deduplication evidence. No GitHub issues were
automatically changed or closed.


## Follow-up validation — 2026-10-23

Backend baseline: `b44b3f5` from `main` (issue #4 is implemented). The following
checks were actually run on macOS with Python 3.14.7, Apple Clang, and GCC 14:

| Check | Result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s scripts/tests -v` | 13 passed, including temporary HTTP/SQLite checker tests |
| `NOISE_FIRMWARE_TEST_PACKETS=/tmp/noise-telemetry-gcc.jsonl .venv/bin/python -m unittest discover -s scripts/integration_tests -v` | 3 passed against the actual project API over loopback HTTP and temporary SQLite |
| `.venv/bin/python -m pytest backend/tests -q` | 45 passed; upstream Python 3.14 deprecation warnings |
| Ruff over simulator, new tools, unit tests, and integration tests | Passed |
| `.venv/bin/python scripts/validate_schema.py` | 29 fixtures passed |
| Host feature aggregation executable | Passed with Clang |
| Host telemetry/acknowledgement executable | Passed with Clang and GCC 14 |
| `scripts/check_firmware_contract.py` applied to C++ output | Two packets passed schema, semantic, sequence, and timing checks |
| `PLATFORMIO_CORE_DIR=/tmp/noise-monitor-platformio .venv/bin/pio run -d firmware -e esp32dev_example -e esp32dev_sampling_compile` | Both environments built and linked successfully |
| `/tmp/noise-actionlint/actionlint -shellcheck= -pyflakes=` | Passed |
| `git diff --check` | Passed |

### Issue #5 evidence

The actual project FastAPI application accepted all five fixed-fixture scenarios.
For quiet, rising, peaks, and missing scenarios, two packets were generated at
fake-clock deadlines of 10 and 20 seconds. Stopped transmissions sent one packet
at 10 seconds and waited through 60 seconds without another upload. Every packet
was resent identically: exactly nine packets were stored, with original payloads
unchanged. A dedicated verification also observed `accepted` / `duplicate` with
committed packet counts `0 -> 1 -> 1`. Wrong keys returned HTTP 401 and conflicting
content returned HTTP 409. No external API or real credentials were used.

This supersedes the earlier statement that project API deduplication evidence
was unavailable. The simulator criteria are covered by implementation,
documentation, unit tests, and project API integration. Physical hardware is not
an acceptance criterion for issue #5. Dashboard rendering and sprint-wide
30-minute device integration remain separate work.

### Issue #3 evidence and remaining checks

The same serializer used by the ESP32 generated two synthetic host packets with
all quality flags, null missing values, 64-bit timestamps/sequences, and 10,000 ms
measurement progression. Both were accepted by the actual API and duplicate
resends did not create new records. Firmware acknowledgement validation rejects
unknown outcomes, extra fields, and mismatched identity/sequence values.

Both hardware-disabled and active sampling/upload compile targets passed. The
active target used empty sanitized configuration and was not flashed. No real
ESP32/microphone observations are claimed: board confirmation, wiring photos,
measured sound response, actual sampling during network faults, and a packet
from a physical device remain pending. Follow
[producer acceptance](producer-acceptance.md) to capture those results.
