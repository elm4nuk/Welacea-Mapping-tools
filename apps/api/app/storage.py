"""Penyimpanan berkas lokal, di luar root publik. Nama acak; nama asli hanya metadata DB."""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

_KEY = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{32}(_display|_thumb)?\.(jpg|png|webp)$")


class Storage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def new_base() -> str:
        h = uuid.uuid4().hex
        return f"{h[:2]}/{h}"

    def path(self, key: str) -> Path:
        if not _KEY.match(key):
            raise ValueError("storage key tidak valid")
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValueError("storage key keluar dari root")
        return p

    def write(self, key: str, data: bytes) -> None:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + f".{uuid.uuid4().hex[:8]}.tmp")
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()

    def delete(self, *keys: str | None) -> None:
        for key in keys:
            if not key:
                continue
            try:
                self.path(key).unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
