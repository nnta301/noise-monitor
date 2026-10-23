# Sprint 1 — Core Telemetry Pipeline

**Status:** Planning

**Goal:** “Build a complete data path from the microphone and ESP32 to the database and dashboard, with a 10-second transmission interval.”

## Issues

| Issue | Title |
| --- | --- |
| [#1](https://github.com/nnta301/noise-monitor/issues/1) | Initialize the monorepo structure and development workflow |
| [#2](https://github.com/nnta301/noise-monitor/issues/2) | Define telemetry contract v1 and shared fixtures |
| [#3](https://github.com/nnta301/noise-monitor/issues/3) | Measure P2P on ESP32 and send telemetry every 10 seconds |
| [#4](https://github.com/nnta301/noise-monitor/issues/4) | Implement telemetry ingestion, storage, and query APIs |
| [#5](https://github.com/nnta301/noise-monitor/issues/5) | Build a telemetry simulator for development and testing |
| [#6](https://github.com/nnta301/noise-monitor/issues/6) | Build the live monitoring dashboard |
| [#7](https://github.com/nnta301/noise-monitor/issues/7) | Integrate and validate the end-to-end telemetry pipeline |
| [#9](https://github.com/nnta301/noise-monitor/issues/9) | Add Copilot review guidance and GitHub Actions CI |

Task details, acceptance criteria, dependencies, assignments, and progress are tracked in the linked GitHub issues.

## Sprint 1 acceptance criteria

- A real ESP32 and microphone send data every 10 seconds.
- The API stores data and prevents duplicates.
- The dashboard shows the latest level, a recent chart, and update time.
- The dashboard recognizes no-data and device-stopped-sending states.
- Run an integration test for at least 30 minutes and record its results.
- Another team member can follow the instructions to run the system again.

The simulator supports development; hardware acceptance must use a real device.

## Sprint updates

### Results

Producer implementation for #3 and #5 is available locally: fixture-based
simulator, initial ESP32 firmware, host tests, and producer CI. See
[validation notes](../validation-sprint-01.md) for remaining acceptance evidence.

### Blockers

The actual hardware must be confirmed before selecting the final board target,
flashing, and accepting #3. Real API upload and persistence evidence requires
the backend from #4; simulator and host tests do not replace this evidence.

### Scope changes

- Added [#9](https://github.com/nnta301/noise-monitor/issues/9) for
  repository-wide Copilot review guidance and baseline CI. Component-specific
  checks will be added with the corresponding implementation PRs.

### Retrospective

To be updated when the sprint ends.
