from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import final

from apps.vpn.infra.single_writer import FileSingleWriterLock


def read_process_command(*, pid: int) -> str:
    try:
        return (
            (Path("/proc") / str(pid) / "cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode("utf-8", errors="replace")
        )
    except OSError:
        # Portable fallback for local macOS tests; Linux containers use /proc and
        # do not need the optional `ps` binary from procps.
        pass
    result = subprocess.run(
        ("ps", "-p", str(pid), "-o", "command="),
        check=False,
        capture_output=True,
        text=True,
        timeout=2,
    )
    return result.stdout if result.returncode == 0 else ""


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNPaymentWorkerHealthCheck:
    """Prove that the live dedicated worker still owns its lifetime lock."""

    lock_path: Path
    pid_path: Path
    read_command: Callable[..., str] = read_process_command
    required_command_fragments: tuple[str, ...] = (
        "celery",
        "vpn_payment_fulfillment",
    )

    def __call__(self) -> bool:
        try:
            raw_pid = self.pid_path.read_text(encoding="ascii").strip()
            if not raw_pid.isascii() or not raw_pid.isdecimal():
                return False
            pid = int(raw_pid)
            os.kill(pid, 0)
            command = self.read_command(pid=pid)
        except (OSError, ValueError):
            return False
        if not all(fragment in command for fragment in self.required_command_fragments):
            return False
        with FileSingleWriterLock(path=self.lock_path)() as unexpectedly_acquired:
            return not unexpectedly_acquired
