from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ObjectSummary:
    name: str
    time_modified: datetime
    size: int = 100


def ts(hour, minute=0):
    return datetime(2026, 10, 1, hour, minute, tzinfo=timezone.utc)
