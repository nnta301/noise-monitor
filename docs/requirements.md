# Requirements

## Functional requirements

- The ESP32 continuously reads microphone signals, processes them locally, and sends numeric features only.
- Generate per-second P2P features, package them, and send them in 10-second batches.
- The backend receives, validates, stores, and queries telemetry, with deduplication.
- The dashboard is planned to display current levels, history, events, nightly reports, and no-data/stale-data status.
- Detect a threshold exceedance lasting 30 seconds; the device provides a dim LED alert.
- The system must reconnect and identify data gaps.

## Non-functional requirements

- Do not commit credentials, real Wi-Fi settings, or runtime data to Git.
- Use HTTP only in the test network; Internet access must use HTTPS.
- Each item needs appropriate test evidence before acceptance.
- Documentation must enable another team member to run the system after implementation.

## Initial scope

The target is the ESP32 → API → SQLite → dashboard data path. The simulator supports development only; hardware acceptance requires a real device. Sound-type recognition, audio recording, and raw-audio transmission are out of scope.

## Measurement limits and privacy

P2P is a relative signal metric and must not be interpreted as dB SPL without acoustic calibration. Magnitude- and duration-based filtering does not identify the sound source. Store only the necessary numeric features; do not create audio files.

## Sprint 1 acceptance criteria

- A real device sends telemetry every 10 seconds.
- The API stores data and prevents duplicates.
- The dashboard shows the latest level, a recent chart, update time, and missing-data status.
- Run an integration test for at least 30 minutes and record the results.
- Another team member can rerun the system using the documentation.
