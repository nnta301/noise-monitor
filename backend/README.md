# Backend API

The FastAPI backend accepts numeric telemetry features only. It never stores raw audio, waveforms, recordings, or secrets.

## Setup and configuration

Use Python 3.10 or later from the repository root:

```shell
python -m venv .venv
# POSIX shells:
. .venv/bin/activate
# Windows PowerShell (use instead of the POSIX command):
.venv\Scripts\Activate.ps1
python -m pip install -e "backend[dev]"
```

Set sanitized local values; do not commit runtime databases or real secrets:

```shell
NOISE_MONITOR_DB_PATH=./noise-monitor.sqlite3
NOISE_MONITOR_DEVICE_KEYS_JSON={"esp32-bedroom-01":"replace-device-key"}
NOISE_MONITOR_READ_KEYS_JSON={"dashboard-dev":{"key":"replace-read-key","device_ids":["esp32-bedroom-01"]}}
NOISE_MONITOR_CORS_ORIGINS=http://localhost:5173
NOISE_MONITOR_FRESH_AFTER_SECONDS=30
```

Device keys map a device ID to a non-empty unique key. Read keys map each reader identity to an object with a non-empty unique `key` and explicit, non-empty `device_ids`. Wildcards are not supported. Invalid, empty, duplicate, or ambiguous keys prevent startup.

```shell
uvicorn noise_monitor.app:create_app --factory --app-dir backend --reload
```

Development CORS is opt-in and does not authorize callers. The dashboard must not receive a read key in a browser bundle. A later proxy/login component must authenticate its human caller and enforce device authorization; merely hiding a read key is insufficient.

## API permissions and examples

`POST /api/v1/telemetry` requires `X-Device-Key`. It must match the configured key for the payload's `device_id`; missing, unknown, or cross-device keys return `401`/`device_authentication_failed`.

`GET /api/v1/devices/{device_id}/latest` and `/history` require `X-Read-Key`. Missing or unknown keys return `401`/`read_authentication_failed`; a known reader outside the device allow-list gets `403`/`device_access_denied`.

```shell
curl -X POST http://127.0.0.1:8000/api/v1/telemetry -H "Content-Type: application/json" -H "X-Device-Key: replace-device-key" --data @shared/fixtures/quiet_baseline.json
curl http://127.0.0.1:8000/api/v1/devices/esp32-bedroom-01/latest -H "X-Read-Key: replace-read-key"
```

A new packet returns `202`/`accepted`; an identical retry is `202`/`duplicate`; a changed payload with the same packet key is `409`/`idempotency_conflict`. Malformed and invalid bodies use the shared `400` validation envelope rather than FastAPI's default `422`.

Telemetry bodies are limited to 65,536 bytes, including streamed bodies without a
Content-Length header. Larger requests receive `413`/`payload_too_large`.
Future synced measurement timestamps have freshness `unknown`.
Timestamp range parameters require full RFC 3339 date-times with explicit offsets.
SQLite startup migrates legacy timestamp sort keys to fixed microsecond precision
in a transaction; packet contents and receipt times are preserved.
The wheel includes the authoritative schemas directly from `shared/`, so regular
installations do not need the repository tree at runtime.

## Query semantics and storage

`latest` and `history` default to `time_sync_status=synced`; they never substitute receipt time for measurement time. Responses include both `measurement_time` and `received_at`. Only synced data has calculated `fresh`/`stale` status; unsynced and monotonic data are `unknown`.

History accepts `time_sync_status`, optional `from_at`/`to_at`, `page_size` (1–100; default 50), and opaque `cursor`. It sorts descending by selected measurement-time representation, then `boot_id` ascending and `sequence` descending. Use `next_cursor` with unchanged filters. Synced/unsynced ranges use RFC 3339; unsynced timestamps remain device-reported. Monotonic ranges use integer milliseconds and require `boot_id`, so boots are never compared on one time axis.

SQLite `packets` has primary key `(device_id, boot_id, sequence)` and index `idx_packets_device_time` on device, time status, measurement sort value, boot ID, and sequence. It retains canonical packet JSON (features and metadata) and a separate receipt time only.

## Validation

```shell
python -m ruff check backend
python -m pytest backend/tests
python scripts/validate_schema.py
git diff --check
```

`backend/postman/noise-monitor-api.postman_collection.json` is a synthetic Postman collection. Set keys only in a local Postman environment, never in the collection or browser bundle.

## Follow-up work outside issue #4

Docker Compose, TLS deployment, system load testing, and seven-day operational validation are whole-project follow-up work. They are not implemented or claimed as accepted here. Dashboard user authentication and the proxy that enforces caller and device permissions are likewise a dashboard/integration dependency, not an end-to-end security claim for this backend issue.
