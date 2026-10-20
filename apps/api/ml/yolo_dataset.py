"""Pemeriksaan dataset YOLO detection sebelum training. Hanya stdlib + PyYAML; tidak butuh Ultralytics/PyTorch.

Struktur yang diharapkan (lihat dataset-example/README.md):

    <root>/images/{train,val,test}/*.jpg|png   <root>/labels/{train,val,test}/*.txt
    label: satu baris per kotak `class_id x_center y_center width height`, dinormalisasi 0–1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
REQUIRED_SPLITS = ("train", "val")


@dataclass
class SplitStats:
    images: int = 0
    labelled: int = 0
    boxes: int = 0
    empty: int = 0          # gambar tanpa berkas label / label kosong (latar belakang; sah tetapi dihitung)


@dataclass
class DatasetReport:
    names: list[str] = field(default_factory=list)
    splits: dict[str, SplitStats] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _names(cfg: dict) -> list[str]:
    names = cfg.get("names")
    if isinstance(names, dict):
        return [str(names[k]) for k in sorted(names, key=int)]
    if isinstance(names, list):
        return [str(n) for n in names]
    return []


def _label_dir(image_dir: Path) -> Path:
    # Konvensi Ultralytics: .../images/<split> → .../labels/<split>
    parts = list(image_dir.parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "images":
            parts[i] = "labels"
            return Path(*parts)
    return image_dir.parent / "labels" / image_dir.name


def check_dataset(yaml_path: Path, max_errors: int = 20) -> DatasetReport:
    import yaml

    rep = DatasetReport()
    if not yaml_path.is_file():
        rep.errors.append(f"dataset.yaml tidak ditemukan: {yaml_path}")
        return rep
    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    rep.names = _names(cfg)
    if not rep.names:
        rep.errors.append("dataset.yaml: `names` wajib diisi, mis. names: {0: jagung}.")
    root = dataset_root(yaml_path, cfg)
    if "download" in cfg:
        rep.warnings.append("Key `download` di dataset.yaml diabaikan: skrip WALLACEA tidak mengunduh dataset.")
    if "test" not in cfg:
        rep.warnings.append("Tidak ada split `test`. Sisihkan foto dari lahan/penerbangan yang TIDAK dipakai train/val "
                            "agar evaluasi akhir jujur.")
    for split in ("train", "val", "test"):
        if split not in cfg:
            if split in REQUIRED_SPLITS:
                rep.errors.append(f"dataset.yaml: split `{split}` wajib.")
            continue
        image_dir = root / str(cfg[split])
        st = rep.splits.setdefault(split, SplitStats())
        if not image_dir.is_dir():
            rep.errors.append(f"Folder gambar {split} tidak ada: {image_dir}")
            continue
        label_dir = _label_dir(image_dir)
        for img in sorted(p for p in image_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS):
            st.images += 1
            lbl = label_dir / img.relative_to(image_dir).with_suffix(".txt")
            if not lbl.is_file():
                st.empty += 1
                continue
            lines = [ln for ln in lbl.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if not lines:
                st.empty += 1
                continue
            st.labelled += 1
            for n, ln in enumerate(lines, start=1):
                problem = _check_line(ln, len(rep.names))
                if problem:
                    if len(rep.errors) < max_errors:
                        rep.errors.append(f"{lbl.relative_to(root) if lbl.is_relative_to(root) else lbl}:{n}: {problem}")
                else:
                    st.boxes += 1
        if st.images == 0:
            rep.errors.append(f"Split {split} tidak berisi gambar ({image_dir}).")
        elif st.boxes == 0:
            rep.errors.append(f"Split {split} tidak punya satu pun bounding box. Foto harus dilabeli dulu.")
    return rep


def dataset_root(yaml_path: Path, cfg: dict) -> Path:
    root = Path(cfg.get("path") or yaml_path.parent)
    return root if root.is_absolute() else (yaml_path.parent / root).resolve()


def write_resolved_yaml(yaml_path: Path, out_dir: Path) -> Path:
    """Salinan dataset.yaml dengan `path` absolut (Ultralytics mengartikan path relatif terhadap folder kerja, bukan
    terhadap berkas yaml) dan TANPA key `download` (Ultralytics akan mengunduh dataset bila key itu ada)."""
    import yaml

    cfg = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    cfg["path"] = str(dataset_root(yaml_path, cfg))
    cfg.pop("download", None)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "dataset.resolved.yaml"
    out.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return out


def _check_line(line: str, nc: int) -> str | None:
    parts = line.split()
    if len(parts) != 5:
        return (f"harus 5 angka `class x_center y_center width height` (ditemukan {len(parts)}); "
                "label segmentasi/polygon tidak dipakai untuk model deteksi ini")
    try:
        cls = int(parts[0])
        x, y, w, h = (float(v) for v in parts[1:])
    except ValueError:
        return "berisi nilai bukan angka"
    if not 0 <= cls < max(nc, 1):
        return f"class_id {cls} di luar names (0..{nc - 1})"
    if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
        return "koordinat harus dinormalisasi 0–1 (bukan piksel)"
    return None


def format_report(rep: DatasetReport) -> str:
    lines = [f"Kelas ({len(rep.names)}): " + ", ".join(f"{i}={n}" for i, n in enumerate(rep.names))]
    for split, st in rep.splits.items():
        lines.append(f"  {split:5s}: {st.images} gambar, {st.labelled} berlabel, {st.boxes} kotak, "
                     f"{st.empty} tanpa kotak")
    lines += [f"[PERINGATAN] {w}" for w in rep.warnings]
    lines += [f"[GAGAL] {e}" for e in rep.errors]
    return "\n".join(lines)
