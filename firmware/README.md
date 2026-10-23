# Firmware

Arduino/PlatformIO firmware extracts relative ADC P2P features locally and
uploads contract-v1 batches to the local test API. No raw audio is retained or
transmitted. The actual board, microphone, wiring, gain, and supply remain
**unconfirmed**. `esp32dev_example` is a provisional compilation target for a
classic dual-core ESP32. Confirm the hardware before flashing; other variants
may need a different environment, ADC settings, and task/core placement.

## Build and configure

Run from the repository root:

```shell
python3 -m venv .venv
.venv/bin/python -m pip install -r scripts/requirements-dev.txt
.venv/bin/pio run -d firmware -e esp32dev_example
cp firmware/include/config.example.h firmware/include/config.local.h
```

Edit the ignored local header for Wi-Fi, endpoint, optional device key,
timezone, ADC pin, clipping limits, and sample period. Only enable
`NOISE_HARDWARE_CONFIRMED` after recording the actual hardware. Without it,
the example compiles but does not sample. Dependencies are pinned in
`platformio.ini`. The optional key uses `X-Device-Key`; confirm this with the
API owner because authentication is not specified by contract v1.

For a confirmed compatible board, build, flash, and monitor (replace the port):

```shell
.venv/bin/pio run -d firmware -e esp32dev_example
.venv/bin/pio run -d firmware -e esp32dev_example -t upload --upload-port /dev/cu.usbserial-EXAMPLE
.venv/bin/pio device monitor -b 115200 --port /dev/cu.usbserial-EXAMPLE
```

## Features and diagnostics

- Example: 12-bit ADC1 GPIO34, `ADC_11db`, target period 2000 microseconds
  (500 Hz), best effort under RTOS scheduling. Record actual sample counts,
  microphone gain, and supply during hardware validation.
- Each 50 ms window keeps min/max only. Twenty window P2Ps form a second:
  median is the integer floor of the mean of the middle two; peak is the max.
- Every second logs counts of samples, invalid readings, clipped readings,
  valid windows, median, peak, and quality flag. ADC rails 0/4095 count as
  clipping by default. Invalid readings take precedence over clipping.
  Any empty window makes the second `missing`, with both features `null`.
  An unplugged analog microphone may still yield plausible values; software
  alone cannot reliably diagnose this wiring fault.
- Every ten seconds a batch receives a sequence (starting at zero), random
  UUIDv4 boot identity, and Wi-Fi MAC device identity. `measured_at` is batch-start
  milliseconds from the 64-bit ESP timer with `time_sync_status=monotonic`.
  No server receipt time or fabricated UTC replaces measurement time.
- Upload runs on a separate task/core with 2-second connect/read timeouts.
  A two-packet queue bounds memory. Offline packets, new arrivals to a full queue,
  and failed requests are dropped with diagnostics. Sequences expose gaps.
  No automatic retries, durable backfill, alert rule, or LED are implemented.
- `sensor` messages describe feature quality; `network` messages report HTTP
  status or transport loss. Application logs exclude endpoints, keys, and Wi-Fi
  credentials. Only local test HTTP is implemented; Internet deployment needs
  HTTPS with certificate verification. Redirects are disabled.

## Tests and acceptance

```shell
c++ -std=c++17 -Wall -Wextra -Werror -Ifirmware/include firmware/test/test_features.cpp -o /tmp/noise-features-test
/tmp/noise-features-test
```

CI runs host feature tests and compiles sanitized example configuration without
hardware. Real acceptance of #3 still requires confirmed hardware settings,
quiet/reference-source feature logs, sampling during network failures, a real
API HTTP 202, and the received packet validated against the shared contract.
Record evidence in [validation notes](../docs/validation-sprint-01.md).
