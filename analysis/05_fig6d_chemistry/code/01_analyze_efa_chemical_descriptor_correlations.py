#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze correlations between EFA and non-DFT chemical descriptors in the
CHAOS database.

Purpose
-------
This script uses EFA and non-DFT chemistry descriptors only.
It computes, for each chemistry descriptor:
  1) Pearson correlation with EFA
  2) Spearman correlation with EFA
  3) Benjamini-Hochberg FDR-corrected p-values
  4) Absolute-correlation rankings

Outputs
-------
  - Excel workbook containing data used for the heatmap and ranking tables:
      efa_chemical_descriptor_correlations.xlsx
  - TXT report explaining the calculation process:
      efa_chemical_descriptor_correlation_report.txt

Recommended command
-------------------
python 01_analyze_efa_chemical_descriptor_correlations.py \
    --input locked_493.xlsx \
    --sheet combined \
    --outdir efa_chemical_descriptor_correlation_outputs

Default chemistry descriptors
-----------------------------
By default, the script uses Excel columns S:AK, which correspond to non-DFT
chemistry descriptors in the uploaded CHAOS dataset.

Default heatmap focus descriptors
---------------------------------
The heatmap sheets are ordered as:
  VEC, δχ_Ghosh, δr_Ghosh, δr_PT, Λ_Ghosh, Λ_PT
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd
from scipy import stats


# Manuscript-style display labels.
LABEL_MAP = {
    "VEC": "VEC",
    "delta_electronegativity_Allen": r"$\delta\chi_{\mathrm{Allen}}$",
    "delta_electronegativity_Ghosh": r"$\delta\chi_{\mathrm{Ghosh}}$",
    "delta_electronegativity_Pauling": r"$\delta\chi_{\mathrm{Pauling}}$",
    "delta_electronegativity_Pearson": r"$\delta\chi_{\mathrm{Pearson}}$",
    "delta_radii_Ghosh08": r"$\delta r_{\mathrm{Ghosh}}$",
    "delta_radii_Pyykko": r"$\delta r_{\mathrm{Pyykk\ddot{o}}}$",
    "delta_radii_Slatter": r"$\delta r_{\mathrm{Slater}}$",
    "delta_radius_PT": r"$\delta r_{\mathrm{PT}}$",
    "delta_radius_Saxena": r"$\delta r_{\mathrm{Saxena}}$",
    "delta_radius_covalent_PT": r"$\delta r_{\mathrm{cov,PT}}$",
    "delta_radius_covalent": r"$\delta r_{\mathrm{cov}}$",
    "param_geo_radii_Ghosh08": r"$\Lambda_{\mathrm{Ghosh}}$",
    "param_geo_radii_Pyykko": r"$\Lambda_{\mathrm{Pyykk\ddot{o}}}$",
    "param_geo_radii_Slatter": r"$\Lambda_{\mathrm{Slater}}$",
    "param_geo_radius_PT": r"$\Lambda_{\mathrm{PT}}$",
    "param_geo_radius_Saxena": r"$\Lambda_{\mathrm{Saxena}}$",
    "param_geo_radius_covalent_PT": r"$\Lambda_{\mathrm{cov,PT}}$",
    "param_geo_radius_covalent": r"$\Lambda_{\mathrm{cov}}$",
}

TARGET_LABELS = {
    "EFA": "EFA",
}

DEFAULT_FOCUS_COLUMNS = [
    "VEC",
    "delta_electronegativity_Ghosh",
    "delta_radii_Ghosh08",
    "delta_radius_PT",
    "param_geo_radii_Ghosh08",
    "param_geo_radius_PT",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze EFA correlations with non-DFT chemistry descriptors."
    )
    parser.add_argument("--input", required=True, help="Input Excel workbook")
    parser.add_argument("--sheet", default="combined", help="Input sheet name. Default: combined")
    parser.add_argument("--outdir", default="efa_chemical_descriptor_correlation_outputs", help="Output directory")
    parser.add_argument("--efa-col", default="EFA", help="EFA column name. Default: EFA")
    parser.add_argument("--feature-start", default="S", help="Excel letter for first chemistry descriptor column. Default: S")
    parser.add_argument("--feature-end", default="AK", help="Excel letter for last chemistry descriptor column. Default: AK")
    parser.add_argument(
        "--focus-cols",
        nargs="*",
        default=DEFAULT_FOCUS_COLUMNS,
        help="Descriptor columns used in the main heatmap. Default: VEC, δχ_Ghosh, δr_Ghosh, δr_PT, Λ_Ghosh, Λ_PT",
    )
    return parser.parse_args()


