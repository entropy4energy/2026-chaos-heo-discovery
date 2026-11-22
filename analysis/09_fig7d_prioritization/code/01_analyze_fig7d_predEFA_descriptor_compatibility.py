#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figure 7d analysis: predicted EFA percentile vs CHAOS descriptor compatibility score.

Its y-axis is a descriptor-only compatibility score built from CHAOS
distortion and chemistry descriptors.

Inputs
------
- locked_493.xlsx

Outputs
-------
1. Excel workbook containing plot data and OriginPro-ready worksheets.
2. TXT report describing the calculation procedure and key metrics.

Important
---------
- EFA is used only as the cross-validated model target and to define the
  true high-EFA class. Raw EFA values are not written to the public plot data.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, KFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


DFT_COLS = [
    "lat_distortion_misfit_mean",
    "lat_distortion_misfit_stdev",
    "lat_distortion_relax_distance_mean",
    "lat_distortion_relax_distance_stdev",
    "solubility_parameter",
]

CONFIG_COLS = [
    "S_config_atom",
    "S_config_cell",
    "S_config_partial_atom",
    "S_config_rfu",
    "S_config_species",
    "S_config_sublattice",
]

CHEMISTRY_COLS = [
    "VEC",
    "delta_electronegativity_Allen",
    "delta_electronegativity_Ghosh",
    "delta_electronegativity_Pauling",
    "delta_electronegativity_Pearson",
    "delta_radii_Ghosh08",
    "delta_radii_Pyykko",
    "delta_radii_Slatter",
    "delta_radius_PT",
    "delta_radius_Saxena",
    "delta_radius_covalent_PT",
    "delta_radius_covalent",
    "param_geo_radii_Ghosh08",
    "param_geo_radii_Pyykko",
    "param_geo_radii_Slatter",
    "param_geo_radius_PT",
    "param_geo_radius_Saxena",
    "param_geo_radius_covalent_PT",
    "param_geo_radius_covalent",
]

SCORE_COMPONENTS = {
    "epsilon_bar_compatibility": ("lat_distortion_misfit_mean", "lower_is_better"),
    "d_bar_compatibility": ("lat_distortion_relax_distance_mean", "lower_is_better"),
    "delta_r_Ghosh_compatibility": ("delta_radii_Ghosh08", "lower_is_better"),
    "delta_chi_Ghosh_compatibility": ("delta_electronegativity_Ghosh", "lower_is_better"),
    "Lambda_Ghosh_compatibility": ("param_geo_radii_Ghosh08", "higher_is_better"),
    "VEC_compatibility": ("VEC", "higher_is_better"),
}

CLASS_ORDER = [
    "other",
    "true high descriptor compatibility score only",
    "true high-EFA only",
    "true high-EFA + high descriptor compatibility score",
]

CLASS_CODE = {label: i for i, label in enumerate(CLASS_ORDER)}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Analyze predicted EFA percentile vs descriptor compatibility score for Figure 7d."
    )
    p.add_argument("--input", required=True, help="Input CHAOS Excel file")
    p.add_argument("--sheet", default="combined", help="Excel sheet name")
    p.add_argument("--outdir", default="fig7d_predEFA_descriptor_compatibility_outputs", help="Output directory")
    p.add_argument("--efa-col", default="EFA", help="EFA column used as model target")
    p.add_argument(
        "--feature-group",
        default="combined",
        choices=["dft", "chemistry", "combined", "combined_no_config"],
        help=(
            "Feature group for predicted EFA. 'combined' uses H-L + M-R + S-AK, "
            "matching the previous 30-feature model. 'combined_no_config' uses H-L + S-AK."
        ),
    )
    p.add_argument("--n-splits", type=int, default=5, help="Number of CV folds")
    p.add_argument("--high-efa-threshold", type=float, default=0.75, help="Observed EFA percentile threshold")
    p.add_argument(
        "--high-score-threshold",
        type=float,
        default=0.75,
        help="Descriptor compatibility score threshold",
    )
    return p.parse_args()


