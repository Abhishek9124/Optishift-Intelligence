"""
Drift monitoring across training runs.

Two flavours of drift we care about:
1. **Data drift** — has the distribution of incoming data shifted? Detected
   via PSI (Population Stability Index) on the daily target series and key
   features.
2. **Performance drift** — has the new model's WAPE/RMSE meaningfully
   worsened compared to the previous run?

A run is "promotable" if both data drift PSI is moderate AND performance has
not regressed beyond a configurable tolerance.

Public API:
    compute_drift(prev_metadata, new_metadata, prev_history, new_history) -> dict
    promotion_decision(drift_report, ...) -> dict
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class DriftConfig:
    psi_buckets: int = 10
    psi_warn: float = 0.10        # 0.10–0.25 = moderate drift (industry rule)
    psi_alert: float = 0.25
    wape_regress_max: float = 1.10  # new must be <= 1.10 * prev to promote
    rmse_regress_max: float = 1.15


def _bucket_edges(reference: np.ndarray, n: int) -> np.ndarray:
    """Equal-frequency buckets on the reference distribution."""
    if len(reference) == 0:
        return np.array([0.0, 1.0])
    qs = np.linspace(0, 1, n + 1)
    edges = np.quantile(reference, qs)
    # ensure strictly increasing
    edges = np.unique(edges)
    if len(edges) < 2:
        edges = np.array([reference.min() - 1, reference.max() + 1])
    return edges


def psi(reference: np.ndarray, current: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index between two distributions.

    Reference rule of thumb:
      < 0.10 — no shift
      0.10 – 0.25 — moderate shift, investigate
      > 0.25 — significant shift
    """
    if len(reference) == 0 or len(current) == 0:
        return float("inf")
    edges = _bucket_edges(reference, buckets)
    ref_counts, _ = np.histogram(reference, bins=edges)
    cur_counts, _ = np.histogram(current, bins=edges)
    ref_pct = ref_counts / max(ref_counts.sum(), 1)
    cur_pct = cur_counts / max(cur_counts.sum(), 1)
    eps = 1e-6
    ref_pct = np.where(ref_pct == 0, eps, ref_pct)
    cur_pct = np.where(cur_pct == 0, eps, cur_pct)
    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def compute_drift(prev_metadata: dict | None,
                  new_metadata: dict,
                  prev_target_series: np.ndarray | None,
                  new_target_series: np.ndarray,
                  config: DriftConfig | None = None) -> dict:
    cfg = config or DriftConfig()
    out: dict = {"data_drift": {}, "performance_drift": {}, "warnings": []}

    if prev_target_series is not None and len(prev_target_series) > 0:
        target_psi = psi(np.asarray(prev_target_series, dtype=float),
                         np.asarray(new_target_series, dtype=float),
                         cfg.psi_buckets)
        out["data_drift"]["target_psi"] = target_psi
        if target_psi >= cfg.psi_alert:
            out["warnings"].append(f"Target PSI {target_psi:.3f} >= {cfg.psi_alert} — significant data drift.")
        elif target_psi >= cfg.psi_warn:
            out["warnings"].append(f"Target PSI {target_psi:.3f} >= {cfg.psi_warn} — moderate data drift, investigate.")

    if prev_metadata is not None:
        prev_test = prev_metadata.get("test_metrics", {})
        new_test = new_metadata.get("test_metrics", {})
        for metric_key, max_ratio in (("WAPE", cfg.wape_regress_max), ("RMSE", cfg.rmse_regress_max)):
            prev_v = prev_test.get(metric_key)
            new_v = new_test.get(metric_key)
            if prev_v and new_v and prev_v > 0:
                ratio = new_v / prev_v
                out["performance_drift"][metric_key + "_ratio"] = ratio
                if ratio > max_ratio:
                    out["warnings"].append(
                        f"{metric_key} regressed: new {new_v:.4f} vs prev {prev_v:.4f} "
                        f"(ratio {ratio:.2f}x > limit {max_ratio:.2f}x)"
                    )

        # Also compare data fingerprint to surface "did the input change at all?"
        if prev_metadata.get("data_fingerprint") and new_metadata.get("data_fingerprint"):
            out["fingerprint_changed"] = (
                prev_metadata["data_fingerprint"] != new_metadata["data_fingerprint"]
            )

    out["promotable"] = not out["warnings"]
    return out


def promotion_decision(drift_report: dict) -> dict:
    """Yes/No gate on whether to promote the new model to production."""
    if drift_report.get("promotable", False):
        return {"promote": True, "reason": "All drift checks passed."}
    return {"promote": False, "reason": "; ".join(drift_report.get("warnings", []))}
