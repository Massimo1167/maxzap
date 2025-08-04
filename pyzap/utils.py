from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
import os
import re
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


_INVALID_CHARS = re.compile(r'[\\/*?:"<>|]')


def safe_filename(name: str, max_length: int = 100) -> str:
    """Return a filesystem-safe version of ``name`` limited in length."""
    name = re.sub(r"\s+", " ", name.strip())
    name = _INVALID_CHARS.sub("_", name)
    if len(name) > max_length:
        base, ext = os.path.splitext(name)
        name = base[: max_length - len(ext)] + ext
    return name
