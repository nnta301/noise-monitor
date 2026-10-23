from __future__ import annotations

import base64
import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.resources import files
from typing import Any

from fastapi import FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jsonschema import Draft7Validator, FormatChecker
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Reader, Settings, load_settings
from .storage import connect

MAX_BODY_BYTES = 64 * 1024


def error(status: int, code: str, message: str, **extra: Any) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, **extra}})


def pointer(parts: list[Any]) -> str:
    return "/" + "/".join(str(part).replace("~", "~0").replace("/", "~1") for part in parts)


def validate_packet(packet: object, validator: Draft7Validator) -> list[dict[str, str]]:
    fields = [
        {"path": pointer(list(issue.absolute_path)), "code": "schema_validation", "message": issue.message}
        for issue in sorted(validator.iter_errors(packet), key=lambda issue: list(issue.absolute_path))
    ]
    if fields or not isinstance(packet, dict):
        return fields
    try:
        ZoneInfo(packet["timezone"])
    except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError):
        fields.append({"path": "/timezone", "code": "iana_timezone", "message": "Timezone must be an installed IANA name."})
    for index, (median, peak, flag) in enumerate(zip(packet["median_p2p"], packet["peak_p2p"], packet["quality_flags"])):
        if flag == "missing" and (median is not None or peak is not None):
            fields.append({"path": f"/quality_flags/{index}", "code": "missing_requires_null", "message": "A missing sample must use null median and peak values."})
        elif flag != "missing" and (median is None or peak is None):
            fields.append({"path": f"/quality_flags/{index}", "code": "null_requires_missing", "message": "Null values require the missing quality flag."})
        elif median is not None and peak is not None and median > peak:
            fields.append({"path": f"/median_p2p/{index}", "code": "median_exceeds_peak", "message": "Median P2P must not exceed peak P2P."})
    return fields


def sort_value(packet: dict[str, Any]) -> str:
    value = packet["measured_at"]
    if packet["time_sync_status"] == "monotonic":
        return f"{value:020d}"
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def packet_key(packet: dict[str, Any]) -> dict[str, Any]:
    return {name: packet[name] for name in ("device_id", "boot_id", "sequence")}


def encode_cursor(row: sqlite3.Row) -> str:
    raw = json.dumps([row["measurement_sort_value"], row["boot_id"], row["sequence"]], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> tuple[str, str, int] | None:
    if cursor is None:
        return None
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        value, boot_id, sequence = json.loads(raw)
        if not isinstance(value, str) or not isinstance(boot_id, str) or not isinstance(sequence, int):
            raise ValueError
        return value, boot_id, sequence
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid page cursor.") from error


def row_response(row: sqlite3.Row, fresh_after_seconds: int) -> dict[str, Any]:
    packet = json.loads(row["payload_json"])
    freshness: dict[str, Any] = {"status": "unknown"}
    if packet["time_sync_status"] == "synced":
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(packet["measured_at"].replace("Z", "+00:00"))).total_seconds()
        if age >= 0:
            freshness = {"status": "fresh" if age <= fresh_after_seconds else "stale", "age_seconds": int(age)}
    return {"packet": packet, "measurement_time": packet["measured_at"], "received_at": row["received_at"], "freshness": freshness}


