# Noise Monitor repository instructions

Noise Monitor is a three-person Applied IoT project. The planned stack is
ESP32 with Arduino/PlatformIO, FastAPI with SQLite, and React with TypeScript.

## Sources and scope

- Read the relevant requirements, architecture, hardware, telemetry contract,
  workflow, and sprint documents before judging project-specific behavior.
- Treat draft contracts and TODO items as unresolved. Do not invent field
  names, thresholds, hardware settings, or reliability policies.
- Review changes against their stated scope. Do not require future-sprint
  features in a PR that does not implement them.
- Repository-facing content and review comments must be written in English.

## Privacy and measurement

- Microphone samples are processed locally for numeric feature extraction.
  Never persist or transmit raw audio, waveforms, or recordings.
- P2P is a relative signal measurement, not calibrated dB SPL. Do not infer
  sound types or actual sleep quality from amplitude.
- Do not expose credentials, real Wi-Fi configuration, device keys, or
  runtime databases in tracked files or logs.

## Telemetry and component boundaries

- Check that changed producers and consumers follow the same approved
  telemetry contract. Identify incompatible changes across firmware,
  simulator, backend, shared fixtures, and dashboard.
- Preserve measurement time separately from server receipt time. Do not
  silently replace missing measurements with zero or unsynchronized times
  with receipt timestamps.
- When ingestion changes, check validation, packet identity, duplicate and
  conflicting-payload handling, and database persistence against the contract.
- Keep microphone sampling and feature calculation independent of network
  upload. Distinguish sampling frequency, feature windows, and batch intervals.
- When retries or buffering change, check timeouts, retry termination, and
  bounded memory. Do not require deferred offline-backfill features.
- Keep device credentials out of browser bundles. Check loading, error,
  stale-data, and missing-data states when dashboard behavior changes.

## Review quality and validation

- Report actionable issues supported by the changed code and relevant
  context. Identify the affected location, explain the impact, and suggest
  a concrete correction.
- Prioritize correctness, security, contract compatibility, and regressions.
  Avoid speculative findings, unrelated refactors, and cosmetic feedback
  already covered by automated checks.
- Check meaningful failure cases and documentation updates. Distinguish
  synthetic tests, compilation, and physical-hardware verification.
- When a component is introduced, check that its PR adds appropriate CI
  commands and reproducible local instructions. Do not accept placeholder
  success steps or silently ignored failures.
- Do not claim tests or hardware checks passed without evidence.
  AI review supplements, but does not replace, another team member's review.