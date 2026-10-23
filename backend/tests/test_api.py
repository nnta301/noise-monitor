from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noise_monitor.app import create_app
from noise_monitor.config import Settings, load_settings


ROOT = Path(__file__).resolve().parents[2]


def packet(name: str = "quiet_baseline.json") -> dict:
    return json.loads((ROOT / "shared" / "fixtures" / name).read_text())


def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_path=tmp_path / "telemetry.sqlite3",
        device_keys={"esp32-bedroom-01": "device-a", "device-b": "device-b"},
        readers_by_key=load_settings({
            "NOISE_MONITOR_DEVICE_KEYS_JSON": '{"esp32-bedroom-01":"device-a"}',
            "NOISE_MONITOR_READ_KEYS_JSON": '{"reader-a":{"key":"read-a","device_ids":["esp32-bedroom-01"]},"reader-b":{"key":"read-b","device_ids":["device-b"]}}',
        }).readers_by_key,
        cors_origins=[],
        fresh_after_seconds=30,
    )
    return TestClient(create_app(settings))


def post(api: TestClient, payload: dict, key: str = "device-a"):
    return api.post("/api/v1/telemetry", json=payload, headers={"X-Device-Key": key})


@pytest.mark.parametrize(
    ("fixture_name", "status"),
    [
        ("brief_peaks.json", 202),
        ("missing_samples.json", 202),
        ("monotonic_samples.json", 202),
        ("quiet_baseline.json", 202),
        ("rising_levels.json", 202),
        ("utc_timezone.json", 202),
        ("invalid_missing_zero.json", 400),
        ("invalid_median_exceeds_peak.json", 400),
        ("invalid_timezone.json", 400),
    ],
)
def test_shared_request_fixtures(tmp_path: Path, fixture_name: str, status: int):
    with client(tmp_path) as api:
        assert post(api, packet(fixture_name)).status_code == status


def test_accepts_fixture_and_handles_idempotency(tmp_path: Path):
    with client(tmp_path) as api:
        body = packet()
        assert post(api, body).json()["outcome"] == "accepted"
        assert post(api, body).json()["outcome"] == "duplicate"
        changed = {**body, "median_p2p": [44, *body["median_p2p"][1:]]}
        response = post(api, changed)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "idempotency_conflict"


def test_rejects_auth_malformed_and_invalid_payloads(tmp_path: Path):
    with client(tmp_path) as api:
        body = packet()
        assert api.post("/api/v1/telemetry", json=body).status_code == 401
        assert post(api, {**body, "device_id": "device-b"}, "device-a").status_code == 401
        assert api.post("/api/v1/telemetry", content=b"{").status_code == 400
        bad = packet("invalid_missing_zero.json")
        response = post(api, bad)
        assert response.status_code == 400
        assert response.json()["error"]["fields"][0]["code"] == "missing_requires_null"


def test_database_persists_across_app_restart(tmp_path: Path):
    with client(tmp_path) as api:
        assert post(api, packet()).status_code == 202
    with client(tmp_path) as api:
        response = api.get("/api/v1/devices/esp32-bedroom-01/latest", headers={"X-Read-Key": "read-a"})
        assert response.status_code == 200
        assert response.json()["packet"]["sequence"] == 1


def test_read_permissions_and_history_pagination(tmp_path: Path):
    with client(tmp_path) as api:
        first, second = packet(), packet("missing_samples.json")
        second["sequence"] = 2
        second["measured_at"] = "2026-10-19T22:00:30Z"
        assert post(api, first).status_code == 202
        assert post(api, second).status_code == 202
        delayed = {**first, "sequence": 3}
        assert post(api, delayed).status_code == 202
        denied = api.get("/api/v1/devices/esp32-bedroom-01/history", headers={"X-Read-Key": "read-b"})
        assert denied.status_code == 403
        latest = api.get("/api/v1/devices/esp32-bedroom-01/latest", headers={"X-Read-Key": "read-a"})
        assert latest.json()["packet"]["sequence"] == 2
        page = api.get("/api/v1/devices/esp32-bedroom-01/history?page_size=1", headers={"X-Read-Key": "read-a"}).json()
        assert [item["packet"]["sequence"] for item in page["items"]] == [2]
        followup = api.get("/api/v1/devices/esp32-bedroom-01/history?page_size=1&cursor=" + page["next_cursor"], headers={"X-Read-Key": "read-a"}).json()
        assert [item["packet"]["sequence"] for item in followup["items"]] == [3]
        final_page = api.get("/api/v1/devices/esp32-bedroom-01/history?page_size=1&cursor=" + followup["next_cursor"], headers={"X-Read-Key": "read-a"}).json()
        assert [item["packet"]["sequence"] for item in final_page["items"]] == [1]


