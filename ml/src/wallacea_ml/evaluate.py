"""Evaluasi deteksi vs ground truth: precision, recall, AP@IoU, dan galat hitungan per foto/petak.

Input (JSON):
{
  "model_id": "...", "model_version": "...", "split": "test", "domain": "public:uavmulticrop",
  "iou_threshold": 0.5,
  "images": [{"image": "a.jpg", "plot_id": "P1",
              "gt":   [{"label": "plant", "bbox": [l, t, w, h]}],
              "pred": [{"label": "plant", "confidence": 0.8, "bbox": [l, t, w, h]}]}]
}
Semua bbox ternormalisasi 0–1 terhadap gambar yang sama (terorientasi EXIF).
Ground truth = label manusia/hitungan lapangan, bukan keluaran model lain.

Threshold confidence DIPILIH di split validation (`sweep` + `choose_threshold`), lalu diterapkan apa adanya
pada split test. AP dihitung dari semua prediksi (tidak bergantung threshold).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field


def iou(a: list[float], b: list[float]) -> float:
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw = max(0.0, min(ax2, bx2) - max(a[0], b[0]))
    ih = max(0.0, min(ay2, by2) - max(a[1], b[1]))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def match_flags(gt: list[dict], pred: list[dict], thr: float, label: str) -> tuple[list[tuple[float, bool]], int]:
    """Greedy berdasarkan confidence; satu GT hanya boleh dipasangkan sekali.
    Return ([(confidence, tp?)] urut confidence menurun, jumlah GT)."""
    g = [x["bbox"] for x in gt if x["label"] == label]
    p = sorted((x for x in pred if x["label"] == label), key=lambda x: -(x.get("confidence") or 0))
    used: set[int] = set()
    flags = []
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
        flags.append((float(d.get("confidence") or 0), best_i is not None))
    return flags, len(g)


def match_details(gt: list[dict], pred: list[dict], thr: float, label: str) -> dict:
    """Seperti `match_flags`, tetapi mengembalikan kotaknya: {'tp': [(pred, gt)], 'fp': [pred], 'fn': [gt]} —
    untuk visualisasi false positive & objek terlewat."""
    g = [x for x in gt if x["label"] == label]
    p = sorted((x for x in pred if x["label"] == label), key=lambda x: -(x.get("confidence") or 0))
    used: set[int] = set()
    out = {"tp": [], "fp": [], "fn": []}
    for d in p:
        best, best_i = thr, None
        for i, box in enumerate(g):
            if i not in used and (v := iou(d["bbox"], box["bbox"])) >= best:
                best, best_i = v, i
        if best_i is None:
            out["fp"].append(d)
        else:
            used.add(best_i)
            out["tp"].append((d, g[best_i]))
    out["fn"] = [b for i, b in enumerate(g) if i not in used]
    return out


def match(gt: list[dict], pred: list[dict], thr: float, label: str) -> tuple[int, int, int]:
    """Return (tp, fp, fn)."""
    flags, n_gt = match_flags(gt, pred, thr, label)
    tp = sum(1 for _, ok in flags if ok)
    return tp, len(flags) - tp, n_gt - tp


def average_precision(flags: list[tuple[float, bool]], n_gt: int) -> float | None:
    """AP all-point interpolation (gaya VOC2010+/COCO-101 tanpa sampling) dari flag TP/FP gabungan."""
    if n_gt == 0:
        return None
    flags = sorted(flags, key=lambda x: -x[0])
    tp = fp = 0
    prec, rec = [], []
    for _, ok in flags:
        tp, fp = tp + ok, fp + (not ok)
        prec.append(tp / (tp + fp))
        rec.append(tp / n_gt)
    for i in range(len(prec) - 2, -1, -1):        # envelope presisi monoton
        prec[i] = max(prec[i], prec[i + 1])
    ap, prev_r = 0.0, 0.0
    for p, r in zip(prec, rec):
        ap += (r - prev_r) * p
        prev_r = r
    return ap


def _filter(pred: list[dict], conf: float | None) -> list[dict]:
    return pred if conf is None else [x for x in pred if (x.get("confidence") or 0) >= conf]


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
    conf_threshold: float | None = None        # diterapkan sebelum P/R & hitungan
    ap: float | None = None                    # AP@iou_threshold dari semua prediksi
    f1: float | None = None
    count_relative_error: float | None = None  # Σ|pred−gt| / Σgt
    gt_total: int = 0
    domain: str | None = None
    notes: list[str] = field(default_factory=list)


def evaluate(data: dict, label: str = "plant", leaks: list[str] | None = None,
             conf_threshold: float | None = None) -> EvalReport:
    thr = float(data.get("iou_threshold", 0.5))
    rows, tp_s, fp_s, fn_s = [], 0, 0, 0
    all_flags: list[tuple[float, bool]] = []
    gt_total = 0
    plot_err: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for img in data.get("images", []):
        gt, pred_all = img.get("gt", []), img.get("pred", [])
        flags, n_gt_img = match_flags(gt, pred_all, thr, label)
        all_flags += flags
        pred = _filter(pred_all, conf_threshold)
        tp, fp, fn = match(gt, pred, thr, label)
        n_gt = sum(1 for x in gt if x["label"] == label)
        n_pred = sum(1 for x in pred if x["label"] == label)
        gt_total += n_gt
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
    domain = data.get("domain")
    if domain and domain != "k919":
        caveats.append(f"Domain {domain}: hasil dataset publik, BUKAN kinerja pada foto K919.")
    if leaks is None:
        kind = "unverified_split"
        caveats.append("Kebocoran split tidak diperiksa: JANGAN sebut validasi produk.")
    elif leaks:
        kind = "leaky_not_product_validation"
        caveats.append("Split bocor: " + "; ".join(leaks[:5]))
    else:
        kind = "group_held_out"
    precision = tp_s / (tp_s + fp_s) if tp_s + fp_s else None
    recall = tp_s / (tp_s + fn_s) if tp_s + fn_s else None
    return EvalReport(
        model_id=data.get("model_id"), model_version=data.get("model_version"), split=data.get("split"),
        label=label, iou_threshold=thr, images=n, tp=tp_s, fp=fp_s, fn=fn_s,
        precision=precision, recall=recall,
        count_mae_per_image=sum(abs(r["count_error"]) for r in rows) / n if n else None,
        count_mean_error_per_image=sum(r["count_error"] for r in rows) / n if n else None,
        count_mae_per_plot=(sum(abs(p - g) for g, p in plot_err.values()) / len(plot_err)) if plot_err else None,
        per_image=rows, validation_kind=kind, caveats=caveats,
        conf_threshold=conf_threshold, ap=average_precision(all_flags, gt_total),
        f1=(2 * precision * recall / (precision + recall)) if precision and recall else None,
        count_relative_error=(sum(abs(r["count_error"]) for r in rows) / gt_total) if gt_total else None,
        gt_total=gt_total, domain=domain,
    )


def sweep(data: dict, thresholds: list[float] | None = None, label: str = "plant") -> list[dict]:
    """Precision/recall/F1/MAE hitungan per threshold confidence. Jalankan pada split VALIDATION."""
    ts = thresholds or [round(0.05 * i, 2) for i in range(1, 20)]
    out = []
    for t in ts:
        r = evaluate(data, label, leaks=[], conf_threshold=t)
        out.append({"conf": t, "precision": r.precision, "recall": r.recall, "f1": r.f1,
                    "count_mae_per_image": r.count_mae_per_image, "count_mean_error_per_image": r.count_mean_error_per_image})
    return out


def choose_threshold(rows: list[dict], criterion: str = "count_mae") -> dict:
    """`count_mae` (default — tujuan produk = hitungan per foto) atau `f1`. Seri → threshold lebih tinggi."""
    if criterion == "f1":
        key = lambda r: (-(r["f1"] or 0), -r["conf"])  # noqa: E731
    elif criterion == "count_mae":
        key = lambda r: (r["count_mae_per_image"] if r["count_mae_per_image"] is not None else float("inf"), -r["conf"])  # noqa: E731
    else:
        raise ValueError("criterion: count_mae | f1")
    return {**min(rows, key=key), "criterion": criterion}


def report_dict(r: EvalReport) -> dict:
    return asdict(r)
