#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common utilities for EFA-guided predictive screening figures.

These helpers are intentionally local-only and do not depend on artifact_tool.
They use pandas/numpy/scikit-learn/matplotlib-compatible outputs.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.base import clone
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import RidgeCV, LogisticRegression
from sklearn.metrics import (
    r2_score, mean_squared_error, mean_absolute_error,
    roc_auc_score, average_precision_score, accuracy_score,
    balanced_accuracy_score, precision_score, recall_score, f1_score,
    brier_score_loss,
)
from sklearn.model_selection import KFold, StratifiedKFold, GroupKFold
try:
    from sklearn.model_selection import StratifiedGroupKFold
except Exception:  # pragma: no cover
    StratifiedGroupKFold = None

RANDOM_STATE = 42
N_SPLITS = 5

DFT_DESCRIPTOR_COLS = [
    "lat_distortion_misfit_mean",
    "lat_distortion_misfit_stdev",
    "lat_distortion_relax_distance_mean",
    "lat_distortion_relax_distance_stdev",
    "solubility_parameter",
]

TARGET_EXCLUDE = {
    "EFA",
    "efa_original_row", "match_count",
}

FEATURE_LABELS = {
    "lat_distortion_misfit_mean": r"$\bar{\epsilon}$",
    "lat_distortion_misfit_stdev": r"$\sigma_{\epsilon}$",
    "lat_distortion_relax_distance_mean": r"$\bar{d}$",
    "lat_distortion_relax_distance_stdev": r"$\sigma_d$",
    "solubility_parameter": r"$\delta_s$",
    "S_config_atom": r"$S_{\mathrm{config,atom}}$",
    "S_config_cell": r"$S_{\mathrm{config,cell}}$",
    "S_config_partial_atom": r"$S_{\mathrm{config,partial}}$",
    "S_config_rfu": r"$S_{\mathrm{config,rfu}}$",
    "S_config_species": r"$S_{\mathrm{config,species}}$",
    "S_config_sublattice": r"$S_{\mathrm{config,sublattice}}$",
    "VEC": "VEC",
    "delta_electronegativity_Allen": r"$\delta\chi_{\mathrm{Allen}}$",
    "delta_electronegativity_Ghosh": r"$\delta\chi_{\mathrm{Ghosh}}$",
    "delta_electronegativity_Pauling": r"$\delta\chi_{\mathrm{Pauling}}$",
    "delta_electronegativity_Pearson": r"$\delta\chi_{\mathrm{Pearson}}$",
    "delta_radii_Ghosh08": r"$\delta r_{\mathrm{Ghosh}}$",
    "delta_radii_Pyykko": r"$\delta r_{\mathrm{Pyykko}}$",
    "delta_radii_Slatter": r"$\delta r_{\mathrm{Slater}}$",
    "delta_radius_PT": r"$\delta r_{\mathrm{PT}}$",
    "delta_radius_Saxena": r"$\delta r_{\mathrm{Saxena}}$",
    "delta_radius_covalent_PT": r"$\delta r_{\mathrm{cov,PT}}$",
    "delta_radius_covalent": r"$\delta r_{\mathrm{cov}}$",
    "param_geo_radii_Ghosh08": r"$\Lambda_{\mathrm{Ghosh}}$",
    "param_geo_radii_Pyykko": r"$\Lambda_{\mathrm{Pyykko}}$",
    "param_geo_radii_Slatter": r"$\Lambda_{\mathrm{Slater}}$",
    "param_geo_radius_PT": r"$\Lambda_{\mathrm{PT}}$",
    "param_geo_radius_Saxena": r"$\Lambda_{\mathrm{Saxena}}$",
    "param_geo_radius_covalent_PT": r"$\Lambda_{\mathrm{cov,PT}}$",
    "param_geo_radius_covalent": r"$\Lambda_{\mathrm{cov}}$",
}

GROUP_LABELS = {
    "DFT only": "DFT only",
    "Chemistry only": "Chemistry only",
    "Combined": "Combined",
}


