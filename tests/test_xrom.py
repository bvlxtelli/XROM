import json
import zipfile

from xrom import ia_auth, organizer
from xrom.ia_catalog import candidates, download_base, file_url
from xrom.library import Library
from xrom.models import Game
from xrom.sources.hydra_json import HydraJsonProvider, parse_size


def test_sanitize():
    assert organizer.sanitize('Halo: Combat "Evolved" /X?') == "Halo Combat Evolved X"
    assert organizer.sanitize("   ") == "Unknown Game"
    assert organizer.sanitize("a..  ") == "a"


def test_build_folder_name():
    g = Game(title="Halo 3", platform="xbox360", year=2007,
             title_id="4d5307e6")
    assert organizer.build_folder_name(g) == "Halo 3 [2007] [4D5307E6]"
    assert organizer.build_folder_name(Game(title="X")) == "X"


def test_unique(tmp_path):
    (tmp_path / "Game").mkdir()
    assert organizer.unique(tmp_path / "Game").name == "Game (2)"
    assert organizer.unique(tmp_path / "Other").name == "Other"


def test_organize_sidecar(tmp_path):
    g = Game(title="Halo 3", platform="xbox360", year=2007)
    folder = organizer.organize(g, tmp_path)
    assert folder.is_dir()
    data = json.loads((folder / ".xrom.json").read_text())
    assert data["title"] == "Halo 3" and data["year"] == 2007


def test_parse_size():
    assert parse_size("15.2 GB") == int(15.2 * 1024**3)
    assert parse_size("700 MB") == 700 * 1024**2
    assert parse_size("n/a") is None


def test_hydra_json(tmp_path):
    p = tmp_path / "src.json"
    p.write_text(json.dumps({
        "name": "mine",
        "downloads": [
            {"title": "Halo 3", "fileSize": "7.1 GB",
             "uris": ["https://x/y", "https://z/w"], "uploadDate": "2024"},
            {"title": "Gears", "fileSize": "?", "uris": "https://g",
             "uploadDate": ""}]}))
    prov = HydraJsonProvider(p)
    assert prov.source_name == "mine"
    games = prov.search("halo")
    assert len(games) == 1 and games[0].title == "Halo 3"
    dls = prov.resolve(games[0])
    assert len(dls) == 1 and len(dls[0].uris) == 2
    assert dls[0].file_size == int(7.1 * 1024**3)


def test_library(tmp_path):
    lib = Library(tmp_path / "t.db")
    lib.upsert_game(Game(title="Halo 3", platform="xbox360", year=2007),
                    folder="/g", cover_path="/c.jpg")
    lib.upsert_game(Game(title="Halo 3", platform="xbox360", year=2008),
                    folder="/g2")
    games = lib.list_games()
    assert len(games) == 1 and games[0]["year"] == 2008  # upsert
    from xrom.models import QueueItem
    qid = lib.enqueue(QueueItem("Halo 3", "https://x", "/d"))
    assert qid > 0
    assert lib.enqueue(QueueItem("Halo 3", "https://x", "/d")) == qid  # ignore dup
    lib.update_queue(qid, status="done")
    assert lib.list_queue()[0]["status"] == "done"
    lib.close()


META = {
    "server": "ia800000.us.archive.org",
    "dir": "/12/items/microsoft_xbox_a",
    "alternate_locations": {"workable": [
        {"server": "dn721604.ca.archive.org", "dir": "/0/items/microsoft_xbox_a"}]},
    "files": [
        {"name": "Halo - Combat Evolved (USA).zip", "format": "ZIP",
         "size": "6717314228"},
        {"name": "readme.txt", "format": "TEXT", "size": "10"},
    ],
}


def test_download_base():
    assert download_base(META) == "https://dn721604.ca.archive.org/0/items/microsoft_xbox_a"
    m2 = {"server": "s", "dir": "/d"}
    assert download_base(m2) == "https://s/d"


def test_file_url():
    assert file_url("https://h/dir", "Halo (USA).zip") == \
        "https://h/dir/Halo%20%28USA%29.zip"


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(self.status_code)


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def get(self, *a, **k):
        self.calls += 1
        return FakeResp(self.payload)


def test_candidates_filters_format_and_query(tmp_path):
    from xrom.ia_catalog import XBOX_IDS
    s = FakeSession(META)
    out = candidates("halo", "xbox", s, tmp_path)
    assert len(out) == len(XBOX_IDS)  # same mocked META per collection
    assert [o["ident"] for o in out] == list(XBOX_IDS)  # ident = collection
    assert out[0]["size"] == 6717314228
    assert out[0]["url"].startswith("https://dn721604")
    assert s.calls == len(XBOX_IDS)


def test_import_xstore_keys(tmp_path):
    p = tmp_path / "ArchiveOrgKeys.txt"
    p.write_text("ACCESS123\nSECRET456\n")
    assert ia_auth.import_xstore_keys(str(p)) == ("ACCESS123", "SECRET456")


def test_unzip_sanitized_and_zipslip(tmp_path):
    from xrom import extractor

    zf = tmp_path / "g.zip"
    with zipfile.ZipFile(zf, "w") as z:
        z.writestr("Halo: X/file.iso", b"iso-bytes")
        z.writestr("../../evil.txt", b"x")
    dest = tmp_path / "out"
    extractor.unzip_sanitized(zf, dest, log=lambda m: None)
    assert (dest / "Halo X" / "file.iso").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_find_xbla_dir(tmp_path):
    from xrom import extractor

    good = tmp_path / "ABCDEF12"
    (good / "000D0000").mkdir(parents=True)
    (tmp_path / "OTHER").mkdir()
    assert extractor.find_xbla_dir(tmp_path) == good
    (tmp_path / "12345678" / "00007000").mkdir(parents=True)
    assert extractor.find_xbla_dir(tmp_path) is None  # ambiguous
