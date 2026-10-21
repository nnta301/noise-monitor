# Scripts

This directory is for development support tools, such as a telemetry simulator or sample-data checks. Every script must document its use and inputs/outputs, and must not contain credentials.

## Validate the telemetry contract

Install the pinned schema and IANA timezone-data dependencies, then run this command from the repository root:

```shell
python -m pip install "jsonschema[format]==4.26.0" "tzdata==2026.5"
python scripts/validate_schema.py
```

The check validates the authoritative schema, all required valid fixtures, and
the expected schema or semantic failure for each required invalid fixture.
