"""Pemuat `.env` minimal (tanpa dependensi) untuk `python -m app`.

Format: satu `NAMA=nilai` per baris; `#` di awal baris = komentar; prefiks `export ` boleh; tanda kutip tunggal/ganda
pembungkus dibuang. Backslash TIDAK diproses sebagai escape, jadi path Windows ditulis apa adanya:

    WALLACEA_MODEL_PATH=C:\\Users\\nama\\Model Tanaman\\best.pt

Variabel yang sudah ada di environment proses TIDAK ditimpa (nilai dari skrip PowerShell/terminal menang).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EnvFileError(ValueError):
    pass


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        name, sep, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not sep or not _NAME.match(name):
            raise EnvFileError(f"{path.name} baris {lineno}: harus berbentuk NAMA=nilai (ditemukan: {raw.strip()[:60]!r}).")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[name] = value
    return values


def load_env_file(path: Path, environ=os.environ) -> list[str]:
    """Isi environ dari berkas; kembalikan nama variabel yang benar-benar diset (tanpa nilai, aman untuk log)."""
    applied = []
    for name, value in parse_env_file(path).items():
        if name in environ:
            continue
        environ[name] = value
        applied.append(name)
    return applied
