#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Panel (c): Enrichment / lift plot for high-EFA candidate screening."""
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
    load_screening_dataframe, get_feature_groups, classification_oof,
    classification_metrics, write_excel, write_text, N_SPLITS, RANDOM_STATE
)


def parse_args():
    p = argparse.ArgumentParser(description="Panel (c): Top-k enrichment/lift plot for high-EFA screening.")
    p.add_argument("--input", required=True, help="Input workbook, e.g. locked_493.xlsx")
    p.add_argument("--sheet", default="combined")
    p.add_argument("--outdir", default="predictive_capability_panel_c")
    p.add_argument("--n-splits", type=int, default=N_SPLITS)
    p.add_argument("--random-state", type=int, default=RANDOM_STATE)
    return p.parse_args()


def enrichment_curve(y_true: pd.Series, y_score: np.ndarray, group_name: str) -> pd.DataFrame:
    y = pd.Series(y_true).astype(int).reset_index(drop=True)
    s = pd.Series(y_score).reset_index(drop=True)
    n = len(y)
    total_pos = int(y.sum())
    prevalence = total_pos / n
    order = s.sort_values(ascending=False).index.to_numpy()
    y_sorted = y.iloc[order].to_numpy()
    rows = []
    for pct in range(1, 101):
        top_n = max(1, int(np.ceil(n * pct / 100.0)))
        hits = int(y_sorted[:top_n].sum())
        precision = hits / top_n
        recall = hits / total_pos if total_pos else np.nan
        enrichment = precision / prevalence if prevalence > 0 else np.nan
        rows.append({
            "feature_group": group_name,
            "top_fraction_percent": pct,
            "top_n": top_n,
            "true_high_EFA_hits": hits,
            "precision_in_top_k": precision,
            "recall_in_top_k": recall,
            "enrichment_factor": enrichment,
            "baseline_prevalence": prevalence,
        })
    return pd.DataFrame(rows)


def main():
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = load_screening_dataframe(args.input, args.sheet)
    groups = get_feature_groups(df)
    feature_order = ["DFT only", "Chemistry only", "Combined"]
    y = df["high_EFA"].astype(int)
    prevalence = float(y.mean())

    pred_tables = []
    metric_records = []
    enrich_tables = []
    top20_records = []
    for group_name in feature_order:
        cols = groups[group_name]
        score, folds = classification_oof(df, cols, target_col="high_EFA", n_splits=args.n_splits, random_state=args.random_state)
        m = classification_metrics(y, score)
        m["feature_group"] = group_name
        m["n_features"] = len(cols)
        metric_records.append(m)
        pred_df = pd.DataFrame({
            "anonymous_id": df["anonymous_id"],
            "compositional_family": df["compositional_family"],
            "feature_group": group_name,
            "fold": folds,
            "observed_high_EFA": y,
            "predicted_probability_high_EFA_oof": score,
            "EFA_percentile": df["EFA_percentile"],
        })
        pred_df["predicted_rank"] = pred_df["predicted_probability_high_EFA_oof"].rank(ascending=False, method="first").astype(int)
        pred_df["predicted_rank_percentile_high_is_best"] = 1 - ((pred_df["predicted_rank"] - 1) / (len(pred_df) - 1))
        pred_tables.append(pred_df)
        enrich = enrichment_curve(y, score, group_name)
        enrich_tables.append(enrich)
        for pct in [5, 10, 20, 25, 50]:
            row = enrich[enrich["top_fraction_percent"] == pct].iloc[0].to_dict()
            top20_records.append(row)

    pred_all = pd.concat(pred_tables, ignore_index=True)
    metrics_df = pd.DataFrame(metric_records)[["feature_group", "n_features", "N", "Prevalence", "ROC_AUC", "Average_precision", "Brier_score"]]
    enrichment_df = pd.concat(enrich_tables, ignore_index=True)
    highlight_df = pd.DataFrame(top20_records)

    out_xlsx = outdir / "panel_c_highEFA_enrichment_lift_data.xlsx"
    write_excel(out_xlsx, {
        "OOF_Probabilities": pred_all,
        "Classifier_Metrics": metrics_df,
        "Enrichment_Curve": enrichment_df,
        "TopK_Highlights": highlight_df,
    })

    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    for group_name in feature_order:
        sub = enrichment_df[enrichment_df["feature_group"] == group_name]
        ax.plot(sub["top_fraction_percent"], sub["enrichment_factor"], linewidth=2.0, label=group_name)
    ax.axhline(1.0, color="black", linestyle="--", linewidth=1.0, label="random baseline")
    ax.set_xlim(1, 100)
    ax.set_xlabel("Top-ranked candidates tested (%)")
    ax.set_ylabel("High-EFA enrichment factor")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out_png = outdir / "panel_c_highEFA_enrichment_lift.png"
    out_pdf = outdir / "panel_c_highEFA_enrichment_lift.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    lines = []
    lines.append("Panel (c): Enrichment / lift plot for high-EFA screening")
    lines.append("=" * 72)
    lines.append(f"Input workbook: {args.input}")
    lines.append(f"Sheet: {args.sheet}")
    lines.append(f"Rows used: {len(df)}")
    lines.append("Positive class: EFA_percentile >= 0.75")
    lines.append(f"Baseline high-EFA prevalence: {prevalence:.4f}")
    lines.append(f"Cross-validation: {args.n_splits}-fold, grouped by cation family when repeated families are present")
    lines.append("Model: median imputation + standard scaling + class-balanced logistic regression")
    lines.append("")
    lines.append("Classifier metrics:")
    lines.append(metrics_df.to_string(index=False))
    lines.append("")
    lines.append("Top-k enrichment highlights:")
    lines.append(highlight_df.to_string(index=False))
    lines.append("")
    lines.append("Interpretation:")
    lines.append("  The enrichment factor is the fraction of true high-EFA systems in the top-ranked candidates")
    lines.append("  divided by the overall high-EFA prevalence. Values above 1 indicate that the model reduces")
    lines.append("  the experimental search space by concentrating high-EFA entries near the top of the ranking.")
    lines.append("")
    lines.append(f"Excel output: {out_xlsx}")
    lines.append(f"Figure PNG:   {out_png}")
    lines.append(f"Figure PDF:   {out_pdf}")
    write_text(outdir / "panel_c_highEFA_enrichment_lift_report.txt", lines)

    print(f"Done. Outputs written to {outdir}")

if __name__ == "__main__":
    main()
