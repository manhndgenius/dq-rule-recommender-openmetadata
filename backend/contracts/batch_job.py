"""Status primitives shared by server-side batch jobs."""

from datetime import datetime, timezone
from enum import Enum


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class JobItemStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


TERMINAL_ITEM_STATUSES = {
    JobItemStatus.SUCCESS,
    JobItemStatus.PARTIAL,
    JobItemStatus.FAILED,
    JobItemStatus.SKIPPED,
}
