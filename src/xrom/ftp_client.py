"""FTP upload to modded consoles (Aurora/DashLaunch presets). stdlib ftplib.

Console FTPDs (FtpDll) speak POSIX-style paths: "Hdd1/Games/...".
Listings may contain non-UTF8 names -> force latin-1 decoding.
"""

from __future__ import annotations

import ftplib
from collections.abc import Callable
from pathlib import Path

ProgressCb = Callable[[str, int, int | None], None]  # path, done, total
CancelCb = Callable[[], bool]


class TransferAborted(Exception):
    """Raised when the caller's cancel flag trips mid-transfer."""


def _connect(
    host: str, port: int, user: str, password: str, passive: bool, timeout: int
) -> ftplib.FTP:
    ftp = ftplib.FTP(timeout=timeout)
    ftp.encoding = "latin-1"
    ftp.connect(host.strip(), port)
    ftp.login(user.strip(), password)
    ftp.set_pasv(passive)
    return ftp


def test_connection(
    host: str, port: int, user: str, password: str, timeout: int = 10
) -> tuple[bool, str]:
    try:
        with _connect(host, port, user, password, False, timeout) as ftp:
            banner = str(ftp.getwelcome())
        return True, banner
    except (OSError, ftplib.Error, UnicodeError) as e:
        return False, f"{type(e).__name__}: {e}"


def _to_xbox_path(p: str) -> str:
    return p.replace("\\", "/").strip("/")


def _mkdirs(ftp: ftplib.FTP, remote: str) -> None:
    parts = _to_xbox_path(remote).split("/")
    acc = ""
    for part in parts:
        acc = f"{acc}/{part}" if acc else part
        try:
            ftp.mkd(acc)
        except ftplib.Error:
            pass  # exists


def upload_tree(
    local_dir: str | Path,
    remote_dir: str,
    host: str,
    port: int,
    user: str,
    password: str,
    passive: bool = False,
    cb: ProgressCb | None = None,
    cancelled: CancelCb | None = None,
) -> int:
    """Recursive upload. Returns file count. Raises on failure/abort."""
    local_dir = Path(local_dir)
    files = [p for p in sorted(local_dir.rglob("*")) if p.is_file()]
    count = 0
    with _connect(host, port, user, password, passive, 60) as ftp:
        for path in files:
            if cancelled and cancelled():
                raise TransferAborted("cancelled by user")
            rel = path.relative_to(local_dir).as_posix()
            remote = _to_xbox_path(f"{remote_dir}/{rel}")
            _mkdirs(ftp, remote.rsplit("/", 1)[0] if "/" in remote else "")
            total = path.stat().st_size
            done = 0

            def _cb(block: bytes, _p=path, _t=total) -> None:
                nonlocal done
                if cancelled and cancelled():
                    raise TransferAborted("cancelled by user")
                done += len(block)
                if cb:
                    cb(str(_p), done, _t)

            with open(path, "rb") as f:
                ftp.storbinary(f"STOR {remote}", f, callback=_cb)
            count += 1
    return count