def excel_col_to_index(col: str) -> int:
    """Convert Excel column letters to zero-based index."""
    col = col.upper().strip()
    n = 0
    for ch in col:
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid Excel column: {col}")
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def safe_feature_label(col: str) -> str:
    return FEATURE_LABELS.get(col, col.replace("_", " "))


def percentile_rank(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.dropna()
    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out.loc[valid.index] = 0.5
        return out
    ranks = valid.rank(method="average", ascending=True)
    out.loc[valid.index] = (ranks - 1) / (n - 1)
    return out


def make_family(row: pd.Series) -> str:
    fam_cols = ["Metal1", "Metal2", "Metal3", "Metal4"]
    metals = []
    for c in fam_cols:
        if c in row.index and pd.notna(row[c]):
            val = str(row[c]).strip()
            if val and val.lower() != "nan":
                metals.append(val)
    return "-".join(sorted(metals)) if metals else "unknown_family"


def load_screening_dataframe(input_path: str | Path, sheet: str = "combined") -> pd.DataFrame:
    input_path = Path(input_path)
    df = pd.read_excel(input_path, sheet_name=sheet)
    required = ["EFA"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required target columns: {missing}")
    df = df.copy()
    df["EFA"] = pd.to_numeric(df["EFA"], errors="coerce")
    df = df.dropna(subset=["EFA"]).copy()
    df = df[df["EFA"] > 0].reset_index(drop=True)
    df["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(len(df))]
    df["compositional_family"] = df.apply(make_family, axis=1)
    df["log10_EFA"] = np.log10(df["EFA"])
    df["EFA_percentile"] = percentile_rank(df["EFA"])
    df["high_EFA"] = (df["EFA_percentile"] >= 0.75).astype(int)
    return df


def get_feature_groups(df: pd.DataFrame) -> Dict[str, List[str]]:
    dft = [c for c in DFT_DESCRIPTOR_COLS if c in df.columns]
    s_idx = excel_col_to_index("S")
    ak_idx = excel_col_to_index("AK")
    h_idx = excel_col_to_index("H")
    chemistry = [c for c in df.columns[s_idx: ak_idx + 1] if c not in TARGET_EXCLUDE]
    combined = [c for c in df.columns[h_idx: ak_idx + 1] if c not in TARGET_EXCLUDE]
    # Keep only numeric-convertible columns with at least one finite value.
    clean = {}
    for name, cols in [("DFT only", dft), ("Chemistry only", chemistry), ("Combined", combined)]:
        kept = []
        for c in cols:
            vals = pd.to_numeric(df[c], errors="coerce") if c in df.columns else pd.Series(dtype=float)
            if vals.notna().sum() > 0:
                kept.append(c)
        clean[name] = kept
    return clean


def get_cv_splits(df: pd.DataFrame, y: Optional[pd.Series] = None, classification: bool = False,
                  n_splits: int = N_SPLITS, random_state: int = RANDOM_STATE):
    groups = df["compositional_family"] if "compositional_family" in df.columns else None
    use_groups = groups is not None and groups.nunique() >= n_splits and groups.value_counts().max() > 1
    indices = np.arange(len(df))
    if classification:
        if use_groups and StratifiedGroupKFold is not None:
            cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
            return list(cv.split(indices, y, groups))
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        return list(cv.split(indices, y))
    else:
        if use_groups:
            cv = GroupKFold(n_splits=n_splits)
            return list(cv.split(indices, groups=groups))
        cv = KFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        return list(cv.split(indices))


def build_ridge_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", RidgeCV(alphas=np.logspace(-4, 4, 41))),
    ])


def build_logistic_pipeline() -> Pipeline:
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(
            C=1.0, class_weight="balanced", solver="lbfgs",
            max_iter=5000, random_state=RANDOM_STATE
        )),
    ])


