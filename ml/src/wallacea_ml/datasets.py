"""Katalog dataset publik + pengunduh EKSPLISIT.

Tidak ada unduhan otomatis. Urutan kerja yang disarankan:
1. `datasets list` / `datasets info <id>`  — baca katalog (configs/datasets.yaml).
2. `datasets remote <id>`                  — metadata langsung dari Zenodo/Mendeley (ukuran, checksum, lisensi).
3. `datasets ls-zip <id> <file>`           — daftar isi zip jarak jauh (HTTP Range; hanya central directory).
4. `datasets sample <id> <file> --pattern` — ambil BEBERAPA berkas dari zip jarak jauh (sampel kecil).
5. `datasets download <id> <file> --yes`   — unduh berkas penuh, verifikasi checksum. Tanpa `--yes` = dry-run.
"""
from __future__ import annotations

import fnmatch
import hashlib
import http.client
import io
import json
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

import yaml

ML_ROOT = Path(__file__).resolve().parents[2]
CATALOG = ML_ROOT / "configs" / "datasets.yaml"
USER_AGENT = "wallacea-ml/0.2 (+dataset inspection)"


def load_catalog(path: str | Path = CATALOG) -> dict[str, dict]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return {d["id"]: d for d in data["datasets"]}


def _get(url: str, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 — URL dari katalog repo


def _json(url: str) -> dict | list:
    with _get(url) as r:
        return json.loads(r.read().decode("utf-8"))


@dataclass
class RemoteFile:
    name: str
    size: int
    url: str
    checksum: str | None   # "md5:..." atau "sha256:..."


def remote_files(entry: dict) -> tuple[dict, list[RemoteFile]]:
    """Metadata dari sumber asli. Return (ringkasan, daftar berkas)."""
    src = entry["source"]
    if src["kind"] == "zenodo":
        d = _json(f"https://zenodo.org/api/records/{src['record']}")
        m = d["metadata"]
        files = [RemoteFile(f["key"], int(f["size"]), f["links"]["self"], f.get("checksum")) for f in d.get("files", [])]
        meta = {"title": m.get("title"), "doi": d.get("doi"), "version": m.get("version"),
                "publication_date": m.get("publication_date"), "license": (m.get("license") or {}).get("id")}
        return meta, files
    if src["kind"] == "mendeley":
        base = f"https://data.mendeley.com/public-api/datasets/{src['dataset']}"
        d = _json(f"{base}?version={src['version']}")
        fl = _json(f"{base}/files?folder_id=root&version={src['version']}")
        files = [RemoteFile(f["filename"], int(f["size"]), f["content_details"]["download_url"],
                            "sha256:" + f["content_details"]["sha256_hash"]) for f in fl]
        meta = {"title": d.get("name"), "doi": (d.get("doi") or {}).get("id"), "version": d.get("version"),
                "publication_date": d.get("publish_date"), "license": (d.get("data_licence") or {}).get("short_name")}
        return meta, files
    raise ValueError(f"Sumber {src['kind']!r} tidak mendukung metadata otomatis; lihat URL di katalog.")


def find_file(entry: dict, name: str) -> RemoteFile:
    _, files = remote_files(entry)
    for f in files:
        if f.name == name:
            return f
    raise SystemExit(f"Berkas {name!r} tidak ada. Tersedia: {[f.name for f in files]}")


class HttpRangeFile(io.RawIOBase):
    """File-like read-only di atas HTTP Range, cukup untuk `zipfile` membaca central directory
    dan anggota tertentu tanpa mengunduh seluruh arsip."""

    def __init__(self, url: str, size: int, block: int = 1 << 20):
        self.url, self.size, self.block, self.pos = url, size, block, 0
        self._cache: dict[int, bytes] = {}
        self.bytes_fetched = 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i: int) -> bytes:
        if i not in self._cache:
            start, end = i * self.block, min(self.size, (i + 1) * self.block) - 1
            for attempt in range(4):
                try:
                    with _get(self.url, {"Range": f"bytes={start}-{end}"}) as r:
                        if r.status != 206:
                            raise RuntimeError("Server tidak mendukung HTTP Range; gunakan `download --yes`.")
                        data = r.read()
                    if len(data) == end - start + 1:
                        break
                except (http.client.IncompleteRead, urllib.error.URLError, TimeoutError, ConnectionError):
                    if attempt == 3:
                        raise
            else:
                raise RuntimeError(f"Range {start}-{end} tidak lengkap setelah 4 percobaan.")
            self._cache[i] = data
            self.bytes_fetched += end - start + 1
            if len(self._cache) > 64:
                self._cache.pop(next(iter(self._cache)))
        return self._cache[i]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        out = bytearray()
        while n > 0 and self.pos < self.size:
            i, o = divmod(self.pos, self.block)
            chunk = self._block(i)[o:o + n]
            out += chunk
            self.pos += len(chunk)
            n -= len(chunk)
        return bytes(out)

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def remote_zip(f: RemoteFile) -> tuple[zipfile.ZipFile, HttpRangeFile]:
    h = HttpRangeFile(f.url, f.size)
    return zipfile.ZipFile(h), h


def sample_from_zip(f: RemoteFile, patterns: list[str], dest: Path, limit: int, max_bytes: int) -> list[Path]:
    """Ekstrak ≤ `limit` anggota yang cocok pola glob, total ≤ `max_bytes` (ukuran tak terkompresi)."""
    z, h = remote_zip(f)
    picked, total = [], 0
    for info in sorted(z.infolist(), key=lambda i: i.filename):
        if info.is_dir() or not any(fnmatch.fnmatch(info.filename, p) for p in patterns):
            continue
        if len(picked) >= limit or total + info.file_size > max_bytes:
            break
        target = (dest / info.filename).resolve()
        if dest.resolve() not in target.parents:
            raise ValueError(f"Path anggota zip tidak aman: {info.filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, open(target, "wb") as out:
            shutil.copyfileobj(src, out)
        picked.append(target)
        total += info.file_size
    print(f"Diambil {len(picked)} berkas ({total / 1e6:.1f} MB); diunduh via Range ±{h.bytes_fetched / 1e6:.1f} MB.",
          file=sys.stderr)
    return picked


def _verify(path: Path, checksum: str | None) -> bool | None:
    if not checksum:
        return None
    algo, expected = checksum.split(":", 1)
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest() == expected


def download(f: RemoteFile, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f.name
    if target.is_file() and target.stat().st_size == f.size and _verify(target, f.checksum) is not False:
        print(f"Sudah ada dan cocok: {target}", file=sys.stderr)
        return target
    part = target.with_suffix(target.suffix + ".part")
    done = part.stat().st_size if part.is_file() else 0
    headers = {"Range": f"bytes={done}-"} if done else {}
    with _get(f.url, headers, timeout=120) as r, open(part, "ab" if done and r.status == 206 else "wb") as out:
        if done and r.status != 206:
            done = 0
        while chunk := r.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            print(f"\r{done / 1e6:,.0f} / {f.size / 1e6:,.0f} MB", end="", file=sys.stderr)
    print(file=sys.stderr)
    ok = _verify(part, f.checksum)
    if ok is False:
        raise SystemExit(f"Checksum TIDAK cocok untuk {part}; berkas tidak dipakai.")
    part.replace(target)
    print(f"Tersimpan: {target} (checksum {'cocok' if ok else 'tidak tersedia'})", file=sys.stderr)
    return target


def safe_dirname(dataset_id: str) -> str:
    return urllib.parse.quote(dataset_id, safe="-_.")
