import json
import sys
from pathlib import Path
import tzdata
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, reset_tzpath

from jsonschema import Draft7Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "shared" / "schemas" / "telemetry_v1.json"
FIXTURES_DIR = ROOT / "shared" / "fixtures"
reset_tzpath(())
VALID_FIXTURES = {"brief_peaks.json", "missing_samples.json", "monotonic_samples.json", "quiet_baseline.json", "rising_levels.json", "utc_timezone.json"}
INVALID_FIXTURES = {
    "invalid_flag.json": ("schema", "quality_flags/5"),
    "invalid_boot_id.json": ("schema", "boot_id"),
    "invalid_format.json": ("schema", "measured_at"),
    "invalid_length_flags.json": ("schema", "quality_flags"),
    "invalid_length_median.json": ("schema", "median_p2p"),
    "invalid_length_peak.json": ("schema", "peak_p2p"),
    "invalid_missing_numeric.json": ("semantic", "missing_requires_null"),
    "invalid_missing_zero.json": ("semantic", "missing_requires_null"),
    "invalid_monotonic_timestamp.json": ("schema", "measured_at"),
    "invalid_null_without_missing.json": ("semantic", "null_requires_missing"),
    "invalid_synced_non_utc.json": ("schema", "measured_at"),
    "invalid_timezone.json": ("semantic", "iana_timezone"),
}


def load_json(path):
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def semantic_errors(packet):
    errors = []
    try:
        ZoneInfo(packet["timezone"])
    except (KeyError, TypeError, ZoneInfoNotFoundError):
        errors.append(("timezone", "iana_timezone"))
    for index, (median, peak, flag) in enumerate(zip(packet.get("median_p2p", []), packet.get("peak_p2p", []), packet.get("quality_flags", []))):
        missing_values = median is None and peak is None
        if flag == "missing" and not missing_values:
            errors.append((f"sample/{index}", "missing_requires_null"))
        elif flag != "missing" and (median is None or peak is None):
            errors.append((f"sample/{index}", "null_requires_missing"))
    return errors


def schema_error_paths(validator, packet):
    return {"/".join(str(part) for part in error.absolute_path) for error in validator.iter_errors(packet)}


def main():
    print("Validating telemetry contract fixtures...")
    try:
        schema = load_json(SCHEMA_PATH)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"[FAIL] Cannot load schema: {error}")
        return 1
    if not FIXTURES_DIR.is_dir():
        print(f"[FAIL] Fixtures directory not found: {FIXTURES_DIR}")
        return 1
    fixture_names = {path.name for path in FIXTURES_DIR.glob("*.json")}
    missing = (VALID_FIXTURES | set(INVALID_FIXTURES)) - fixture_names
    if missing:
        print(f"[FAIL] Missing required fixtures: {', '.join(sorted(missing))}")
        return 1

    validator = Draft7Validator(schema, format_checker=FormatChecker())
    all_passed = True
    for filename in sorted(fixture_names):
        try:
            packet = load_json(FIXTURES_DIR / filename)
        except json.JSONDecodeError as error:
            print(f"[FAIL] {filename}: invalid JSON: {error}")
            all_passed = False
            continue
        schema_paths = schema_error_paths(validator, packet)
        semantics = semantic_errors(packet) if not schema_paths else []
        if filename in VALID_FIXTURES:
            passed = not schema_paths and not semantics
        elif filename in INVALID_FIXTURES:
            kind, expected = INVALID_FIXTURES[filename]
            actual = schema_paths if kind == "schema" else {code for _, code in semantics}
            passed = expected in actual
        else:
            print(f"[FAIL] {filename}: fixture is not classified as valid or invalid")
            all_passed = False
            continue
        if passed:
            print(f"[PASS] {filename}")
        else:
            print(f"[FAIL] {filename}: schema={sorted(schema_paths)}, semantic={semantics}")
            all_passed = False
    print("Validation completed successfully." if all_passed else "Validation failed.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
