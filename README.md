# Noise Monitor

Noise Monitor is an IoT project for monitoring noise in a sleep environment. The system measures signals using an ESP32 and microphone, processes them locally, and sends numeric features to a server; it does not record or transmit raw audio.

**Status:** the Sprint 1 software is implemented: the shared telemetry contract,
ESP32 firmware (compiles; sampling stays disabled until the hardware is
confirmed), a synthetic telemetry simulator, an authenticated FastAPI/SQLite
backend, and a React dashboard. The end-to-end flow has been validated with
synthetic data only. Hardware purchase and real-device validation (#3, #7) are
pending.

## Goals

- Continuously read signals and send telemetry every 10 seconds.
- Track the current level, history, events, and nightly reports.
- Detect levels exceeding a threshold for 30 seconds and provide a dim LED alert on the device.
- Support reconnection and handling of data gaps.

Peak-to-Peak (P2P) is a relative signal metric, **not dB SPL** without acoustic calibration. Filtering by magnitude and duration also does not identify sound types.

## Technologies

- Firmware: C++, Arduino framework, PlatformIO.
- Hardware: ESP32 and a MAX4466 microphone (not yet purchased; the exact board and microphone models must be confirmed).
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

Current sprint: **Sprint 1 — Core Telemetry Pipeline** (software complete; hardware validation pending).

## Running locally

Start the components in this order:

1. **Backend:** follow [backend/README.md](backend/README.md) to install the package, set the device and read keys, and start the API with `uvicorn`.
2. **Simulator (instead of a real device):** follow [scripts/README.md](scripts/README.md). Register the simulator's device ID and key in the backend configuration.
3. **Dashboard:** a React + TypeScript application.

   ```shell
   cd dashboard
   npm ci
   npm run dev
   ```

   Set these Vite variables before `npm run dev`:
   - `VITE_API_BASE_URL`: API base URL. Default: `http://localhost:8000`.
   - `VITE_DEVICE_ID`: device ID to query. Default: `esp32-sleep-monitor-01`; use the simulator's device ID when running with the simulator.
   - `VITE_READ_KEY`: read key sent as `X-Read-Key`. It is embedded in the browser bundle, so use a development-only key.