def check_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def percentile_rank(series: pd.Series) -> pd.Series:
    """Return 0-1 percentile ranks using rank-1 over n-1, preserving NaNs."""
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
    out.loc[valid.index] = (ranks - 1.0) / (n - 1.0)
    return out


def extract_cations(name: str) -> Tuple[str, ...]:
    """Parse cation symbols from the AFLOW-like name field."""
    if not isinstance(name, str):
        return tuple()
    head = name.split(":", 1)[0]
    # Strip common PAW suffix markers before element extraction.
    head = head.replace("_sv", "").replace("_pv", "").replace("_d", "")
    elems = re.findall(r"[A-Z][a-z]?", head)
    anions = {"O", "N", "C", "B", "F", "S", "P"}
    cations = sorted({e for e in elems if e not in anions})
    return tuple(cations)


def formula_from_cations(cations: Tuple[str, ...]) -> str:
    if not cations:
        return "unknown"
    return "(" + ",".join(cations) + ")O"


def get_feature_columns(df: pd.DataFrame, feature_group: str) -> List[str]:
    if feature_group == "dft":
        cols = DFT_COLS
    elif feature_group == "chemistry":
        cols = CHEMISTRY_COLS
    elif feature_group == "combined_no_config":
        cols = DFT_COLS + CHEMISTRY_COLS
    elif feature_group == "combined":
        cols = DFT_COLS + CONFIG_COLS + CHEMISTRY_COLS
    else:
        raise ValueError(feature_group)
    return [c for c in cols if c in df.columns]


def make_oof_regression_predictions(
    X: pd.DataFrame,
    y: pd.Series,
    groups: pd.Series,
    n_splits: int = 5,
) -> Tuple[np.ndarray, pd.DataFrame]:
    """Return out-of-fold RidgeCV predictions and fold metrics."""
    valid_mask = y.notna() & np.isfinite(y)
    X = X.loc[valid_mask].copy()
    y = y.loc[valid_mask].astype(float).copy()
    groups = groups.loc[valid_mask].astype(str).copy()

    unique_groups = groups.nunique()
    if unique_groups >= n_splits:
        splitter = GroupKFold(n_splits=n_splits)
        splits = splitter.split(X, y, groups=groups)
        cv_name = f"GroupKFold(n_splits={n_splits})"
    else:
        splitter = KFold(n_splits=n_splits, shuffle=True, random_state=42)
        splits = splitter.split(X, y)
        cv_name = f"KFold(n_splits={n_splits}, shuffle=True, random_state=42)"

    alphas = np.logspace(-4, 4, 41)
    pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("model", RidgeCV(alphas=alphas)),
        ]
    )

    pred = pd.Series(np.nan, index=X.index, dtype=float)
    fold_records = []
    for fold_id, (train_idx, test_idx) in enumerate(splits, start=1):
        train_index = X.index[train_idx]
        test_index = X.index[test_idx]
        model = pipeline.fit(X.loc[train_index], y.loc[train_index])
        y_pred = model.predict(X.loc[test_index])
        pred.loc[test_index] = y_pred
        fold_records.append(
            {
                "fold": fold_id,
                "n_train": len(train_index),
                "n_test": len(test_index),
                "alpha_selected": float(model.named_steps["model"].alpha_),
                "r2": float(r2_score(y.loc[test_index], y_pred)) if len(test_index) > 1 else np.nan,
                "rmse": float(math.sqrt(mean_squared_error(y.loc[test_index], y_pred))),
                "mae": float(mean_absolute_error(y.loc[test_index], y_pred)),
            }
        )
    fold_df = pd.DataFrame(fold_records)
    fold_df.attrs["cv_name"] = cv_name
    return pred.reindex(y.index).values, fold_df


def compatibility_component(series: pd.Series, direction: str) -> pd.Series:
    p = percentile_rank(series)
    if direction == "lower_is_better":
        return 1.0 - p
    if direction == "higher_is_better":
        return p
    raise ValueError(direction)


