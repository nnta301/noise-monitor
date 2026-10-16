# Telemetry contract (draft)

This document is intended to align discussion; it is not yet a JSON Schema or validator.

## Identity and time

- `device_id`: a stable device identifier; the assignment method is **TODO**.
- `boot_id`: a unique identifier for one boot instance.
- `sequence`: an increasing packet sequence number within `boot_id`.
- `measured_at`: the measurement-batch start time in ISO 8601 format.
- `timezone`: an IANA time zone or agreed offset; **TODO: select a standard**.
- `time_sync_status`: for example, `synced`, `unsynced`, or `estimated`; the final value set is **TODO**.

## Batch contents

Each packet represents a planned 10-second window. `p2p_samples` contains one relative P2P value per second, not dB SPL. `valid_samples` is the number of valid samples; `missing_samples` describes missing positions/reasons when applicable. `saturated_samples` records saturated samples when firmware can detect them.

```json
{
  "device_id": "demo-esp32-01",
  "boot_id": "demo-boot-a1",
  "sequence": 42,
  "measured_at": "2026-01-01T22:00:00+07:00",
  "timezone": "Asia/Bangkok",
  "time_sync_status": "synced",
  "p2p_samples": [120, 132, 118, 125, 140, 121, 130, 128, 119, 124],
  "valid_samples": 10,
  "missing_samples": [],
  "saturated_samples": []
}
```

The example above is **mock data**, not a real measurement.

## Planned rules

- The planned deduplication key is `device_id` + `boot_id` + `sequence`.
- The server must process retransmissions idempotently and record/display data gaps.
- Receipt order does not replace measurement order; the client and server must retain measurement time.
- Numeric types, the P2P range, batch-size limits, missing/saturation representations, and the strategy for an unsynchronized clock are all **TODO: confirm**.
