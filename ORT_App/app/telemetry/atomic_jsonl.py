from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from typing import Any, Dict, Iterator


_LOCKS_GUARD = threading.Lock()
_THREAD_LOCKS: Dict[str, threading.RLock] = {}


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _LOCKS_GUARD:
        lock = _THREAD_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _THREAD_LOCKS[key] = lock
        return lock


@contextmanager
def _cross_process_lock(path: Path) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt

            if os.fstat(fd).st_size == 0:
                os.write(fd, b"\0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("atomic JSONL write returned no progress")
        view = view[written:]


class AtomicJsonlWriter:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_lock = _thread_lock(self.path)

    def append(self, item: Dict[str, Any], *, fsync: bool | None = None) -> bool:
        line = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded = line.encode("utf-8")
        sync = os.environ.get("ORT_JSONL_FSYNC", "0") == "1" if fsync is None else bool(fsync)
        flags = os.O_CREAT | os.O_APPEND | os.O_WRONLY
        flags |= getattr(os, "O_BINARY", 0)
        try:
            with self._thread_lock:
                with _cross_process_lock(self.path):
                    fd = os.open(str(self.path), flags, 0o600)
                    try:
                        _write_all(fd, encoded)
                        if sync:
                            os.fsync(fd)
                    finally:
                        os.close(fd)
            return True
        except Exception:
            return False


def append_jsonl(path: str | os.PathLike[str], item: Dict[str, Any], *, fsync: bool | None = None) -> bool:
    return AtomicJsonlWriter(path).append(item, fsync=fsync)
