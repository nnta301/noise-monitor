from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class ConfigurationError(ValueError):
    """Raised when a required environment configuration is unsafe or invalid."""


@dataclass(frozen=True)
class Reader:
    reader_id: str
    key: str
    device_ids: frozenset[str]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    device_keys: dict[str, str]
    readers_by_key: dict[str, Reader]
    cors_origins: list[str]
    fresh_after_seconds: int


def _json_object(name: str, value: str | None) -> dict[str, object]:
    if not value:
        raise ConfigurationError(f"{name} must be set to a JSON object.")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"{name} is not valid JSON.") from error
    if not isinstance(parsed, dict):
        raise ConfigurationError(f"{name} must be a JSON object.")
    return parsed


def load_settings(environ: dict[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    raw_devices = _json_object("NOISE_MONITOR_DEVICE_KEYS_JSON", env.get("NOISE_MONITOR_DEVICE_KEYS_JSON"))
    device_keys: dict[str, str] = {}
    for device_id, key in raw_devices.items():
        if not isinstance(device_id, str) or not device_id or not isinstance(key, str) or not key:
            raise ConfigurationError("Device IDs and device keys must be non-empty strings.")
        if key in device_keys.values():
            raise ConfigurationError("Device keys must be unique.")
        device_keys[device_id] = key

    raw_readers = _json_object("NOISE_MONITOR_READ_KEYS_JSON", env.get("NOISE_MONITOR_READ_KEYS_JSON"))
    readers_by_key: dict[str, Reader] = {}
    for reader_id, entry in raw_readers.items():
        if not isinstance(reader_id, str) or not reader_id or not isinstance(entry, dict):
            raise ConfigurationError("Each read-key entry must have a non-empty reader ID and object value.")
        key, device_ids = entry.get("key"), entry.get("device_ids")
        if not isinstance(key, str) or not key or not isinstance(device_ids, list) or not device_ids:
            raise ConfigurationError("Read keys and device_ids must be non-empty.")
        if not all(isinstance(device_id, str) and device_id for device_id in device_ids):
            raise ConfigurationError("Read allow-list device IDs must be non-empty strings.")
        if len(device_ids) != len(set(device_ids)):
            raise ConfigurationError("Read allow-list device IDs must not contain duplicates.")
        if key in readers_by_key:
            raise ConfigurationError("Read keys must be unique to avoid ambiguous reader identities.")
        readers_by_key[key] = Reader(reader_id, key, frozenset(device_ids))

    try:
        freshness = int(env.get("NOISE_MONITOR_FRESH_AFTER_SECONDS", "30"))
    except ValueError as error:
        raise ConfigurationError("NOISE_MONITOR_FRESH_AFTER_SECONDS must be an integer.") from error
    if freshness < 0:
        raise ConfigurationError("NOISE_MONITOR_FRESH_AFTER_SECONDS must not be negative.")
    origins = [origin for origin in env.get("NOISE_MONITOR_CORS_ORIGINS", "").split(",") if origin]
    return Settings(
        database_path=Path(env.get("NOISE_MONITOR_DB_PATH", "noise-monitor.sqlite3")),
        device_keys=device_keys,
        readers_by_key=readers_by_key,
        cors_origins=origins,
        fresh_after_seconds=freshness,
    )
