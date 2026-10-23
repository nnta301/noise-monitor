"""RFC 3339 parsing compatible with Python 3.10."""

import re
from datetime import datetime


FRACTIONAL_SECONDS = re.compile(r"\.(\d+)(?=[+-]\d{2}:\d{2}$)")


def parse_rfc3339(value: str) -> datetime:
    """Parse validated timestamps at microsecond precision without changing the payload."""
    text = value.upper().replace("Z", "+00:00")
    text = FRACTIONAL_SECONDS.sub(
        lambda match: "." + match.group(1)[:6].ljust(6, "0"), text
    )
    return datetime.fromisoformat(text)
