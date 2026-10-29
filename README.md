# Noise Monitor

Noise Monitor is an IoT project for monitoring noise in a sleep environment. The planned system measures signals using an ESP32 and microphone, processes them locally, and sends numeric features to a server; it does not record or transmit raw audio.

**Status:** shared contracts, a synthetic telemetry simulator, and initial ESP32
firmware are implemented. Hardware confirmation and real device/API validation
are pending; backend and dashboard implementations remain planned.

## Planned goals

- Continuously read signals and send telemetry every 10 seconds.
- Track the current level, history, events, and nightly reports.
- Detect levels exceeding a threshold for 30 seconds and provide a dim LED alert on the device.
- Support reconnection and handling of data gaps.

Peak-to-Peak (P2P) is a relative signal metric, **not dB SPL** without acoustic calibration. Filtering by magnitude and duration also does not identify sound types.

## Planned technologies

- Firmware: C++, Arduino framework, PlatformIO.
- Hardware: ESP32 and a MAX4466 microphone (the actual components must be confirmed).
- Data transport: an HTTP API in the test network; HTTPS when accessed over the Internet.
- Backend: FastAPI, SQLite.
- Dashboard: React, TypeScript.

## Structure

```text
firmware/   device firmware
backend/    API and storage
dashboard/  monitoring interface
shared/     shared contracts and resources
scripts/    development support tools
docs/       requirements, architecture, hardware, workflow, and sprints
```

## Documentation

- [Requirements](docs/requirements.md), [architecture](docs/architecture.md), [hardware](docs/hardware.md), and [workflow](docs/workflow.md)
- [Telemetry contract](docs/contracts/telemetry.md)
- [Roadmap](docs/sprints/README.md) and [Sprint 1](docs/sprints/sprint-01.md)

Current sprint: **Sprint 1 — Planning**.

## Dashboard Setup
The frontend is a React + TypeScript application. To run it locally:
1. `cd dashboard`
2. `npm install`
3. `npm run dev`

The dashboard uses these optional Vite variables. Set them before `npm run dev`:
- `VITE_API_BASE_URL`: API base URL. Default: `http://localhost:8000`.
- `VITE_DEVICE_ID`: device ID to query. Default: `esp32-sleep-monitor-01`.
3. `npm run dev`