def excel_col_to_zero_index(col: str) -> int:
    col = col.strip().upper()
    value = 0
    for ch in col:
        if not ("A" <= ch <= "Z"):
            raise ValueError(f"Invalid Excel column letter: {col}")
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value - 1


def check_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}\nAvailable columns: {list(df.columns)}")


def benjamini_hochberg(pvals: Sequence[float]) -> np.ndarray:
    """Return Benjamini-Hochberg FDR-adjusted p-values."""
    p = np.asarray(pvals, dtype=float)
    q = np.full_like(p, np.nan, dtype=float)
    valid = np.isfinite(p)
    if valid.sum() == 0:
        return q

    pv = p[valid]
    n = len(pv)
    order = np.argsort(pv)
    ranked = pv[order]
    adjusted = ranked * n / np.arange(1, n + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0, 1)

    q_valid = np.empty_like(adjusted)
    q_valid[order] = adjusted
    q[valid] = q_valid
    return q


def calc_corr(x: pd.Series, y: pd.Series, method: str) -> Dict[str, float]:
    temp = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    n = len(temp)
    if n < 3:
        return {"N": n, "coefficient": np.nan, "p_value": np.nan}

    if method == "Pearson":
        res = stats.pearsonr(temp["x"].values, temp["y"].values)
    elif method == "Spearman":
        res = stats.spearmanr(temp["x"].values, temp["y"].values)
    else:
        raise ValueError("method must be 'Pearson' or 'Spearman'")

    return {"N": int(n), "coefficient": float(res.statistic), "p_value": float(res.pvalue)}


def summary_stats(series: pd.Series, label: str) -> Dict[str, float | str | int]:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return {"variable": label, "N": 0}
    return {
        "variable": label,
        "N": int(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)),
        "min": float(s.min()),
        "q25": float(s.quantile(0.25)),
        "median": float(s.median()),
        "q75": float(s.quantile(0.75)),
        "max": float(s.max()),
    }


