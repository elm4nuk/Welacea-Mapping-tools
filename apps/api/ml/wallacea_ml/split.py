"""Split berdasarkan grup (lahan/penerbangan), bukan acak per foto.

Foto berurutan dari satu penerbangan saling bertumpang tindih; tile dari satu foto induk berbagi piksel.
Bila keduanya tersebar di train dan test, angka evaluasi menjadi terlalu optimistis dan BUKAN validasi produk.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .manifest import ImageEntry, Manifest

SPLITS = ("train", "val", "test")


@dataclass
class SplitResult:
    group_by: str
    assignments: dict[str, str]          # image → split
    groups: dict[str, list[str]]         # split → daftar grup
    leaks: list[str]

    @property
    def is_product_validation(self) -> bool:
        return not self.leaks and bool(self.groups.get("test"))


def _group_key(e: ImageEntry, group_by: str) -> str:
    return e.field_id if group_by == "field" else f"{e.field_id}/{e.flight_id}"


def _stable_rank(key: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def group_split(manifest: Manifest, group_by: str = "field", ratios=(0.7, 0.15, 0.15), seed: str = "wallacea",
                ) -> SplitResult:
    if group_by not in ("field", "flight"):
        raise ValueError("group_by harus 'field' atau 'flight'")
    by_parent = {e.image: e for e in manifest.images}
    groups: dict[str, list[ImageEntry]] = defaultdict(list)
    for e in manifest.images:
        root = e
        while root.parent_image and root.parent_image in by_parent:   # tile ikut grup foto induk
            root = by_parent[root.parent_image]
        groups[_group_key(root, group_by)].append(e)
    keys = sorted(groups, key=lambda k: _stable_rank(k, seed))
    n = len(keys)
    if n < 3:
        raise ValueError(f"Butuh ≥ 3 grup ({group_by}) agar train/val/test terpisah; ada {n}.")
    n_test = max(1, round(n * ratios[2]))
    n_val = max(1, round(n * ratios[1]))
    if n - n_test - n_val < 1:
        n_val = max(1, n - n_test - 1)
    split_of = {k: ("test" if i < n_test else "val" if i < n_test + n_val else "train") for i, k in enumerate(keys)}
    assignments = {e.image: split_of[k] for k, es in groups.items() for e in es}
    out_groups = {s: sorted(k for k in keys if split_of[k] == s) for s in SPLITS}
    return SplitResult(group_by, assignments, out_groups, check_leakage(manifest, assignments, group_by))


def check_leakage(manifest: Manifest, assignments: dict[str, str], group_by: str = "field") -> list[str]:
    """Kebocoran: grup (lahan bila group_by=field; penerbangan selalu), foto induk, atau berkas identik
    (sha256) muncul di > 1 split."""
    leaks: list[str] = []
    by_image = {e.image: e for e in manifest.images}
    checks = [("flight", lambda e: f"{e.field_id}/{e.flight_id}"), ("sha256", lambda e: e.sha256),
              ("parent_image", lambda e: e.parent_image or e.image)]
    if group_by == "field":
        checks.insert(0, ("field", lambda e: e.field_id))
    for label, keyf in checks:
        seen: dict[str, set[str]] = defaultdict(set)
        for img, split in assignments.items():
            if img in by_image:
                seen[keyf(by_image[img])].add(split)
        for key, splits in seen.items():
            if len(splits) > 1:
                leaks.append(f"{label} '{key}' ada di {sorted(splits)}")
    missing = [e.image for e in manifest.images if e.image not in assignments]
    if missing:
        leaks.append(f"{len(missing)} gambar tidak punya split")
    return leaks


def yolo_dataset_yaml(manifest: Manifest, root: str) -> str:
    names = {idx: label for label, idx in manifest.label_map.items()}
    lines = [f"# Dataset {manifest.crop_type} — dibuat oleh wallacea_ml.split", f"path: {root}",
             "train: splits/train.txt", "val: splits/val.txt", "test: splits/test.txt", "names:"]
    lines += [f"  {i}: {names[i]}" for i in sorted(names)]
    return "\n".join(lines) + "\n"
