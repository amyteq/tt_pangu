from __future__ import annotations

from enum import Enum


class SideEffect(str, Enum):
    READ_ONLY = "READ_ONLY"
    LOCAL_WRITE = "LOCAL_WRITE"
    REMOTE_WRITE = "REMOTE_WRITE"
    SUBMISSION = "SUBMISSION"


EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_BLOCKED = 2