def make_heatmap_matrix(corr_long: pd.DataFrame, method: str, focus_cols: List[str], target_cols: List[str]) -> pd.DataFrame:
    subset = corr_long[
        (corr_long["method"] == method)
        & (corr_long["descriptor_column"].isin(focus_cols))
        & (corr_long["target_column"].isin(target_cols))
    ].copy()
    matrix = subset.pivot(index="target_label", columns="descriptor_label", values="coefficient")
    row_order = [TARGET_LABELS.get(t, t) for t in target_cols]
    col_order = [LABEL_MAP.get(c, c) for c in focus_cols]
    return matrix.reindex(index=row_order, columns=col_order)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input workbook not found: {input_path}")

    df = pd.read_excel(input_path, sheet_name=args.sheet)
    start_idx = excel_col_to_zero_index(args.feature_start)
    end_idx = excel_col_to_zero_index(args.feature_end)
    if start_idx < 0 or end_idx >= len(df.columns) or start_idx > end_idx:
        raise ValueError(f"Invalid feature range {args.feature_start}:{args.feature_end} for columns {list(df.columns)}")

    chemistry_cols = list(df.columns[start_idx : end_idx + 1])
    target_cols = [args.efa_col]
    check_columns(df, target_cols + chemistry_cols + args.focus_cols)

    data = df.copy()
    for col in target_cols + chemistry_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=target_cols).reset_index(drop=True)
    data["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(len(data))]

    if {"Metal1", "Metal2", "Metal3", "Metal4"}.issubset(data.columns):
        fam_cols = ["Metal1", "Metal2", "Metal3", "Metal4"]
        def make_family(row):
            vals = [str(row[c]).strip() for c in fam_cols if pd.notna(row[c]) and str(row[c]).strip().lower() != "nan"]
            return "-".join(sorted(vals)) if vals else "unknown_family"
        data["compositional_family"] = data.apply(make_family, axis=1)
    else:
        data["compositional_family"] = "unknown_family"

    records = []
    for target_col in target_cols:
        for descriptor_col in chemistry_cols:
            for method in ["Pearson", "Spearman"]:
                result = calc_corr(data[target_col], data[descriptor_col], method)
                records.append(
                    {
                        "target_column": target_col,
                        "target_label": TARGET_LABELS.get(target_col, target_col),
                        "descriptor_column": descriptor_col,
                        "descriptor_label": LABEL_MAP.get(descriptor_col, descriptor_col),
                        "method": method,
                        "N": result["N"],
                        "coefficient": result["coefficient"],
                        "abs_coefficient": abs(result["coefficient"]) if np.isfinite(result["coefficient"]) else np.nan,
                        "p_value": result["p_value"],
                    }
                )
    corr_long = pd.DataFrame(records)

    # FDR correction is applied separately for each target and method across all chemistry descriptors.
    corr_long["p_value_fdr_bh"] = np.nan
    corr_long["abs_correlation_rank"] = np.nan
    for (target_col, method), group in corr_long.groupby(["target_column", "method"]):
        idx = group.index
        corr_long.loc[idx, "p_value_fdr_bh"] = benjamini_hochberg(group["p_value"].values)
        corr_long.loc[idx, "abs_correlation_rank"] = group["abs_coefficient"].rank(ascending=False, method="min")

    corr_long = corr_long.sort_values(["target_column", "method", "abs_correlation_rank", "descriptor_column"]).reset_index(drop=True)

    heatmap_pearson = make_heatmap_matrix(corr_long, "Pearson", args.focus_cols, target_cols)
    heatmap_spearman = make_heatmap_matrix(corr_long, "Spearman", args.focus_cols, target_cols)

    # FDR-corrected p-value matrices for the focus descriptors.
    focus = corr_long[corr_long["descriptor_column"].isin(args.focus_cols)].copy()
    p_fdr_pearson = focus[focus["method"] == "Pearson"].pivot(index="target_label", columns="descriptor_label", values="p_value_fdr_bh")
    p_fdr_spearman = focus[focus["method"] == "Spearman"].pivot(index="target_label", columns="descriptor_label", values="p_value_fdr_bh")
    p_fdr_pearson = p_fdr_pearson.reindex(index=heatmap_pearson.index, columns=heatmap_pearson.columns)
    p_fdr_spearman = p_fdr_spearman.reindex(index=heatmap_spearman.index, columns=heatmap_spearman.columns)

    # Raw plot data for the focus descriptors; includes only the columns needed to reproduce the figure.
    plot_data = data[["anonymous_id", "compositional_family"] + target_cols + args.focus_cols].copy()

    summary = pd.DataFrame(
        [summary_stats(data[c], c) for c in target_cols + chemistry_cols]
    )

    config = pd.DataFrame(
        [
            {"parameter": "input_workbook", "value": str(input_path)},
            {"parameter": "sheet", "value": args.sheet},
            {"parameter": "rows_used", "value": len(data)},
            {"parameter": "feature_range", "value": f"{args.feature_start}:{args.feature_end}"},
            {"parameter": "chemistry_descriptor_count", "value": len(chemistry_cols)},
            {"parameter": "chemistry_descriptor_columns", "value": ", ".join(chemistry_cols)},
            {"parameter": "focus_descriptor_columns", "value": ", ".join(args.focus_cols)},
            {"parameter": "correlation_methods", "value": "Pearson, Spearman"},
            {"parameter": "FDR_method", "value": "Benjamini-Hochberg, applied separately by target and method"},
        ]
    )

    out_xlsx = outdir / "efa_chemical_descriptor_correlations.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        plot_data.to_excel(writer, sheet_name="Plot_Data_Focus", index=False)
        corr_long.to_excel(writer, sheet_name="Correlation_Long_All", index=False)
        heatmap_pearson.to_excel(writer, sheet_name="Heatmap_Pearson")
        heatmap_spearman.to_excel(writer, sheet_name="Heatmap_Spearman")
        p_fdr_pearson.to_excel(writer, sheet_name="FDR_Pearson_Focus")
        p_fdr_spearman.to_excel(writer, sheet_name="FDR_Spearman_Focus")
        summary.to_excel(writer, sheet_name="Summary_Statistics", index=False)
        config.to_excel(writer, sheet_name="Config", index=False)

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "border": 1})
        num_fmt = workbook.add_format({"num_format": "0.000"})
        sci_fmt = workbook.add_format({"num_format": "0.000E+00"})
        text_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})

        for sheet_name in writer.sheets:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)

        for sheet_name, df_sheet in [
            ("Plot_Data_Focus", plot_data),
            ("Correlation_Long_All", corr_long),
            ("Summary_Statistics", summary),
            ("Config", config),
        ]:
            ws = writer.sheets[sheet_name]
            for j, col in enumerate(df_sheet.columns):
                ws.write(0, j, col, header_fmt)
                width = min(max(len(str(col)) + 4, 14), 42)
                if col in ["coefficient", "abs_coefficient"]:
                    ws.set_column(j, j, width, num_fmt)
                elif col in ["p_value", "p_value_fdr_bh"]:
                    ws.set_column(j, j, width, sci_fmt)
                elif col in ["descriptor_label", "target_label", "chemistry_descriptor_columns", "focus_descriptor_columns"]:
                    ws.set_column(j, j, 36, text_fmt)
                else:
                    ws.set_column(j, j, width)

    out_txt = outdir / "efa_chemical_descriptor_correlation_report.txt"
    lines = []
    lines.append("EFA vs non-DFT chemical descriptors: calculation report")
    lines.append("=" * 78)
    lines.append("")
    lines.append("1. Purpose")
    lines.append("   This analysis quantifies how non-DFT chemistry descriptors relate to the")
    lines.append("   entropy-forming ability (EFA).")
    lines.append("")
    lines.append("2. Input data")
    lines.append(f"   Input workbook: {input_path}")
    lines.append(f"   Sheet: {args.sheet}")
    lines.append(f"   Rows used after dropping missing EFA: {len(data)}")
    lines.append(f"   Non-DFT chemistry descriptor range: Excel columns {args.feature_start}:{args.feature_end}")
    lines.append(f"   Number of chemistry descriptors analyzed: {len(chemistry_cols)}")
    lines.append("")
    lines.append("3. Target")
    lines.append(f"   {args.efa_col}: entropy-forming ability, plotted as EFA")
    lines.append("")
    lines.append("4. Heatmap focus descriptors")
    for c in args.focus_cols:
        lines.append(f"   {c} -> {LABEL_MAP.get(c, c)}")
    lines.append("")
    lines.append("5. Calculation procedure")
    lines.append("   a) Read the input workbook and select non-DFT chemistry descriptors from S:AK.")
    lines.append("   b) Convert EFA and descriptor columns to numeric values.")
    lines.append("   c) For every target–descriptor pair, calculate Pearson and Spearman correlations.")
    lines.append("   d) For each target and method, apply Benjamini-Hochberg FDR correction across all S:AK descriptors.")
    lines.append("   e) Rank descriptors by absolute correlation coefficient for each target and method.")
    lines.append("   f) Store all long-form results, heatmap matrices, FDR matrices, and plot-data columns in Excel.")
    lines.append("")
    lines.append("6. Main Spearman heatmap matrix")
    lines.append(heatmap_spearman.to_string())
    lines.append("")
    lines.append("7. Pearson heatmap matrix")
    lines.append(heatmap_pearson.to_string())
    lines.append("")
    lines.append("8. Top descriptors by absolute Spearman correlation")
    for target in target_cols:
        label = TARGET_LABELS.get(target, target)
        subset = corr_long[(corr_long["target_column"] == target) & (corr_long["method"] == "Spearman")].head(8)
        lines.append(f"   Target: {label}")
        for _, row in subset.iterrows():
            lines.append(
                f"      rank {int(row['abs_correlation_rank']):2d}: {row['descriptor_label']} "
                f"rho={row['coefficient']:.3f}, p_FDR={row['p_value_fdr_bh']:.3e}"
            )
    lines.append("")
    lines.append("9. Interpretation")
    lines.append("   Positive correlations with EFA indicate chemistry descriptors that increase with entropy-forming ability.")
    lines.append("   The heatmap focuses on chemically interpretable descriptors: VEC, Ghosh electronegativity mismatch,")
    lines.append("   Ghosh and Pauling/periodic-table radius mismatch, and the corresponding Λ parameters.")
    lines.append("")
    lines.append("10. Output files")
    lines.append(f"   Excel workbook: {out_xlsx}")
    lines.append(f"   TXT report:     {out_txt}")
    out_txt.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "script": Path(__file__).name,
        "input": str(input_path),
        "sheet": args.sheet,
        "outputs": {"excel": str(out_xlsx), "txt": str(out_txt)},
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Done. Outputs written to:")
    print(f"  Excel: {out_xlsx}")
    print(f"  TXT:   {out_txt}")


if __name__ == "__main__":
    main()
