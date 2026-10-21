# Shared

This directory is for resources shared across components, such as approved telemetry fixtures or data-format documentation. Do not place secrets, runtime data, or audio recordings here.

`schemas/telemetry_v1.json` is the authoritative telemetry schema. The JSON
fixtures are synthetic contract examples; validate them with
`python scripts/validate_schema.py` after installing `jsonschema[format]==4.26.0`
and `tzdata==2026.5`.
