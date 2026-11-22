#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze correlations between EFA and lattice-distortion descriptors in the
CHAOS database.

Outputs
-------
1. Excel workbook with:
   - Plot_Data_Raw
   - Correlation_Long
   - Heatmap_Pearson
   - Heatmap_Spearman
   - Summary_Statistics
   - Config
2. TXT report describing the calculation process and key results.

This script uses only EFA and the five lattice-distortion descriptors.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats


DESCRIPTOR_MAP = {
    "lat_distortion_misfit_mean": r"$\bar{\epsilon}$",
    "lat_distortion_misfit_stdev": r"$\sigma_{\epsilon}$",
    "lat_distortion_relax_distance_mean": r"$\bar{d}$",
    "lat_distortion_relax_distance_stdev": r"$\sigma_d$",
    "solubility_parameter": r"$\delta_s$",
}

TARGET_MAP = {
    "EFA": "EFA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze EFA vs lattice-distortion descriptor correlations."
    )
    parser.add_argument("--input", required=True, help="Input Excel workbook")
    parser.add_argument("--sheet", default="combined", help="Input sheet name")
    parser.add_argument("--outdir", default="efa_lattice_descriptor_correlation_outputs", help="Output directory")
    parser.add_argument("--efa-col", default="EFA", help="EFA column name")
    parser.add_argument(
        "--descriptor-cols",
        nargs="*",
        default=list(DESCRIPTOR_MAP.keys()),
        help="Lattice-distortion descriptor columns",
    )
    return parser.parse_args()


def check_columns(df: pd.DataFrame, columns: List[str]) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def calc_corr(x: pd.Series, y: pd.Series, method: str) -> Dict[str, float]:
    temp = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    n = len(temp)
    if n < 3:
        return {"N": n, "coefficient": np.nan, "p_value": np.nan}

    if method == "Pearson":
        res = stats.pearsonr(temp["x"], temp["y"])
    elif method == "Spearman":
        res = stats.spearmanr(temp["x"], temp["y"])
    else:
        raise ValueError("method must be Pearson or Spearman")

    return {"N": int(n), "coefficient": float(res.statistic), "p_value": float(res.pvalue)}


