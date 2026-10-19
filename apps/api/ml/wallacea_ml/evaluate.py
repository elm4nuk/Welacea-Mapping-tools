"""Evaluasi deteksi vs ground truth: precision, recall, dan galat hitungan per foto/petak.

Input (JSON):
{
  "model_id": "...", "model_version": "...", "split": "test",
  "iou_threshold": 0.5,
  "images": [{"image": "a.jpg", "plot_id": "P1",
              "gt":   [{"label": "plant", "bbox": [l, t, w, h]}],
              "pred": [{"label": "plant", "confidence": 0.8, "bbox": [l, t, w, h]}]}]
}
Semua bbox ternormalisasi 0–1 terhadap gambar yang sama (terorientasi EXIF).
Ground truth = label manusia/hitungan lapangan, bukan keluaran model lain.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass


def iou(a: list[float], b: list[float]) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def match(gt: list[dict], pred: list[dict], thr: float, label: str) -> tuple[int, int, int]:
    """Greedy berdasarkan confidence; satu GT hanya boleh dipasangkan sekali. Return (tp, fp, fn)."""
    g = [x["bbox"] for x in gt if x["label"] == label]
    p = sorted((x for x in pred if x["label"] == label), key=lambda x: -(x.get("confidence") or 0))
    used: set[int] = set()
    tp = 0
    for d in p:
        best, best_i = thr, None
        for i, box in enumerate(g):
            if i in used:
                continue
            v = iou(d["bbox"], box)
            if v >= best:
                best, best_i = v, i
        if best_i is not None:
            used.add(best_i)
            tp += 1
    return tp, len(p) - tp, len(g) - tp


@dataclass
class EvalReport:
    model_id: str | None
    model_version: str | None
    split: str | None
    label: str
    iou_threshold: float
    images: int
    tp: int
    fp: int
    fn: int
    precision: float | None
    recall: float | None
    count_mae_per_image: float | None
    count_mean_error_per_image: float | None   # + = model menghitung lebih banyak
    count_mae_per_plot: float | None
    per_image: list[dict]
    validation_kind: str
    caveats: list[str]


def evaluate(data: dict, label: str = "plant", leaks: list[str] | None = None) -> EvalReport:
    thr = float(data.get("iou_threshold", 0.5))
    rows, tp_s, fp_s, fn_s = [], 0, 0, 0
    plot_err: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for img in data.get("images", []):
        gt, pred = img.get("gt", []), img.get("pred", [])
        tp, fp, fn = match(gt, pred, thr, label)
        n_gt = sum(1 for x in gt if x["label"] == label)
        n_pred = sum(1 for x in pred if x["label"] == label)
        tp_s, fp_s, fn_s = tp_s + tp, fp_s + fp, fn_s + fn
        rows.append({"image": img.get("image"), "plot_id": img.get("plot_id"), "gt": n_gt, "pred": n_pred,
                     "tp": tp, "fp": fp, "fn": fn, "count_error": n_pred - n_gt})
        if img.get("plot_id"):
            plot_err[img["plot_id"]][0] += n_gt
            plot_err[img["plot_id"]][1] += n_pred
    n = len(rows)
    caveats = [
        "Metrik berlaku untuk split, kamera, ketinggian, dan tanaman pada data ini saja.",
        "Confidence model bukan akurasi; precision/recall di sini dihitung terhadap ground truth.",
        "Galat per petak menjumlahkan foto dalam petak; bila foto bertumpang tindih, ini bukan hitungan tanaman unik.",
    ]
    if leaks is None:
        kind = "unverified_split"
        caveats.append("Kebocoran split tidak diperiksa: JANGAN sebut validasi produk.")
    elif leaks:
        kind = "leaky_not_product_validation"
        caveats.append("Split bocor: " + "; ".join(leaks[:5]))
    else:
        kind = "group_held_out"
    return EvalReport(
        model_id=data.get("model_id"), model_version=data.get("model_version"), split=data.get("split"),
        label=label, iou_threshold=thr, images=n, tp=tp_s, fp=fp_s, fn=fn_s,
        precision=tp_s / (tp_s + fp_s) if tp_s + fp_s else None,
        recall=tp_s / (tp_s + fn_s) if tp_s + fn_s else None,
        count_mae_per_image=sum(abs(r["count_error"]) for r in rows) / n if n else None,
        count_mean_error_per_image=sum(r["count_error"] for r in rows) / n if n else None,
        count_mae_per_plot=(sum(abs(p - g) for g, p in plot_err.values()) / len(plot_err)) if plot_err else None,
        per_image=rows, validation_kind=kind, caveats=caveats,
    )


def report_dict(r: EvalReport) -> dict:
    return asdict(r)
