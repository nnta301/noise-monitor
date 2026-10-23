"""Validate JSON Lines emitted by the host firmware contract executable."""

import json
import sys

try:
    from .simulate_telemetry import VALIDATOR, semantic_errors
except ImportError:
    from simulate_telemetry import VALIDATOR, semantic_errors


def check(stream):
    packets = [json.loads(line) for line in stream if line.strip()]
    if len(packets) != 2:
        raise ValueError("Expected two firmware-generated test packets")
    for packet in packets:
        VALIDATOR.validate(packet)
        if semantic_errors(packet):
            raise ValueError("Firmware packet violates telemetry semantics")
        if packet["quality_flags"] != ["ok", "clipping", "out_of_range", "missing"] + ["ok"] * 6:
            raise ValueError("Unexpected firmware quality flags")
        if packet["median_p2p"][3] is not None or packet["peak_p2p"][3] is not None:
            raise ValueError("Missing features must be null")
    if packets[1]["sequence"] != packets[0]["sequence"] + 1:
        raise ValueError("Firmware sequence did not increment")
    if packets[1]["measured_at"] != packets[0]["measured_at"] + 10000:
        raise ValueError("Firmware measurement timestamps are not ten seconds apart")
    print("Two firmware-generated packets passed schema, semantics, and timing checks")


if __name__ == "__main__":
    check(sys.stdin)
