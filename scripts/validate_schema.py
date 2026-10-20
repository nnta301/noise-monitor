import json
import os
import sys
from jsonschema import validate, ValidationError, FormatChecker

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '../shared/schemas/telemetry_v1.json')
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../shared/fixtures')

REQUIRED_FIXTURES = {
    "quiet_baseline.json", "rising_levels.json", "brief_peaks.json", "missing_samples.json",
    "invalid_length.json", "invalid_flag.json", "invalid_format.json"
}

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    print("Validating fixtures against schema...")

    try:
        schema = load_json(SCHEMA_PATH)
    except FileNotFoundError:
        print(f"Error: Schema not found at {SCHEMA_PATH}")
        sys.exit(1)

    all_passed = True
    found_fixtures = set()

    for filename in sorted(os.listdir(FIXTURES_DIR)):
        if not filename.endswith('.json'):
            continue

        found_fixtures.add(filename)
        filepath = os.path.join(FIXTURES_DIR, filename)
        fixture_data = load_json(filepath)

        try:
            # Thêm format_checker để bắt lỗi ngày giờ
            validate(instance=fixture_data, schema=schema, format_checker=FormatChecker())

            if filename.startswith("invalid_"):
                print(f"[FAIL] {filename} (Expected validation to fail, but it passed)")
                all_passed = False
            else:
                print(f"[PASS] {filename}")
        except ValidationError as e:
            if filename.startswith("invalid_"):
                print(f"[PASS] {filename} (Caught expected error: {e.message})")
            else:
                print(f"[FAIL] {filename} - {e.message}")
                all_passed = False

    # Kiểm tra xem có bị thiếu file nào không
    missing = REQUIRED_FIXTURES - found_fixtures
    if missing:
        print(f"[FAIL] Missing required fixtures: {missing}")
        all_passed = False

    if all_passed:
        print("Validation completed successfully.")
        sys.exit(0)
    else:
        print("Validation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()