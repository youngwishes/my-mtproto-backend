from __future__ import annotations

import fcntl
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, final


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class FileSingleWriterLock:
    """Provide a non-blocking process lock shared through the host data mount."""

    path: Path

    @contextmanager
    def __call__(self) -> Iterator[bool]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a+b") as lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
