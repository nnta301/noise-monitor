import json
import os
import sys
from jsonschema import validate, ValidationError

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '../shared/schemas/telemetry_v1.json')
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '../shared/fixtures')

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

    for filename in sorted(os.listdir(FIXTURES_DIR)):
        if not filename.endswith('.json'):
            continue

        filepath = os.path.join(FIXTURES_DIR, filename)
        fixture_data = load_json(filepath)

        try:
            validate(instance=fixture_data, schema=schema)
            if filename == "invalid_payload.json":
                print(f"[FAIL] {filename} (Expected validation to fail, but it passed)")
                all_passed = False
            else:
                print(f"[PASS] {filename}")
        except ValidationError as e:
            if filename == "invalid_payload.json":

                print(f"[PASS] {filename} (Caught expected error: {e.message})")
            else:
                print(f"[FAIL] {filename} - {e.message}")
                all_passed = False

    if all_passed:
        print("Validation completed successfully.")
        sys.exit(0)
    else:
        print("Validation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()