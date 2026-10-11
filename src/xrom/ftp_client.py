"""FTP upload to modded consoles (Aurora/DashLaunch presets). stdlib ftplib."""
from __future__ import annotations

import ftplib
from collections.abc import Callable
from pathlib import Path

ProgressCb = Callable[[str, int, int | None], None]  # path, done, total


def _to_xbox_path(p: str) -> str:
    return p.replace("/", "\\")


def test_connection(host: str, port: int, user: str, password: str,
                    timeout: int = 10) -> tuple[bool, str]:
    try:
        with ftplib.FTP(timeout=timeout) as ftp:
            ftp.connect(host, port)
            ftp.login(user, password)
            banner = str(ftp.getwelcome())
        return True, banner
    except (OSError, ftplib.Error) as e:
        return False, f"{type(e).__name__}: {e}"


def _mkdirs(ftp: ftplib.FTP, remote: str) -> None:
    parts = _to_xbox_path(remote).strip("\\").split("\\")
    acc = ""
    for part in parts:
        acc = f"{acc}\\{part}" if acc else part
        try:
            ftp.mkd(acc)
        except ftplib.Error:
            pass  # exists


def upload_tree(local_dir: str | Path, remote_dir: str, host: str, port: int,
                user: str, password: str, passive: bool = False,
                cb: ProgressCb | None = None) -> int:
    """Recursive upload. Returns file count. Raises on failure."""
    local_dir = Path(local_dir)
    files = [p for p in sorted(local_dir.rglob("*")) if p.is_file()]
    count = 0
    with ftplib.FTP(timeout=60) as ftp:
        ftp.connect(host, port)
        ftp.login(user, password)
        ftp.set_pasv(passive)
        for path in files:
            rel = path.relative_to(local_dir).as_posix()
            remote = _to_xbox_path(f"{remote_dir}\\{rel}")
            _mkdirs(ftp, str(Path(_to_xbox_path(remote)).parent))
            total = path.stat().st_size
            done = 0

            def _cb(block: bytes, _p=path, _t=total) -> None:
                nonlocal done
                done += len(block)
                if cb:
                    cb(str(_p), done, _t)

            with open(path, "rb") as f:
                ftp.storbinary(f"STOR {remote}", f, callback=_cb)
            count += 1
    return count
