"""OS-released exclusive executor ownership, including after a process crash."""

import os
from .db import DomainError


class ProcessLock:
    def __init__(self, path):
        self.path, self.handle = path, None

    def acquire(self):
        self.handle = open(self.path, "a+b")
        self.handle.seek(0, 2)
        if not self.handle.tell():
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            self.handle.close()
            self.handle = None
            raise DomainError(
                "Another executor owns this data directory. Run exactly one ZeroWall server.",
                503,
            )

    def release(self):
        if self.handle:
            self.handle.close()
            self.handle = None
