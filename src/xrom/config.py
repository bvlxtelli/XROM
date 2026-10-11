"""Local config + runtime dirs. Secrets stay out of the repo.

archive.org password: OS keyring (service "xrom", account = email) when the
`keyring` package is installed, else env XROM_IA_PASSWORD, else prompt.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_home() -> Path:
    return Path(os.environ.get("XROM_HOME", Path.home() / ".xrom"))


@dataclass
class FtpPreset:
    name: str = "Aurora"
    host: str = "192.168.0.10"
    port: int = 21
    user: str = "xbox"
    password: str = "xbox"
    remote_dir: str = "Hdd1:\\Games"
    passive: bool = False


@dataclass
class XromConfig:
    home: Path = field(default_factory=default_home)
    library_dir: str = ""
    downloads_dir: str = ""
    # archive.org (user's own account — Hydra-style, never bundled)
    ia_email: str = ""
    ia_s3_access: str = ""
    ia_s3_secret: str = ""
    # metadata providers (user's own keys)
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    tgdb_api_key: str = ""
    ss_user: str = ""
    ss_password: str = ""
    ftp: FtpPreset = field(default_factory=FtpPreset)
    delete_after_ftp: bool = False
    max_retries: int = 3
    # local-only tool paths (never committed; user machine only)
    xstore_keys_file: str = ""
    extract_xiso_exe: str = ""
    iso2god_exe: str = ""

    @property
    def cache_dir(self) -> Path:
        return self.home / "cache"

    @property
    def art_dir(self) -> Path:
        return self.home / "art"

    @property
    def bin_dir(self) -> Path:
        return self.home / "bin"

    @property
    def db_path(self) -> Path:
        return self.home / "xrom.db"

    @property
    def file_path(self) -> Path:
        return self.home / "config.json"

    def ensure_dirs(self) -> None:
        for d in (self.home, self.cache_dir, self.art_dir, self.bin_dir,
                  Path(self.library_dir or self.home / "library"),
                  Path(self.downloads_dir or self.home / "downloads")):
            d.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.ensure_dirs()
        data = asdict(self)
        self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, home: Path | None = None) -> XromConfig:
        cfg = cls(home=home or default_home())
        try:
            data = json.loads(cfg.file_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        ftp = data.pop("ftp", None)
        # pathlib round-trip
        if isinstance(data.get("home"), str):
            data["home"] = Path(data["home"])
        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        if isinstance(ftp, dict):
            cfg.ftp = FtpPreset(**{k: v for k, v in ftp.items()
                                   if k in FtpPreset.__dataclass_fields__})
        return cfg


def get_ia_password(email: str) -> str:
    """Password lookup order: keyring -> env -> '' (caller prompts)."""
    env = os.environ.get("XROM_IA_PASSWORD", "")
    if env:
        return env
    try:
        import keyring  # optional dependency

        pw = keyring.get_password("xrom", email or "archive.org")
        return pw or ""
    except Exception:
        return ""


def set_ia_password(email: str, password: str) -> bool:
    try:
        import keyring  # optional dependency

        keyring.set_password("xrom", email or "archive.org", password)
        return True
    except Exception:
        return False