def summary_stats(s: pd.Series, name: str) -> Dict[str, float]:
    x = pd.to_numeric(s, errors="coerce").dropna()
    return {
        "variable": name,
        "N": int(len(x)),
        "mean": float(x.mean()),
        "std": float(x.std(ddof=1)),
        "min": float(x.min()),
        "q25": float(x.quantile(0.25)),
        "median": float(x.median()),
        "q75": float(x.quantile(0.75)),
        "max": float(x.max()),
    }


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_excel(input_path, sheet_name=args.sheet)
    required = [args.efa_col] + args.descriptor_cols
    check_columns(df, required)

    data = df.copy()
    for col in required:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    # Keep rows with EFA available; descriptors can still be pairwise complete.
    data = data.dropna(subset=[args.efa_col]).reset_index(drop=True)
    data["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(len(data))]

    if {"Metal1", "Metal2", "Metal3", "Metal4"}.issubset(df.columns):
        fam_cols = ["Metal1", "Metal2", "Metal3", "Metal4"]
        def make_family(row):
            vals = [str(row[c]).strip() for c in fam_cols if pd.notna(row[c]) and str(row[c]).strip().lower() != "nan"]
            return "-".join(sorted(vals)) if vals else "unknown_family"
        data["compositional_family"] = data.apply(make_family, axis=1)
    else:
        data["compositional_family"] = "unknown_family"

    # Plot-data sheet (raw numeric values used in calculations)
    plot_cols = ["anonymous_id", "compositional_family", args.efa_col] + args.descriptor_cols
    plot_data = data[plot_cols].copy()

    # Long-form correlations
    records = []
    targets = [(args.efa_col, TARGET_MAP.get(args.efa_col, args.efa_col))]
    for target_col, target_label in targets:
        for desc_col in args.descriptor_cols:
            desc_label = DESCRIPTOR_MAP.get(desc_col, desc_col)
            for method in ["Pearson", "Spearman"]:
                result = calc_corr(data[target_col], data[desc_col], method)
                records.append(
                    {
                        "target_column": target_col,
                        "target_label": target_label,
                        "descriptor_column": desc_col,
                        "descriptor_label": desc_label,
                        "method": method,
                        "N": result["N"],
                        "coefficient": result["coefficient"],
                        "p_value": result["p_value"],
                    }
                )
    corr_long = pd.DataFrame(records)

    # Wide matrices for heatmaps
    pearson = corr_long[corr_long["method"] == "Pearson"].pivot(
        index="target_label", columns="descriptor_label", values="coefficient"
    )
    spearman = corr_long[corr_long["method"] == "Spearman"].pivot(
        index="target_label", columns="descriptor_label", values="coefficient"
    )

    # Enforce manuscript order
    col_order = [DESCRIPTOR_MAP[c] for c in args.descriptor_cols]
    row_order = [TARGET_MAP.get(args.efa_col, args.efa_col)]
    pearson = pearson.reindex(index=row_order, columns=col_order)
    spearman = spearman.reindex(index=row_order, columns=col_order)

    summary = pd.DataFrame(
        [summary_stats(data[args.efa_col], args.efa_col)]
        + [summary_stats(data[c], c) for c in args.descriptor_cols]
    )

    config = pd.DataFrame(
        [
            {"parameter": "input_workbook", "value": str(input_path)},
            {"parameter": "sheet", "value": args.sheet},
            {"parameter": "rows_used", "value": len(data)},
            {"parameter": "EFA_column", "value": args.efa_col},
            {"parameter": "descriptor_columns", "value": ", ".join(args.descriptor_cols)},
            {"parameter": "methods", "value": "Pearson and Spearman"},
        ]
    )

    out_xlsx = outdir / "efa_lattice_descriptor_correlations.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        plot_data.to_excel(writer, sheet_name="Plot_Data_Raw", index=False)
        corr_long.to_excel(writer, sheet_name="Correlation_Long", index=False)
        pearson.to_excel(writer, sheet_name="Heatmap_Pearson")
        spearman.to_excel(writer, sheet_name="Heatmap_Spearman")
        summary.to_excel(writer, sheet_name="Summary_Statistics", index=False)
        config.to_excel(writer, sheet_name="Config", index=False)

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "border": 1})
        num_fmt = workbook.add_format({"num_format": "0.000"})
        sci_fmt = workbook.add_format({"num_format": "0.000E+00"})
        for sheet_name, df_sheet in [
            ("Plot_Data_Raw", plot_data),
            ("Correlation_Long", corr_long),
            ("Summary_Statistics", summary),
            ("Config", config),
        ]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            for j, col in enumerate(df_sheet.columns):
                ws.write(0, j, col, header_fmt)
                width = max(14, min(36, len(str(col)) + 4))
                if col in ["coefficient"]:
                    ws.set_column(j, j, width, num_fmt)
                elif col in ["p_value"]:
                    ws.set_column(j, j, width, sci_fmt)
                else:
                    ws.set_column(j, j, width)

    out_txt = outdir / "efa_lattice_descriptor_correlation_report.txt"
    lines = []
    lines.append("EFA vs lattice-distortion descriptors: calculation report")
    lines.append("=" * 78)
    lines.append("")
    lines.append("1. Purpose")
    lines.append("   This analysis quantifies the relationship between EFA and the lattice-distortion")
    lines.append("   descriptors used in the CHAOS manuscript.")
    lines.append("   Only EFA and the five lattice-distortion descriptors were used.")
    lines.append("")
    lines.append("2. Variables")
    lines.append(f"   Target: {args.efa_col}  -> figure label: EFA")
    for c in args.descriptor_cols:
        lines.append(f"   Descriptor: {c} -> figure label: {DESCRIPTOR_MAP.get(c, c)}")
    lines.append("")
    lines.append("3. Calculation procedure")
    lines.append("   a) Read the input workbook and the specified sheet.")
    lines.append("   b) Convert EFA and the five descriptor columns to numeric values.")
    lines.append("   c) Drop rows with missing EFA.")
    lines.append("   d) For each EFA–descriptor pair, compute:")
    lines.append("      - Pearson correlation coefficient and p-value")
    lines.append("      - Spearman correlation coefficient and p-value")
    lines.append("      Pairwise complete observations are used for each correlation.")
    lines.append("   e) Store the raw plot data and the correlation matrices in an Excel workbook.")
    lines.append("   f) Use the resulting Heatmap_Pearson and Heatmap_Spearman sheets to create the figure.")
    lines.append("")
    lines.append(f"4. Rows used in the analysis: {len(data)}")
    lines.append("")
    lines.append("5. Summary statistics")
    lines.append(summary.to_string(index=False))
    lines.append("")
    lines.append("6. Pearson correlations")
    lines.append(pearson.to_string())
    lines.append("")
    lines.append("7. Spearman correlations")
    lines.append(spearman.to_string())
    lines.append("")
    lines.append("8. Interpretation")
    lines.append("   Negative EFA correlations mean that larger lattice distortion is associated with")
    lines.append("   lower entropy-forming ability. Because EFA can be skewed, the manuscript can")
    lines.append("   emphasize the Spearman heatmap in the main text,")
    lines.append("   while keeping Pearson as supporting information.")
    lines.append("")
    lines.append("9. Output files")
    lines.append(f"   Excel workbook: {out_xlsx}")
    lines.append(f"   TXT report:     {out_txt}")
    out_txt.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "script": Path(__file__).name,
        "input": str(input_path),
        "sheet": args.sheet,
        "outputs": {
            "excel": str(out_xlsx),
            "txt": str(out_txt),
        },
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Done. Excel: {out_xlsx}")
    print(f"Done. TXT:   {out_txt}")


if __name__ == "__main__":
    main()
