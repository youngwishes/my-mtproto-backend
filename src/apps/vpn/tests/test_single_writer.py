from __future__ import annotations

import multiprocessing
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from apps.vpn.infra.single_writer import FileSingleWriterLock
from apps.vpn.infra.worker_health import VPNPaymentWorkerHealthCheck


def _hold_lock(
    path: str, ready: multiprocessing.Queue[bool], release: multiprocessing.Queue[bool]
) -> None:
    lock = FileSingleWriterLock(path=Path(path))
    with lock() as acquired:
        ready.put(acquired)
        release.get(timeout=5)


class FileSingleWriterLockTest(SimpleTestCase):
    def test_only_one_process_can_hold_shared_file_lock(self) -> None:
        with TemporaryDirectory() as directory:
            lock_path = Path(directory) / "vpn-payment-writer.lock"
            ready: multiprocessing.Queue[bool] = multiprocessing.Queue()
            release: multiprocessing.Queue[bool] = multiprocessing.Queue()
            process = multiprocessing.Process(
                target=_hold_lock,
                args=(str(lock_path), ready, release),
            )
            process.start()
            try:
                self.assertTrue(ready.get(timeout=5))
                with FileSingleWriterLock(path=lock_path)() as acquired:
                    self.assertFalse(acquired)
            finally:
                release.put(True)
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)

            self.assertEqual(process.exitcode, 0)
            with FileSingleWriterLock(path=lock_path)() as acquired:
                self.assertTrue(acquired)


class VPNPaymentWorkerLifetimeOwnershipTest(SimpleTestCase):
    def _start_worker(self, *, owner_lock: Path, owner_pid: Path) -> subprocess.Popen[bytes]:
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "apps.vpn.worker_entrypoint",
                "--lock-path",
                str(owner_lock),
                "--pid-path",
                str(owner_pid),
                "--",
                sys.executable,
                "-c",
                "import time; time.sleep(60)",
                "celery",
                "-Q",
                "vpn_payment_fulfillment",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def _wait_for_pid_file(self, path: Path) -> None:
        deadline = time.monotonic() + 5
        while not path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(path.exists(), "owner PID file was not created")

    def test_duplicate_worker_cannot_serve_health_stays_up_when_receipt_lock_is_busy_and_releases_on_exit(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            owner_lock = root / "owner.lock"
            owner_pid = root / "owner.pid"
            receipt_lock = root / "receipt.lock"
            owner = self._start_worker(owner_lock=owner_lock, owner_pid=owner_pid)
            try:
                self._wait_for_pid_file(owner_pid)
                health = VPNPaymentWorkerHealthCheck(
                    lock_path=owner_lock,
                    pid_path=owner_pid,
                    required_command_fragments=("celery", "vpn_payment_fulfillment"),
                )
                self.assertTrue(health())

                duplicate = self._start_worker(owner_lock=owner_lock, owner_pid=owner_pid)
                self.assertNotEqual(duplicate.wait(timeout=5), 0)
                self.assertTrue(health())

                with FileSingleWriterLock(path=receipt_lock)() as acquired:
                    self.assertTrue(acquired)
                    self.assertTrue(health())
            finally:
                owner.terminate()
                owner.wait(timeout=5)

            with FileSingleWriterLock(path=owner_lock)() as acquired:
                self.assertTrue(acquired)
