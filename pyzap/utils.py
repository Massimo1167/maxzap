from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import os
import time

try:
    from filelock import FileLock  # type: ignore
except Exception:  # pragma: no cover - fallback if dependency missing
    class FileLock:  # type: ignore
        def __init__(self, path: str, timeout: float = 10):
            self.path = path
            self.timeout = timeout
            self.fd: int | None = None

        def acquire(self, timeout: float | None = None) -> None:
            end = time.monotonic() + (timeout or self.timeout)
            while True:
                try:
                    self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    break
                except FileExistsError:
                    if time.monotonic() > end:
                        raise TimeoutError()
                    time.sleep(0.05)

        def release(self) -> None:
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
                try:
                    os.unlink(self.path)
                except OSError:
                    pass

        def __enter__(self) -> "FileLock":
            self.acquire(self.timeout)
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            self.release()


@contextmanager
def excel_lock(path: str, timeout: int = 10) -> Iterator[None]:
    """Acquire a lock for exclusive access to an Excel file."""
    lock = FileLock(f"{path}.lock", timeout=timeout)
    with lock:
        yield
