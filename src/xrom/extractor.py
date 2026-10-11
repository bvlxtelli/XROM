"""Post-download extraction. No links, no creds — local files only.

Pipeline (mirrors X-Store getGame + extract-xiso-gui flag mapping):
  .zip -> unzip (sanitized) -> find .iso -> per-platform backend
  .7z  -> py7zr   (sanitized) -> find .iso -> per-platform backend
  .iso -> direct to backend
Backends:
  xbox    -> extract-xiso -x -d <dest> <iso>   (BSD, runtime-fetched)
  xbox360 -> Iso2God.exe -i <iso> -o <dest>    (closed freeware, user path)
  xbla    -> XBLA title-dir detect (xblaParsing.cpp logic) + copytree
"""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from collections.abc import Callable
from pathlib import Path

from . import organizer
from .tools_fetch import tool_path

LogCb = Callable[[str], None]
ProgCb = Callable[[int, int], None]  # (done_files, total_files)

_XBLA_CONTENT = {"000D0000", "00007000", "00004000", "00000002", "00020000",
                 "000B0000", "000E0000", "02000000", "00030000", "00009000"}
_HEX8 = re.compile(r"^[0-9a-fA-F]{8}$")


def _lognoop(msg: str) -> None:
    _ = msg


def _prognoop(done: int, total: int) -> None:
    _ = (done, total)


def unzip_sanitized(archive: Path, dest: Path,
                    log: LogCb = _lognoop,
                    prog: ProgCb = _prognoop) -> Path:
    """Extract zip, sanitizing each name part (X-Store AppendRelativePath)."""
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]
        for n, info in enumerate(entries, 1):
            prog(n, len(entries))
            parts = [organizer.sanitize(p) for p in
                     Path(info.filename).parts]
            if any(p in ("", ".", "..") for p in parts):
                log(f"skip unsafe entry: {info.filename}")
                continue
            target = dest.joinpath(*parts)
            if not str(target.resolve()).startswith(str(dest.resolve())):
                log(f"skip zip-slip: {info.filename}")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    return dest


def un7z(archive: Path, dest: Path, log: LogCb = _lognoop) -> Path:
    import py7zr  # optional at import time, required at call time

    dest.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive, "r") as zf:
        zf.extractall(dest)
    log(f"7z extracted: {archive.name}")
    return dest


def find_iso(root: Path) -> Path | None:
    for pat in ("*.iso", "*.iso.001"):
        hits = sorted(root.rglob(pat))
        if hits:
            return hits[0]
    return None


def find_xbla_dir(root: Path) -> Path | None:
    """xblaParsing.cpp: dir named ^[0-9a-f]{8}$ containing a content folder."""
    matches: list[Path] = []
    for d in root.rglob("*"):
        if d.is_dir() and _HEX8.match(d.name):
            try:
                subs = {c.name.upper() for c in d.iterdir() if c.is_dir()}
            except OSError:
                continue
            if subs & _XBLA_CONTENT:
                matches.append(d)
    return matches[0] if len(matches) == 1 else None


def run_extract_xiso(iso: Path, dest: Path, bin_dir: Path,
                     skip_sysupdate: bool = False,
                     log: LogCb = _lognoop) -> Path:
    exe = tool_path("extract-xiso", bin_dir)
    if exe is None:
        raise RuntimeError("extract-xiso not found — set path in Config "
                           "or fetch it (Tools).")
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [str(exe)] + (["-s"] if skip_sysupdate else []) + \
        ["-d", str(dest), "-x", str(iso)]
    log(f"$ {' '.join(cmd)}")
    p = subprocess.run(cmd, check=False, capture_output=True, text=True,
                       errors="replace")
    log(p.stdout[-2000:] + p.stderr[-2000:])
    if p.returncode != 0:
        raise RuntimeError(f"extract-xiso failed (rc={p.returncode})")
    return dest


def run_iso2god(iso: Path, dest: Path, iso2god_exe: Path,
                log: LogCb = _lognoop) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = [str(iso2god_exe), "-i", str(iso), "-o", str(dest)]
    log(f"$ {' '.join(cmd)}")
    p = subprocess.run(cmd, check=False, capture_output=True, text=True,
                       errors="replace")
    log(p.stdout[-2000:] + p.stderr[-2000:])
    if p.returncode != 0:
        raise RuntimeError(f"Iso2God failed (rc={p.returncode})")
    return dest


def extract_download(path: str | Path, platform: str, out_root: str | Path,
                     bin_dir: Path, iso2god_exe: str = "",
                     log: LogCb = _lognoop,
                     prog: ProgCb = _prognoop) -> Path:
    """Full pipeline: archive -> workdir -> backend -> out_root/<game>."""
    src = Path(path)
    out_root = Path(out_root)
    work = out_root / "_work" / src.stem
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    suffix = src.suffix.lower()
    if suffix == ".zip":
        log("Unpacking zip…")
        unzip_sanitized(src, work, log, prog)
    elif suffix == ".7z":
        log("Unpacking 7z…")
        prog(0, 1)
        un7z(src, work, log)
        prog(1, 1)
    elif suffix == ".iso":
        work = src.parent  # backend reads the iso in place
    else:
        raise ValueError(f"unsupported file: {src.suffix}")

    dest = organizer.unique(out_root / organizer.sanitize(src.stem))
    if platform == "xbla":
        log("Locating XBLA title dir…")
        found = find_xbla_dir(work) or work
        shutil.copytree(found, dest)
        log(f"XBLA copied: {found} -> {dest}")
        return dest
    iso = src if suffix == ".iso" else find_iso(work)
    if iso is None:
        raise RuntimeError("no .iso found after unpacking")
    if platform == "xbox":
        log("Running extract-xiso…")
        return run_extract_xiso(iso, dest, bin_dir, log=log)
    if platform == "xbox360":
        if not iso2god_exe:
            raise RuntimeError("Iso2God path not set — see Config tab.")
        log("Running Iso2God…")
        return run_iso2god(iso, dest, Path(iso2god_exe), log)
    raise ValueError(f"unknown platform: {platform}")
