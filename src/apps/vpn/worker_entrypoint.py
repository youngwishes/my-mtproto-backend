from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
from typing import Sequence


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lock-path", required=True, type=Path)
    parser.add_argument("--pid-path", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("worker command is required after --")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    args.lock_path.parent.mkdir(parents=True, exist_ok=True)
    args.pid_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = args.lock_path.open("a+b")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_file.close()
        return 75

    os.set_inheritable(lock_file.fileno(), True)
    args.pid_path.write_text(str(os.getpid()), encoding="ascii")
    try:
        os.execvp(args.command[0], args.command)
    finally:
        lock_file.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
