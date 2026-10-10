#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Panel (b): ROC and precision-recall curves for high-EFA classification."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, precision_recall_curve

sys.path.append(str(Path(__file__).resolve().parent))
from efa_screening_common import (
    load_screening_dataframe, get_feature_groups, classification_oof,
    classification_metrics, write_excel, write_text, N_SPLITS, RANDOM_STATE
)


def parse_args():
    p = argparse.ArgumentParser(description="Panel (b): ROC/PR curves for high-EFA classifier.")
    p.add_argument("--input", required=True, help="Input workbook, e.g. locked_493.xlsx")
    p.add_argument("--sheet", default="combined")
    p.add_argument("--outdir", default="predictive_capability_panel_b")
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
    y = df["high_EFA"].astype(int)
    prevalence = float(y.mean())

    pred_tables = []
    metric_records = []
    curve_records = []
    feature_records = []
    for group_name in feature_order:
        cols = groups[group_name]
        score, folds = classification_oof(df, cols, target_col="high_EFA", n_splits=args.n_splits, random_state=args.random_state)
        m = classification_metrics(y, score)
        m["feature_group"] = group_name
        m["n_features"] = len(cols)
        metric_records.append(m)
        pred_tables.append(pd.DataFrame({
            "anonymous_id": df["anonymous_id"],
            "compositional_family": df["compositional_family"],
            "feature_group": group_name,
            "fold": folds,
            "observed_high_EFA": y,
            "predicted_probability_high_EFA_oof": score,
            "EFA_percentile": df["EFA_percentile"],
        }))
        fpr, tpr, roc_thr = roc_curve(y, score)
        roc_df = pd.DataFrame({"feature_group": group_name, "curve_type": "ROC", "x": fpr, "y": tpr, "threshold": roc_thr})
        prec, rec, pr_thr = precision_recall_curve(y, score)
        # precision_recall_curve returns one fewer threshold than points.
        pr_thr_full = list(pr_thr) + [float("nan")]
        pr_df = pd.DataFrame({"feature_group": group_name, "curve_type": "PR", "x": rec, "y": prec, "threshold": pr_thr_full})
        curve_records.extend([roc_df, pr_df])
        feature_records.append(pd.DataFrame({"feature_group": group_name, "feature_column": cols}))

    pred_df = pd.concat(pred_tables, ignore_index=True)
    metrics_df = pd.DataFrame(metric_records)[["feature_group", "n_features", "N", "Prevalence", "ROC_AUC", "Average_precision", "Brier_score", "Accuracy_at_0.5", "Balanced_accuracy_at_0.5", "Precision_at_0.5", "Recall_at_0.5", "F1_at_0.5"]]
    curves_df = pd.concat(curve_records, ignore_index=True)
    features_df = pd.concat(feature_records, ignore_index=True)

    out_xlsx = outdir / "panel_b_highEFA_ROC_PR_data.xlsx"
    write_excel(out_xlsx, {
        "OOF_Probabilities": pred_df,
        "Classifier_Metrics": metrics_df,
        "Curve_Data": curves_df,
        "Feature_Columns": features_df,
    })

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.7))
    ax_roc, ax_pr = axes
    for group_name in feature_order:
        sub_roc = curves_df[(curves_df["feature_group"] == group_name) & (curves_df["curve_type"] == "ROC")]
        sub_pr = curves_df[(curves_df["feature_group"] == group_name) & (curves_df["curve_type"] == "PR")]
        m = metrics_df[metrics_df["feature_group"] == group_name].iloc[0]
        ax_roc.plot(sub_roc["x"], sub_roc["y"], linewidth=1.8, label=f"{group_name} (AUC={m['ROC_AUC']:.2f})")
        ax_pr.plot(sub_pr["x"], sub_pr["y"], linewidth=1.8, label=f"{group_name} (AP={m['Average_precision']:.2f})")
    ax_roc.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1.0)
    ax_pr.axhline(prevalence, linestyle="--", color="black", linewidth=1.0, label=f"baseline={prevalence:.2f}")
    ax_roc.set_xlim(0, 1); ax_roc.set_ylim(0, 1.02)
    ax_pr.set_xlim(0, 1); ax_pr.set_ylim(0, 1.02)
    ax_roc.set_xlabel("False positive rate")
    ax_roc.set_ylabel("True positive rate")
    ax_pr.set_xlabel("Recall")
    ax_pr.set_ylabel("Precision")
    ax_roc.set_title("ROC curve", fontsize=11)
    ax_pr.set_title("Precision–recall curve", fontsize=11)
    ax_roc.legend(frameon=False, fontsize=8)
    ax_pr.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    out_png = outdir / "panel_b_highEFA_ROC_PR_curves.png"
    out_pdf = outdir / "panel_b_highEFA_ROC_PR_curves.pdf"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")
    plt.close(fig)

    lines = []
    lines.append("Panel (b): ROC/PR curves for high-EFA classification")
    lines.append("=" * 72)
    lines.append(f"Input workbook: {args.input}")
    lines.append(f"Sheet: {args.sheet}")
    lines.append(f"Rows used: {len(df)}")
    lines.append(f"Positive class: EFA_percentile >= 0.75")
    lines.append(f"Positive-class prevalence: {prevalence:.4f}")
    lines.append(f"Cross-validation: {args.n_splits}-fold, grouped by cation family when repeated families are present")
    lines.append("Model: median imputation + standard scaling + class-balanced logistic regression")
    lines.append("")
    lines.append("Cross-validated classification metrics:")
    lines.append(metrics_df.to_string(index=False))
    lines.append("")
    lines.append("Interpretation:")
    lines.append("  ROC-AUC measures how well each descriptor group ranks high-EFA systems above other entries.")
    lines.append("  The precision–recall curve emphasizes experimental screening value because high-EFA entries")
    lines.append("  are a minority class. Curves above the baseline prevalence indicate enrichment of high-EFA candidates.")
    lines.append("")
    lines.append(f"Excel output: {out_xlsx}")
    lines.append(f"Figure PNG:   {out_png}")
    lines.append(f"Figure PDF:   {out_pdf}")
    write_text(outdir / "panel_b_highEFA_ROC_PR_report.txt", lines)

    print(f"Done. Outputs written to {outdir}")

if __name__ == "__main__":
    main()