def create_app(settings: Settings | None = None) -> FastAPI:
    actual_settings = settings or load_settings()
    schema = json.loads(files("noise_monitor_contract").joinpath("schemas/telemetry_v1.json").read_text(encoding="utf-8"))
    validator = Draft7Validator(schema, format_checker=FormatChecker())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.db = connect(actual_settings.database_path)
        yield
        app.state.db.close()

    app = FastAPI(title="Noise Monitor API", lifespan=lifespan)
    if actual_settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=actual_settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["X-Device-Key", "X-Read-Key", "Content-Type"])

    def authorize_device(packet: dict[str, Any], key: str | None) -> JSONResponse | None:
        if not key or packet["device_id"] not in actual_settings.device_keys or actual_settings.device_keys[packet["device_id"]] != key:
            return error(401, "device_authentication_failed", "A valid device key is required.")
        return None

    def authorize_reader(device_id: str, key: str | None) -> tuple[Reader | None, JSONResponse | None]:
        if not key or key not in actual_settings.readers_by_key:
            return None, error(401, "read_authentication_failed", "A valid read key is required.")
        reader = actual_settings.readers_by_key[key]
        if device_id not in reader.device_ids:
            return None, error(403, "device_access_denied", "This reader is not allowed to access the device.")
        return reader, None

    @app.post("/api/v1/telemetry")
    async def ingest(request: Request, x_device_key: str | None = Header(default=None)):
        try:
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_BODY_BYTES:
                    return error(413, "payload_too_large", "Telemetry body exceeds 65536 bytes.")
                body.extend(chunk)
            packet = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return error(400, "validation_error", "Telemetry payload validation failed.", fields=[{"path": "", "code": "malformed_json", "message": "Request body must be valid JSON."}])
        fields = validate_packet(packet, validator)
        if fields:
            return error(400, "validation_error", "Telemetry payload validation failed.", fields=fields)
        assert isinstance(packet, dict)
        unauthorized = authorize_device(packet, x_device_key)
        if unauthorized:
            return unauthorized
        canonical = json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        db: sqlite3.Connection = request.app.state.db
        try:
            db.execute("INSERT INTO packets VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (*packet_key(packet).values(), packet["time_sync_status"], json.dumps(packet["measured_at"]), sort_value(packet), canonical, received_at))
            return JSONResponse(status_code=202, content={"outcome": "accepted", "packet_key": packet_key(packet)})
        except sqlite3.IntegrityError:
            row = db.execute("SELECT payload_json FROM packets WHERE device_id=? AND boot_id=? AND sequence=?", tuple(packet_key(packet).values())).fetchone()
            if row and row["payload_json"] == canonical:
                return JSONResponse(status_code=202, content={"outcome": "duplicate", "packet_key": packet_key(packet)})
            return error(409, "idempotency_conflict", "A different payload already exists for this packet key.", packet_key=packet_key(packet))

    def validate_read_mode(status: str, boot_id: str | None, from_at: str | None, to_at: str | None) -> JSONResponse | None:
        if status == "monotonic" and not boot_id:
            return error(400, "boot_id_required", "boot_id is required for monotonic measurements.")
        try:
            if status == "monotonic":
                if any(value is not None and int(value) < 0 for value in (from_at, to_at)):
                    raise ValueError
            else:
                for value in (from_at, to_at):
                    if value is not None:
                        if not FormatChecker().conforms(value, "date-time"):
                            raise ValueError
                        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        if parsed.utcoffset() is None:
                            raise ValueError
        except ValueError:
            return error(400, "invalid_time_range", "Use non-negative milliseconds for monotonic data and RFC 3339 otherwise.")
        return None

    @app.get("/api/v1/devices/{device_id}/latest")
    async def latest(device_id: str, request: Request, x_read_key: str | None = Header(default=None), time_sync_status: str = Query(default="synced"), boot_id: str | None = Query(default=None)):
        _, denied = authorize_reader(device_id, x_read_key)
        if denied:
            return denied
        invalid = validate_read_mode(time_sync_status, boot_id, None, None)
        if invalid:
            return invalid
        if time_sync_status not in {"synced", "unsynced", "monotonic"}:
            return error(400, "invalid_time_sync_status", "time_sync_status must be synced, unsynced, or monotonic.")
        clauses, values = ["device_id=?", "time_sync_status=?"], [device_id, time_sync_status]
        if boot_id:
            clauses.append("boot_id=?")
            values.append(boot_id)
        row = request.app.state.db.execute(f"SELECT * FROM packets WHERE {' AND '.join(clauses)} ORDER BY measurement_sort_value DESC, boot_id ASC, sequence DESC LIMIT 1", values).fetchone()
        return JSONResponse(status_code=404, content={"error": {"code": "measurement_not_found", "message": "No matching measurement exists."}}) if row is None else row_response(row, actual_settings.fresh_after_seconds)

    @app.get("/api/v1/devices/{device_id}/history")
    async def history(device_id: str, request: Request, x_read_key: str | None = Header(default=None), time_sync_status: str = Query(default="synced"), boot_id: str | None = Query(default=None), from_at: str | None = Query(default=None), to_at: str | None = Query(default=None), page_size: int = Query(default=50, ge=1, le=100), cursor: str | None = Query(default=None)):
        _, denied = authorize_reader(device_id, x_read_key)
        if denied:
            return denied
        if time_sync_status not in {"synced", "unsynced", "monotonic"}:
            return error(400, "invalid_time_sync_status", "time_sync_status must be synced, unsynced, or monotonic.")
        invalid = validate_read_mode(time_sync_status, boot_id, from_at, to_at)
        if invalid:
            return invalid
        try:
            decoded = decode_cursor(cursor)
        except ValueError:
            return error(400, "invalid_page_cursor", "The page cursor is invalid.")
        clauses, values = ["device_id=?", "time_sync_status=?"], [device_id, time_sync_status]
        if boot_id:
            clauses.append("boot_id=?")
            values.append(boot_id)
        for operator, value in ((">=", from_at), ("<=", to_at)):
            if value is not None:
                normalized = f"{int(value):020d}" if time_sync_status == "monotonic" else sort_value({"time_sync_status": time_sync_status, "measured_at": value})
                clauses.append(f"measurement_sort_value {operator} ?")
                values.append(normalized)
        if decoded:
            clauses.append("(measurement_sort_value < ? OR (measurement_sort_value = ? AND (boot_id > ? OR (boot_id = ? AND sequence < ?))))")
            values.extend([decoded[0], decoded[0], decoded[1], decoded[1], decoded[2]])
        rows = request.app.state.db.execute(f"SELECT * FROM packets WHERE {' AND '.join(clauses)} ORDER BY measurement_sort_value DESC, boot_id ASC, sequence DESC LIMIT ?", [*values, page_size + 1]).fetchall()
        has_more = len(rows) > page_size
        rows = rows[:page_size]
        return {"items": [row_response(row, actual_settings.fresh_after_seconds) for row in rows], "next_cursor": encode_cursor(rows[-1]) if has_more and rows else None}

    return app