def regression_oof(df: pd.DataFrame, feature_cols: List[str], target_col: str = "log10_EFA",
                   n_splits: int = N_SPLITS, random_state: int = RANDOM_STATE) -> Tuple[np.ndarray, List[int]]:
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(df[target_col], errors="coerce").values
    oof = np.full(len(df), np.nan, dtype=float)
    fold_ids = np.full(len(df), -1, dtype=int)
    splits = get_cv_splits(df, classification=False, n_splits=n_splits, random_state=random_state)
    for fold, (tr, te) in enumerate(splits, start=1):
        model = build_ridge_pipeline()
        model.fit(X.iloc[tr], y[tr])
        oof[te] = model.predict(X.iloc[te])
        fold_ids[te] = fold
    return oof, fold_ids.tolist()


def classification_oof(df: pd.DataFrame, feature_cols: List[str], target_col: str = "high_EFA",
                       n_splits: int = N_SPLITS, random_state: int = RANDOM_STATE) -> Tuple[np.ndarray, List[int]]:
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    y = pd.to_numeric(df[target_col], errors="coerce").astype(int).values
    oof = np.full(len(df), np.nan, dtype=float)
    fold_ids = np.full(len(df), -1, dtype=int)
    splits = get_cv_splits(df, y=pd.Series(y), classification=True, n_splits=n_splits, random_state=random_state)
    for fold, (tr, te) in enumerate(splits, start=1):
        model = build_logistic_pipeline()
        model.fit(X.iloc[tr], y[tr])
        oof[te] = model.predict_proba(X.iloc[te])[:, 1]
        fold_ids[te] = fold
    return oof, fold_ids.tolist()


def regression_metrics(y_true: Iterable[float], y_pred: Iterable[float]) -> Dict[str, float]:
    temp = pd.DataFrame({"y_true": y_true, "y_pred": y_pred}).dropna()
    y = temp["y_true"].values
    p = temp["y_pred"].values
    pear = stats.pearsonr(y, p) if len(temp) >= 3 else (np.nan, np.nan)
    spear = stats.spearmanr(y, p) if len(temp) >= 3 else (np.nan, np.nan)
    return {
        "N": int(len(temp)),
        "R2": float(r2_score(y, p)),
        "RMSE": float(math.sqrt(mean_squared_error(y, p))),
        "MAE": float(mean_absolute_error(y, p)),
        "Pearson_r": float(pear.statistic if hasattr(pear, "statistic") else pear[0]),
        "Pearson_p": float(pear.pvalue if hasattr(pear, "pvalue") else pear[1]),
        "Spearman_rho": float(spear.statistic if hasattr(spear, "statistic") else spear[0]),
        "Spearman_p": float(spear.pvalue if hasattr(spear, "pvalue") else spear[1]),
    }


def classification_metrics(y_true: Iterable[int], y_score: Iterable[float], threshold: float = 0.5) -> Dict[str, float]:
    temp = pd.DataFrame({"y_true": y_true, "y_score": y_score}).dropna()
    y = temp["y_true"].astype(int).values
    s = temp["y_score"].values
    pred = (s >= threshold).astype(int)
    return {
        "N": int(len(temp)),
        "Prevalence": float(np.mean(y)),
        "ROC_AUC": float(roc_auc_score(y, s)),
        "Average_precision": float(average_precision_score(y, s)),
        "Brier_score": float(brier_score_loss(y, s)),
        "Accuracy_at_0.5": float(accuracy_score(y, pred)),
        "Balanced_accuracy_at_0.5": float(balanced_accuracy_score(y, pred)),
        "Precision_at_0.5": float(precision_score(y, pred, zero_division=0)),
        "Recall_at_0.5": float(recall_score(y, pred, zero_division=0)),
        "F1_at_0.5": float(f1_score(y, pred, zero_division=0)),
    }


def write_excel(path: str | Path, sheets: Dict[str, pd.DataFrame]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, df in sheets.items():
            safe_sheet = sheet[:31]
            df.to_excel(writer, sheet_name=safe_sheet, index=False)


def write_text(path: str | Path, lines: List[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
