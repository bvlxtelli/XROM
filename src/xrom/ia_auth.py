"""archive.org auth ported from X-Store ia.cpp/ia.h (AGPL-3.0, see CREDITS).

Flow: GET /services/csrf-token -> POST /services/account/login/ (cookies kept
in the session), or S3 keys "Authorization: LOW access:secret".
PC note: requests handles TLS/certs/redirects — XboxTLS/dns.cpp not needed.
"""
from __future__ import annotations

from pathlib import Path

import requests

BASE = "https://archive.org"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) XROM/0.1.0"}


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    return s


def get_csrf_token(s: requests.Session) -> str:
    r = s.get(f"{BASE}/services/csrf-token",
              headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()["value"]["token"]


def login(s: requests.Session, email: str, password: str) -> bool:
    """CSRF login with the USER's own archive.org account. Returns ok."""
    token = get_csrf_token(s)
    r = s.post(
        f"{BASE}/services/account/login/",
        headers={"Accept": "application/json",
                 "Content-Type": "application/json",
                 "X-CSRF-Token": token, "Origin": BASE,
                 "Referer": f"{BASE}/login"},
        json={"username": email, "password": password,
              "remember": "true", "t": token},
        timeout=30)
    if r.status_code != 200:
        return False
    try:
        return bool(r.json().get("success", True))
    except ValueError:
        return "logged-in-sig" in s.cookies


def apply_s3(s: requests.Session, access: str, secret: str) -> None:
    s.headers["Authorization"] = f"LOW {access}:{secret}"


def import_xstore_keys(path: str) -> tuple[str, str]:
    """Read an X-Store ArchiveOrgKeys.txt (line1=access, line2=secret).

    Local-only helper: the file lives OUTSIDE the repo and is never
    committed (see .gitignore). Mirrors X-Store getS3KeysFromFile().
    """
    lines = Path(path).read_text(encoding="utf-8").split()
    if len(lines) < 2:
        raise ValueError(f"{path}: expected 2 lines (access, secret)")
    return lines[0], lines[1]