def classify_true(high_efa: bool, high_score: bool) -> str:
    if high_efa and high_score:
        return "true high-EFA + high descriptor compatibility score"
    if high_efa and not high_score:
        return "true high-EFA only"
    if (not high_efa) and high_score:
        return "true high descriptor compatibility score only"
    return "other"


def write_report(
    path: Path,
    args: argparse.Namespace,
    n_rows: int,
    n_features: int,
    metrics: Dict[str, float],
    class_counts: pd.DataFrame,
    region_summary: Dict[str, float],
    cv_name: str,
    feature_cols: List[str],
) -> None:
    lines = []
    lines.append("Figure 7d: predicted EFA percentile vs descriptor compatibility score")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Purpose")
    lines.append("  The y-axis is a descriptor-only compatibility score.")
    lines.append("  The x-axis remains the out-of-fold predicted EFA percentile.")
    lines.append("")
    lines.append("Inputs")
    lines.append(f"  Input workbook: {args.input}")
    lines.append(f"  Sheet: {args.sheet}")
    lines.append(f"  Rows used: {n_rows}")
    lines.append(f"  Feature group for EFA prediction: {args.feature_group}")
    lines.append(f"  Number of features: {n_features}")
    lines.append(f"  Cross-validation: {cv_name}")
    lines.append("  Model: median imputation + standard scaling + RidgeCV")
    lines.append("  EFA used: only as the regression target and to define the true high-EFA class")
    lines.append("")
    lines.append("Descriptor compatibility score")
    lines.append("  S_distortion = [1-P(epsilon_bar) + 1-P(d_bar)] / 2")
    lines.append("  S_chemistry  = [1-P(delta_r_Ghosh) + 1-P(delta_chi_Ghosh) + P(Lambda_Ghosh) + P(VEC)] / 4")
    lines.append("  S_CHAOS      = 0.5*S_distortion + 0.5*S_chemistry")
    lines.append("  Larger S_CHAOS indicates lower distortion, lower chemical mismatch, higher Lambda_Ghosh, and higher VEC.")
    lines.append("")
    lines.append("Class definitions")
    lines.append(f"  true high-EFA: observed EFA percentile >= {args.high_efa_threshold}")
    lines.append(f"  true high descriptor compatibility score: S_CHAOS >= {args.high_score_threshold}")
    lines.append("")
    lines.append("Regression metrics for predicted log10(EFA)")
    for k, v in metrics.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("True-class counts")
    lines.append(class_counts.to_string(index=False))
    lines.append("")
    lines.append("Upper-right predicted-priority region summary")
    for k, v in region_summary.items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Features used for predicted EFA")
    for c in feature_cols:
        lines.append(f"  - {c}")
    lines.append("")
    lines.append("Interpretation")
    lines.append("  This panel converts EFA prediction into a descriptor-grounded screening map.")
    lines.append("  The upper-right region corresponds to high predicted EFA and high CHAOS descriptor compatibility.")
    lines.append("  Enrichment of true high-EFA + high-compatibility systems in this region supports using CHAOS descriptors")
    lines.append("  to identify materials that are both entropy-forming and descriptor-compatible.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    df = pd.read_excel(input_path, sheet_name=args.sheet)
    check_columns(df, [args.efa_col] + list(SCORE_COMPONENTS[c][0] for c in SCORE_COMPONENTS))

    # Numeric conversion for all relevant columns.
    feature_cols = get_feature_columns(df, args.feature_group)
    check_columns(df, feature_cols)
    relevant_cols = list(dict.fromkeys([args.efa_col] + feature_cols + [col for col, _ in SCORE_COMPONENTS.values()]))
    data = df.copy()
    for col in relevant_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Drop rows without valid positive EFA, because EFA is the model target.
    data = data[data[args.efa_col].notna() & (data[args.efa_col] > 0)].reset_index(drop=True)
    n_rows = len(data)
    if n_rows < 10:
        raise ValueError("Too few rows with positive EFA to run cross-validation.")

    # Cation family labels.
    data["cation_tuple"] = data["name"].apply(extract_cations)
    data["cation_family"] = data["cation_tuple"].apply(lambda x: "-".join(x) if x else "unknown")
    data["candidate_formula"] = data["cation_tuple"].apply(formula_from_cations)
    data["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(n_rows)]
    data["CHAOS_excel_row"] = data.index + 2  # header row in Excel input

    # Out-of-fold predicted log10(EFA)
    y_log = np.log10(data[args.efa_col].astype(float))
    X = data[feature_cols]
    pred_log, fold_df = make_oof_regression_predictions(X, y_log, data["cation_family"], args.n_splits)
    data["observed_log10_EFA"] = y_log
    data["predicted_log10_EFA_oof"] = pred_log
    data["predicted_EFA_percentile"] = percentile_rank(data["predicted_log10_EFA_oof"])
    data["observed_EFA_percentile"] = percentile_rank(data[args.efa_col])

    # Descriptor compatibility score components.
    component_cols = []
    for comp_name, (col, direction) in SCORE_COMPONENTS.items():
        data[comp_name] = compatibility_component(data[col], direction)
        component_cols.append(comp_name)
    data["S_distortion"] = data[["epsilon_bar_compatibility", "d_bar_compatibility"]].mean(axis=1)
    data["S_chemistry"] = data[
        [
            "delta_r_Ghosh_compatibility",
            "delta_chi_Ghosh_compatibility",
            "Lambda_Ghosh_compatibility",
            "VEC_compatibility",
        ]
    ].mean(axis=1)
    data["descriptor_compatibility_score"] = 0.5 * data["S_distortion"] + 0.5 * data["S_chemistry"]

    data["true_high_EFA"] = data["observed_EFA_percentile"] >= args.high_efa_threshold
    data["true_high_descriptor_compatibility_score"] = data["descriptor_compatibility_score"] >= args.high_score_threshold
    data["true_class"] = [
        classify_true(h, s)
        for h, s in zip(data["true_high_EFA"], data["true_high_descriptor_compatibility_score"])
    ]
    data["true_class_code"] = data["true_class"].map(CLASS_CODE)

    # Predicted priority region: high predicted EFA and high descriptor compatibility.
    data["predicted_priority_region"] = (
        (data["predicted_EFA_percentile"] >= args.high_efa_threshold)
        & (data["descriptor_compatibility_score"] >= args.high_score_threshold)
    )
    true_both_mask = data["true_class"].eq("true high-EFA + high descriptor compatibility score")
    pred_region = data[data["predicted_priority_region"]]
    baseline_true_both = true_both_mask.mean()
    pred_precision = pred_region["true_class"].eq("true high-EFA + high descriptor compatibility score").mean() if len(pred_region) else np.nan
    pred_enrichment = pred_precision / baseline_true_both if baseline_true_both > 0 else np.nan

    # Metrics.
    valid_pred = data[["observed_log10_EFA", "predicted_log10_EFA_oof"]].dropna()
    pearson = stats.pearsonr(valid_pred["observed_log10_EFA"], valid_pred["predicted_log10_EFA_oof"])
    spearman = stats.spearmanr(valid_pred["observed_log10_EFA"], valid_pred["predicted_log10_EFA_oof"])
    metrics = {
        "N": int(len(valid_pred)),
        "R2": float(r2_score(valid_pred["observed_log10_EFA"], valid_pred["predicted_log10_EFA_oof"])),
        "RMSE": float(math.sqrt(mean_squared_error(valid_pred["observed_log10_EFA"], valid_pred["predicted_log10_EFA_oof"]))),
        "MAE": float(mean_absolute_error(valid_pred["observed_log10_EFA"], valid_pred["predicted_log10_EFA_oof"])),
        "Pearson_r": float(pearson.statistic),
        "Pearson_p": float(pearson.pvalue),
        "Spearman_rho": float(spearman.statistic),
        "Spearman_p": float(spearman.pvalue),
    }

    class_counts = (
        data["true_class"]
        .value_counts()
        .rename_axis("true_class")
        .reset_index(name="count")
    )
    class_counts["fraction"] = class_counts["count"] / len(data)
    class_counts["order"] = class_counts["true_class"].map(CLASS_CODE)
    class_counts = class_counts.sort_values("order").drop(columns="order").reset_index(drop=True)

    region_summary = {
        "rows": int(len(data)),
        "feature_group": args.feature_group,
        "n_features": int(len(feature_cols)),
        "true_high_EFA_prevalence": float(data["true_high_EFA"].mean()),
        "true_high_descriptor_compatibility_prevalence": float(data["true_high_descriptor_compatibility_score"].mean()),
        "true_high_EFA_and_high_compatibility_prevalence": float(baseline_true_both),
        "predicted_priority_region_count": int(len(pred_region)),
        "predicted_priority_region_precision_for_true_both": float(pred_precision) if not np.isnan(pred_precision) else np.nan,
        "predicted_priority_region_enrichment_for_true_both": float(pred_enrichment) if not np.isnan(pred_enrichment) else np.nan,
    }

    # Public plot data: no raw EFA values.
    plot_cols = [
        "anonymous_id",
        "CHAOS_excel_row",
        "candidate_formula",
        "cation_family",
        "predicted_EFA_percentile",
        "descriptor_compatibility_score",
        "observed_EFA_percentile",
        "true_high_EFA",
        "true_high_descriptor_compatibility_score",
        "true_class",
        "true_class_code",
        "predicted_priority_region",
        "S_distortion",
        "S_chemistry",
    ] + component_cols
    plot_df = data[plot_cols].copy()

    # OriginPro worksheet: single XY table.
    origin_xy = plot_df[[
        "predicted_EFA_percentile",
        "descriptor_compatibility_score",
        "true_class",
        "true_class_code",
        "candidate_formula",
        "anonymous_id",
        "CHAOS_excel_row",
    ]].rename(
        columns={
            "predicted_EFA_percentile": "X_predicted_EFA_percentile",
            "descriptor_compatibility_score": "Y_descriptor_compatibility_score",
        }
    )

    # OriginPro by class: padded X/Y columns for each class.
    by_class_cols = {}
    max_len = 0
    for label in CLASS_ORDER:
        sub = origin_xy[origin_xy["true_class"] == label]
        max_len = max(max_len, len(sub))
        by_class_cols[f"{CLASS_CODE[label]}_{label}_X"] = sub["X_predicted_EFA_percentile"].to_list()
        by_class_cols[f"{CLASS_CODE[label]}_{label}_Y"] = sub["Y_descriptor_compatibility_score"].to_list()
    for key, vals in by_class_cols.items():
        vals.extend([np.nan] * (max_len - len(vals)))
    origin_by_class = pd.DataFrame(by_class_cols)

    # Threshold line data for OriginPro.
    origin_thresholds = pd.DataFrame(
        {
            "vertical_x": [args.high_efa_threshold, args.high_efa_threshold],
            "vertical_y": [0, 1],
            "horizontal_x": [0, 1],
            "horizontal_y": [args.high_score_threshold, args.high_score_threshold],
        }
    )

    score_definition = pd.DataFrame(
        [
            {"quantity": "S_distortion", "definition": "[1-P(epsilon_bar)+1-P(d_bar)]/2"},
            {
                "quantity": "S_chemistry",
                "definition": "[1-P(delta_r_Ghosh)+1-P(delta_chi_Ghosh)+P(Lambda_Ghosh)+P(VEC)]/4",
            },
            {"quantity": "S_CHAOS", "definition": "0.5*S_distortion + 0.5*S_chemistry"},
            {"quantity": "high_EFA", "definition": f"observed EFA percentile >= {args.high_efa_threshold}"},
            {
                "quantity": "high_descriptor_compatibility",
                "definition": f"descriptor compatibility score >= {args.high_score_threshold}",
            },
        ]
    )

    summary_df = pd.DataFrame([region_summary])
    metrics_df = pd.DataFrame([metrics])
    feature_df = pd.DataFrame({"feature_group": args.feature_group, "feature_column": feature_cols})
    component_df = pd.DataFrame(
        [
            {"component": comp, "source_column": col, "direction": direction}
            for comp, (col, direction) in SCORE_COMPONENTS.items()
        ]
    )

    # Internal score data without raw EFA. This is sufficient for checking.
    internal_score = data[[
        "candidate_formula",
        "cation_family",
        "predicted_log10_EFA_oof",
        "predicted_EFA_percentile",
        "observed_EFA_percentile",
        "descriptor_compatibility_score",
        "true_class",
        "predicted_priority_region",
    ] + component_cols].copy()

    out_xlsx = outdir / "fig7d_predEFA_descriptor_compatibility_analysis.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        metrics_df.to_excel(writer, sheet_name="Regression_Metrics", index=False)
        fold_df.to_excel(writer, sheet_name="CV_Fold_Metrics", index=False)
        class_counts.to_excel(writer, sheet_name="True_Class_Counts", index=False)
        score_definition.to_excel(writer, sheet_name="Score_Definition", index=False)
        component_df.to_excel(writer, sheet_name="Score_Components", index=False)
        feature_df.to_excel(writer, sheet_name="Feature_Definition", index=False)
        plot_df.to_excel(writer, sheet_name="Plot_Data_Public", index=False)
        origin_xy.to_excel(writer, sheet_name="OriginPro_XY", index=False)
        origin_by_class.to_excel(writer, sheet_name="OriginPro_By_Class", index=False)
        origin_thresholds.to_excel(writer, sheet_name="OriginPro_Thresholds", index=False)
        internal_score.to_excel(writer, sheet_name="Internal_Model_Check", index=False)

        wb = writer.book
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "border": 1})
        pct_fmt = wb.add_format({"num_format": "0.000"})
        sci_fmt = wb.add_format({"num_format": "0.000E+00"})
        text_fmt = wb.add_format({"text_wrap": True, "valign": "top"})
        for sheet_name, sheet_df in {
            "Summary": summary_df,
            "Regression_Metrics": metrics_df,
            "CV_Fold_Metrics": fold_df,
            "True_Class_Counts": class_counts,
            "Score_Definition": score_definition,
            "Score_Components": component_df,
            "Feature_Definition": feature_df,
            "Plot_Data_Public": plot_df,
            "OriginPro_XY": origin_xy,
            "OriginPro_By_Class": origin_by_class,
            "OriginPro_Thresholds": origin_thresholds,
            "Internal_Model_Check": internal_score,
        }.items():
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            for j, col in enumerate(sheet_df.columns):
                ws.write(0, j, col, header_fmt)
                width = max(12, min(42, len(str(col)) + 3))
                if any(k in col.lower() for k in ["percentile", "score", "fraction", "precision", "enrichment", "r2", "rmse", "mae", "rho", "pearson", "spearman"]):
                    ws.set_column(j, j, width, pct_fmt)
                elif "p" in col.lower() and sheet_name == "Regression_Metrics":
                    ws.set_column(j, j, width, sci_fmt)
                elif sheet_df[col].dtype == object:
                    ws.set_column(j, j, min(42, max(width, 18)), text_fmt)
                else:
                    ws.set_column(j, j, width)

    out_txt = outdir / "fig7d_predEFA_descriptor_compatibility_report.txt"
    write_report(
        out_txt,
        args,
        n_rows,
        len(feature_cols),
        metrics,
        class_counts,
        region_summary,
        fold_df.attrs.get("cv_name", "unknown"),
        feature_cols,
    )

    manifest = {
        "input": str(input_path),
        "sheet": args.sheet,
        "outputs": {"excel": str(out_xlsx), "txt": str(out_txt)},
        "raw_EFA_written": False,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Done.")
    print(f"Excel: {out_xlsx}")
    print(f"TXT:   {out_txt}")


if __name__ == "__main__":
    main()
