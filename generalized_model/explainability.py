"""
SHAP-based explainability for both regression (daily count) and classification
(per-employee leave probability) heads.

For tree models we use TreeExplainer (fast, exact). For other estimators we
fall back to KernelExplainer (slower, approximate).

Public API:
    explain_global(model, X, feature_names, ...) -> dict
        Returns:
            'mean_abs_shap' : feature importance via mean |SHAP|
            'beeswarm_data' : sample of (feature_value, shap_value) pairs for plotting
    explain_local(model, x_row, feature_names, ...) -> dict
        Returns:
            'feature_contributions' : list of {feature, value, shap, direction}
            'base_value', 'prediction'
"""
from __future__ import annotations

import logging
import numpy as np
import pandas as pd

LOG = logging.getLogger("explainability")
if not LOG.handlers:
    import sys as _sys
    _h = logging.StreamHandler(_sys.stdout)
    _h.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s | %(message)s", "%H:%M:%S"))
    LOG.addHandler(_h)
LOG.setLevel(logging.INFO)


def _get_explainer(model, X_background: np.ndarray):
    """Pick the cheapest explainer that works for `model`."""
    import shap
    # Try tree explainer first
    try:
        return shap.TreeExplainer(model)
    except Exception:
        pass
    # CalibratedClassifierCV wraps a base estimator
    try:
        if hasattr(model, "calibrated_classifiers_") and model.calibrated_classifiers_:
            inner = model.calibrated_classifiers_[0].estimator
            if hasattr(inner, "feature_importances_"):
                return shap.TreeExplainer(inner)
    except Exception:
        pass
    # Fallback: kernel explainer with a small background sample (slow)
    bg = X_background[: min(100, len(X_background))]
    return shap.KernelExplainer(model.predict, bg)


def explain_global(model, X: np.ndarray, feature_names: list[str],
                   max_samples: int = 500, seed: int = 42) -> dict:
    """Compute global feature importance + sample for beeswarm plotting."""
    try:
        import shap  # noqa: F401
    except ImportError:
        LOG.warning("shap not installed — skipping explainability.")
        return {"available": False, "reason": "shap not installed"}

    rng = np.random.default_rng(seed)
    if len(X) > max_samples:
        idx = rng.choice(len(X), size=max_samples, replace=False)
        X_sample = X[idx]
    else:
        X_sample = X

    try:
        explainer = _get_explainer(model, X)
        sv = explainer.shap_values(X_sample)
        # shap_values may return list (multi-class) — take positive class for binary
        if isinstance(sv, list) and len(sv) == 2:
            sv = sv[1]
        elif isinstance(sv, np.ndarray) and sv.ndim == 3:
            # newer shap returns (n, features, classes) for binary
            sv = sv[..., 1] if sv.shape[-1] == 2 else sv.mean(axis=-1)
    except Exception as e:
        LOG.warning(f"SHAP failed: {e}")
        return {"available": False, "reason": str(e)[:200]}

    mean_abs = np.abs(sv).mean(axis=0)
    order = np.argsort(mean_abs)[::-1]
    importance = [
        {"feature": feature_names[i], "mean_abs_shap": float(mean_abs[i])}
        for i in order
    ]
    # Beeswarm sample — capped for plotting size
    bee_n = min(200, len(X_sample))
    bee_idx = rng.choice(len(X_sample), size=bee_n, replace=False)
    beeswarm = []
    for j in order[:15]:  # top 15 features
        for i in bee_idx:
            beeswarm.append({
                "feature": feature_names[j],
                "feature_value": float(X_sample[i, j]),
                "shap_value": float(sv[i, j]),
            })
    return {
        "available": True,
        "mean_abs_shap": importance,
        "beeswarm_data": beeswarm,
        "n_samples_used": len(X_sample),
    }


def explain_local(model, x_row: np.ndarray, feature_names: list[str],
                  X_background: np.ndarray, top_k: int = 10) -> dict:
    """Per-prediction breakdown: which features pushed the prediction up/down."""
    try:
        import shap  # noqa: F401
    except ImportError:
        return {"available": False, "reason": "shap not installed"}

    if x_row.ndim == 1:
        x_row = x_row.reshape(1, -1)
    try:
        explainer = _get_explainer(model, X_background)
        sv = explainer.shap_values(x_row)
        if isinstance(sv, list) and len(sv) == 2:
            sv = sv[1]
        elif isinstance(sv, np.ndarray) and sv.ndim == 3:
            sv = sv[..., 1] if sv.shape[-1] == 2 else sv.mean(axis=-1)
        sv = sv[0]
        base_value = explainer.expected_value
        if isinstance(base_value, (list, np.ndarray)):
            base_value = float(np.asarray(base_value).flatten()[-1])
    except Exception as e:
        return {"available": False, "reason": str(e)[:200]}

    contrib = []
    order = np.argsort(np.abs(sv))[::-1]
    for j in order[:top_k]:
        contrib.append({
            "feature": feature_names[j],
            "value": float(x_row[0, j]),
            "shap": float(sv[j]),
            "direction": "increases" if sv[j] > 0 else "decreases",
        })
    try:
        prediction = float(model.predict(x_row)[0])
    except Exception:
        prediction = float("nan")
    return {
        "available": True,
        "feature_contributions": contrib,
        "base_value": float(base_value),
        "prediction": prediction,
    }
