#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Panel (a): Out-of-fold predicted vs observed log10(EFA)."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).resolve().parent))
from efa_screening_common import (
    load_screening_dataframe, get_feature_groups, regression_oof,
    regression_metrics, write_excel, write_text, N_SPLITS, RANDOM_STATE
)


def parse_args():
    p = argparse.ArgumentParser(description="Panel (a): OOF predicted vs observed log10(EFA).")
    p.add_argument("--input", required=True, help="Input workbook, e.g. locked_493.xlsx")
    p.add_argument("--sheet", default="combined")
    p.add_argument("--outdir", default="predictive_capability_panel_a")
    p.add_argument("--n-splits", type=int, default=N_SPLITS)
    p.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return p.parse_args()


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_screening_dataframe(args.input, args.sheet)
    groups = get_feature_groups(df)
    feature_order = ["DFT only", "Chemistry only", "Combined"]

    pred_tables = []
    metric_records = []
    fold_records = []
    for group_name in feature_order:
        cols = groups[group_name]
        pred, folds = regression_oof(df, cols, target_col="log10_EFA", n_splits=args.n_splits, random_state=args.random_state)
        m = regression_metrics(df["log10_EFA"], pred)
        m["feature_group"] = group_name
        m["n_features"] = len(cols)
        metric_records.append(m)
        pred_tables.append(pd.DataFrame({
            "anonymous_id": df["anonymous_id"],
            "compositional_family": df["compositional_family"],
            "feature_group": group_name,
            "fold": folds,
            "observed_log10_EFA": df["log10_EFA"],
            "predicted_log10_EFA_oof": pred,
            "residual_observed_minus_predicted": df["log10_EFA"] - pred,
            "EFA_percentile": df["EFA_percentile"],
            "high_EFA": df["high_EFA"],
        }))
        fold_records.append(pd.DataFrame({
            "feature_group": group_name,
            "feature_column": cols,
        }))

    pred_df = pd.concat(pred_tables, ignore_index=True)
    metrics_df = pd.DataFrame(metric_records)[["feature_group", "n_features", "N", "R2", "RMSE", "MAE", "Pearson_r", "Pearson_p", "Spearman_rho", "Spearman_p"]]
    features_df = pd.concat(fold_records, ignore_index=True)

    out_xlsx = outdir / "panel_a_predicted_vs_observed_logEFA_data.xlsx"
    write_excel(out_xlsx, {
        "OOF_Predictions": pred_df,
        "CV_Metrics": metrics_df,
        "Feature_Columns": features_df,
    })

    # Plot: three mini-panels in a single Panel (a) figure.
    x = df["log10_EFA"].values
    y_all = pred_df["predicted_log10_EFA_oof"].dropna().values
    lim_min = np.nanmin([np.nanmin(x), np.nanmin(y_all)]) - 0.05
    lim_max = np.nanmax([np.nanmax(x), np.nanmax(y_all)]) + 0.05

    fig, axes = plt.subplots(1, 3, figsize=(10.8, 3.4), sharex=True, sharey=True)
    for ax, group_name in zip(axes, feature_order):
        sub = pred_df[pred_df["feature_group"] == group_name]
        ax.scatter(sub["observed_log10_EFA"], sub["predicted_log10_EFA_oof"], s=22, alpha=0.68, edgecolors="none")
        ax.plot([lim_min, lim_max], [lim_min, lim_max], linestyle="--", linewidth=1.0, color="black")
        ax.set_xlim(lim_min, lim_max)
        ax.set_ylim(lim_min, lim_max)
        ax.set_title(group_name, fontsize=11)
        m = metrics_df[metrics_df["feature_group"] == group_name].iloc[0]
        ax.text(0.05, 0.95, f"$R^2$={m['R2']:.2f}\n$\\rho$={m['Spearman_rho']:.2f}",
                transform=ax.transAxes, ha="left", va="top", fontsize=10)
    axes[0].set_ylabel(r"Predicted $\log_{10}(\mathrm{EFA})$")
    for ax in axes:
        ax.set_xlabel(r"Observed $\log_{10}(\mathrm{EFA})$")
    fig.tight_layout()
    out_png = outdir / "panel_a_predicted_vs_observed_logEFA.png"
    out_pdf = outdir / "panel_a_predicted_vs_observed_logEFA.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    lines = []
    lines.append("Panel (a): Out-of-fold predicted vs observed log10(EFA)")
    lines.append("=" * 72)
    lines.append(f"Input workbook: {args.input}")
    lines.append(f"Sheet: {args.sheet}")
    lines.append(f"Rows used: {len(df)}")
    lines.append(f"Cross-validation: {args.n_splits}-fold, grouped by cation family when repeated families are present")
    lines.append("Model: median imputation + standard scaling + RidgeCV")
    lines.append("Target: log10(EFA)")
    lines.append("")
    lines.append("Feature groups:")
    for name in feature_order:
        lines.append(f"  {name}: {len(groups[name])} features")
    lines.append("")
    lines.append("Cross-validated out-of-fold metrics:")
    lines.append(metrics_df.to_string(index=False))
    lines.append("")
    lines.append("Interpretation:")
    lines.append("  This panel tests whether CHAOS descriptors can predict the EFA ranking rather than merely correlate post hoc.")
    lines.append("  Points close to the y=x line indicate accurate out-of-fold prediction. Chemistry-only and combined")
    lines.append("  descriptor sets provide direct visual evidence that EFA is encoded in the descriptor space.")
    lines.append("")
    lines.append(f"Excel output: {out_xlsx}")
    lines.append(f"Figure PNG:   {out_png}")
    lines.append(f"Figure PDF:   {out_pdf}")
    write_text(outdir / "panel_a_predicted_vs_observed_logEFA_report.txt", lines)

    print(f"Done. Outputs written to {outdir}")

if __name__ == "__main__":
    main()