def test_unsynced_and_monotonic_never_claim_freshness(tmp_path: Path):
    with client(tmp_path) as api:
        sample = packet("monotonic_samples.json")
        assert post(api, sample).status_code == 202
        response = api.get("/api/v1/devices/esp32-bedroom-01/latest?time_sync_status=monotonic&boot_id=123e4567-e89b-12d3-a456-426614174000", headers={"X-Read-Key": "read-a"})
        assert response.json()["freshness"] == {"status": "unknown"}
        assert api.get("/api/v1/devices/esp32-bedroom-01/history?time_sync_status=monotonic", headers={"X-Read-Key": "read-a"}).status_code == 400


def test_rejects_ambiguous_read_key_configuration():
    try:
        load_settings({
            "NOISE_MONITOR_DEVICE_KEYS_JSON": '{"device-a":"key-a"}',
            "NOISE_MONITOR_READ_KEYS_JSON": '{"reader-a":{"key":"same","device_ids":["device-a"]},"reader-b":{"key":"same","device_ids":["device-a"]}}',
        })
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("Expected ambiguous reader keys to be rejected")


@pytest.mark.parametrize("value", ["bnVsbA", "MQ", "e30", "W10"])
def test_invalid_cursor_returns_client_error(tmp_path, value):
    with client(tmp_path) as api:
        response = api.get(
            "/api/v1/devices/esp32-bedroom-01/history",
            params={"cursor": value}, headers={"X-Read-Key": "read-a"},
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "invalid_page_cursor"


@pytest.mark.parametrize("value", ["2026-10-19", "2026-10-19T22:00:00"])
def test_naive_range_rejected(tmp_path, value):
    with client(tmp_path) as api:
        for field in ("from_at", "to_at"):
            response = api.get(
                "/api/v1/devices/esp32-bedroom-01/history",
                params={field: value}, headers={"X-Read-Key": "read-a"},
            )
            assert response.status_code == 400


def test_invalid_encoding_and_stream_size_limit(tmp_path):
    with client(tmp_path) as api:
        assert api.post("/api/v1/telemetry", content=b'"\xff"').status_code == 400
        for headers in ({}, {"Content-Length": "1"}):
            response = api.post(
                "/api/v1/telemetry", content=iter([b" " * 40000, b" " * 40000]),
                headers=headers,
            )
            assert response.status_code == 413
            assert response.json()["error"]["code"] == "payload_too_large"


def test_future_synced_measurement_has_unknown_freshness(tmp_path):
    with client(tmp_path) as api:
        assert post(api, {**packet(), "measured_at": "2099-01-01T00:00:00Z"}).status_code == 202
        response = api.get("/api/v1/devices/esp32-bedroom-01/latest", headers={"X-Read-Key": "read-a"})
        assert response.json()["freshness"] == {"status": "unknown"}


def test_fractional_order_ranges_pagination_and_legacy_migration(tmp_path):
    with client(tmp_path) as api:
        for sequence, measured_at in enumerate([
            "2026-10-19T22:00:00Z", "2026-10-19T22:00:00.500000Z"
        ]):
            assert post(api, {**packet(), "sequence": sequence, "measured_at": measured_at}).status_code == 202
    db = sqlite3.connect(tmp_path / "telemetry.sqlite3")
    db.execute("UPDATE packets SET measurement_sort_value='2026-10-19T22:00:00Z' WHERE sequence=0")
    db.execute("PRAGMA user_version=0")
    db.commit()
    db.close()
    with client(tmp_path) as api:
        url = "/api/v1/devices/esp32-bedroom-01/"
        headers = {"X-Read-Key": "read-a"}
        assert api.get(url + "latest", headers=headers).json()["packet"]["sequence"] == 1
        page = api.get(url + "history", params={"page_size": 1}, headers=headers).json()
        assert page["items"][0]["packet"]["sequence"] == 1
        second = api.get(url + "history", params={"cursor": page["next_cursor"]}, headers=headers).json()
        assert second["items"][0]["packet"]["sequence"] == 0
        bounded = api.get(url + "history", params={"to_at": "2026-10-19T22:00:00Z"}, headers=headers).json()
        assert [item["packet"]["sequence"] for item in bounded["items"]] == [0]
