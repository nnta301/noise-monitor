"""RFC 3339 parsing compatible with Python 3.10."""

import re
from datetime import datetime, timezone


FRACTIONAL_SECONDS = re.compile(r"\.(\d+)(?=[+-]\d{2}:\d{2}$)")


def parse_rfc3339(value: str) -> datetime:
    """Parse validated timestamps at microsecond precision without changing the payload."""
    text = value.upper().replace("Z", "+00:00")
    text = FRACTIONAL_SECONDS.sub(
        lambda match: "." + match.group(1)[:6].ljust(6, "0"), text
    )
    return datetime.fromisoformat(text)


def timestamp_sort_key(value: str) -> str:
    """Preserve arbitrary fractional precision in lexicographic UTC ordering."""
    text = value.upper().replace("Z", "+00:00")
    match = FRACTIONAL_SECONDS.search(text)
    fraction = match.group(1).rstrip("0") if match else ""
    whole_second = FRACTIONAL_SECONDS.sub("", text)
    utc = datetime.fromisoformat(whole_second).astimezone(timezone.utc)
    # '/' sorts before digits, so an exact second or fraction prefix sorts first.
    return utc.isoformat(timespec="seconds").replace("+00:00", "") + "." + fraction + "/"
