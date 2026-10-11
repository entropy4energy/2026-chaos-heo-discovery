#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figure 6a analysis: descriptor compatibility score vs EFA percentile.

This script builds a 2D percentile-ranked map whose x-axis is a descriptor-only
CHAOS compatibility score and whose y-axis is EFA percentile.

Important:
- EFA is used only to calculate the y-axis percentile and high-EFA class.
- The x-axis is constructed only from CHAOS distortion and chemistry descriptors.

Outputs
-------
1. TXT report explaining the calculation.
2. Excel workbook containing plot data and OriginPro 2024-friendly worksheets.

Recommended command
-------------------
python 01_analyze_fig6a_descriptor_compatibility_vs_efa.py \
    --input locked_493.xlsx \
    --sheet combined \
    --outdir fig6a_descriptor_compatibility_vs_efa_outputs

Publication-safe option
-----------------------
If you only want to plot entries approved for public EFA release, provide a
release-decision workbook and enable --public-only:

python 01_analyze_fig6a_descriptor_compatibility_vs_efa.py \
    --input locked_493.xlsx \
    --sheet combined \
    --release CHAOS_EFA_public_release_decisions_20260623.xlsx \
    --public-only \
    --outdir fig6a_descriptor_compatibility_vs_efa_outputs_public
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats


# -----------------------------
# Default descriptor definitions
# -----------------------------
DISTORTION_DESCRIPTOR_COLS = [
    "lat_distortion_misfit_mean",          # epsilon_bar
    "lat_distortion_relax_distance_mean", # d_bar
]

CHEMISTRY_DESCRIPTOR_COLS = [
    "delta_radii_Ghosh08",                # lower is more compatible
    "delta_electronegativity_Ghosh",      # lower is more compatible
    "param_geo_radii_Ghosh08",            # higher is more compatible
    "VEC",                                # higher is used as favorable screening axis
]

# Direction = +1 means high raw value is favorable; -1 means low raw value is favorable.
DESCRIPTOR_DIRECTIONS = {
    "lat_distortion_misfit_mean": -1,
    "lat_distortion_relax_distance_mean": -1,
    "delta_radii_Ghosh08": -1,
    "delta_electronegativity_Ghosh": -1,
    "param_geo_radii_Ghosh08": +1,
    "VEC": +1,
}

DESCRIPTOR_LABELS = {
    "lat_distortion_misfit_mean": r"1-P(epsilon_bar)",
    "lat_distortion_relax_distance_mean": r"1-P(d_bar)",
    "delta_radii_Ghosh08": r"1-P(delta_r_Ghosh)",
    "delta_electronegativity_Ghosh": r"1-P(delta_chi_Ghosh)",
    "param_geo_radii_Ghosh08": r"P(Lambda_Ghosh)",
    "VEC": r"P(VEC)",
}

CLASS_ORDER = [
    "high-EFA + high descriptor compatibility",
    "high-EFA only",
    "high descriptor compatibility only",
    "other",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze Figure 6a descriptor compatibility score vs EFA percentile."
    )
    parser.add_argument("--input", required=True, help="Input CHAOS Excel workbook")
    parser.add_argument("--sheet", default="combined", help="Input sheet name")
    parser.add_argument("--outdir", default="fig6a_descriptor_compatibility_vs_efa_outputs", help="Output directory")
    parser.add_argument("--efa-col", default="EFA", help="EFA column name")
    parser.add_argument("--name-col", default="name", help="Formula/name column")
    parser.add_argument("--release", default=None, help="Optional EFA public-release decision workbook")
    parser.add_argument("--public-only", action="store_true", help="Only include rows approved for public EFA release")
    parser.add_argument("--efa-threshold", type=float, default=0.50, help="High-EFA threshold on percentile axis")
    parser.add_argument("--score-threshold", type=float, default=0.50, help="High descriptor-compatibility threshold")
    parser.add_argument("--distortion-weight", type=float, default=0.50, help="Weight for distortion component")
    parser.add_argument("--chemistry-weight", type=float, default=0.50, help="Weight for chemistry component")
    parser.add_argument(
        "--include-raw-efa-in-internal-sheet",
        action="store_true",
        help="Include raw EFA in an internal sheet. Default is off to avoid accidental release.",
    )
    return parser.parse_args()


def check_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}\nAvailable columns: {list(df.columns)}")


def percentile_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """Return percentile ranks scaled to [0, 1]. Ties use average ranks."""
    s = pd.to_numeric(series, errors="coerce")
    out = pd.Series(np.nan, index=s.index, dtype=float)
    valid = s.dropna()
    n = len(valid)
    if n == 0:
        return out
    if n == 1:
        out.loc[valid.index] = 0.5
        return out
    ranks = valid.rank(method="average", ascending=ascending)
    out.loc[valid.index] = (ranks - 1) / (n - 1)
    return out


def parse_formula_to_cation_set(formula: str) -> Tuple[str, ...]:
    """Extract a sorted cation tuple from a formula-like string.

    This is intentionally simple and robust for strings such as:
    (Co,Cu,Mg,Ni,Zn)O, CoCuMgNiZnO, Li0.3(Co,Cu,Mg,Mn,Zn)O.
    We remove common anions and Li dopant from the returned cation set.
    """
    if formula is None or (isinstance(formula, float) and np.isnan(formula)):
        return tuple()
    text = str(formula)
    elements = re.findall(r"[A-Z][a-z]?", text)
    exclude = {"O", "F", "N", "C", "B", "Li"}
    cations = sorted({e for e in elements if e not in exclude})
    return tuple(cations)


def cation_key(cations: Tuple[str, ...]) -> str:
    return "-".join(cations) if cations else "unknown"


def read_public_release_keys(path: Optional[str]) -> set:
    """Read exact CHAOS row identities approved for public EFA release.

    The function accepts the workbook created in previous steps. It tries common
    sheet/column names and returns a set of CHAOS_excel_row values when available;
    otherwise it returns candidate cation keys.
    """
    if not path:
        return set()
    release_path = Path(path)
    if not release_path.exists():
        raise FileNotFoundError(f"Release workbook not found: {release_path}")

    xl = pd.ExcelFile(release_path)
    # Prefer the dedicated public release sheet if present.
    preferred_sheets = ["Public_EFA_Release", "All_Release_Decisions", "Release_Decisions"]
    sheet_name = next((s for s in preferred_sheets if s in xl.sheet_names), xl.sheet_names[0])
    rdf = pd.read_excel(release_path, sheet_name=sheet_name)

    # Filter rows if a decision column exists.
    decision_cols = [c for c in rdf.columns if "decision" in c.lower() or "publish" in c.lower() or "release" in c.lower()]
    if decision_cols:
        col = decision_cols[0]
        mask = rdf[col].astype(str).str.lower().str.contains("publish|public|yes|release", regex=True)
        rdf = rdf[mask].copy()

    # Prefer row number identifiers.
    row_cols = [c for c in rdf.columns if c.lower() in {"chaos_excel_row", "efa_original_row", "excel_row"}]
    if row_cols:
        return set(pd.to_numeric(rdf[row_cols[0]], errors="coerce").dropna().astype(int).tolist())

    # Fall back to cation-set keys.
    formula_cols = [c for c in rdf.columns if any(k in c.lower() for k in ["formula", "candidate", "composition", "name"])]
    keys = set()
    if formula_cols:
        for val in rdf[formula_cols[0]].dropna():
            keys.add(cation_key(parse_formula_to_cation_set(str(val))))
    return keys


def classify(row: pd.Series, efa_threshold: float, score_threshold: float) -> str:
    high_efa = row["EFA_percentile"] >= efa_threshold
    high_score = row["CHAOS_descriptor_compatibility_score"] >= score_threshold
    if high_efa and high_score:
        return "high-EFA + high descriptor compatibility"
    if high_efa and not high_score:
        return "high-EFA only"
    if (not high_efa) and high_score:
        return "high descriptor compatibility only"
    return "other"


def pad_columns_by_class(plot_df: pd.DataFrame, x_col: str, y_col: str, class_col: str) -> pd.DataFrame:
    """Create an OriginPro-friendly wide table with X/Y pairs for each class."""
    class_frames = []
    max_len = 0
    for cls in CLASS_ORDER:
        sub = plot_df.loc[plot_df[class_col] == cls, [x_col, y_col]].reset_index(drop=True)
        sub.columns = [f"X_{cls}", f"Y_{cls}"]
        class_frames.append(sub)
        max_len = max(max_len, len(sub))
    padded = []
    for sub in class_frames:
        sub = sub.reindex(range(max_len))
        padded.append(sub)
    return pd.concat(padded, axis=1)


def safe_corr(x: pd.Series, y: pd.Series) -> Dict[str, float]:
    temp = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(temp) < 3:
        return {"N": len(temp), "pearson_r": np.nan, "pearson_p": np.nan, "spearman_rho": np.nan, "spearman_p": np.nan}
    pearson = stats.pearsonr(temp["x"], temp["y"])
    spearman = stats.spearmanr(temp["x"], temp["y"])
    return {
        "N": int(len(temp)),
        "pearson_r": float(pearson.statistic),
        "pearson_p": float(pearson.pvalue),
        "spearman_rho": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
    }


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    df = pd.read_excel(input_path, sheet_name=args.sheet)
    df = df.replace([np.inf, -np.inf], np.nan)

    required = [args.efa_col, args.name_col] + DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS
    check_columns(df, required)

    # Preserve original Excel row numbers: header is row 1, first data row is row 2.
    df = df.reset_index(drop=False).rename(columns={"index": "zero_based_index"})
    df["CHAOS_excel_row"] = df["zero_based_index"] + 2
    df["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(len(df))]
    df["cation_set"] = df[args.name_col].apply(lambda x: cation_key(parse_formula_to_cation_set(x)))

    # Optional public-only filter.
    public_keys = read_public_release_keys(args.release) if args.release else set()
    if args.public_only:
        if not public_keys:
            raise ValueError("--public-only was requested, but no public release keys could be read. Provide --release.")
        row_key_mask = df["CHAOS_excel_row"].isin(public_keys)
        cation_key_mask = df["cation_set"].isin(public_keys)
        df = df[row_key_mask | cation_key_mask].copy()

    # Convert numeric columns.
    numeric_cols = [args.efa_col] + DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with missing EFA or score descriptors.
    data = df.dropna(subset=numeric_cols).copy()

    # EFA percentile: high is favorable.
    data["EFA_percentile"] = percentile_rank(data[args.efa_col], ascending=True)

    # Component percentiles and compatibility transforms.
    for col in DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS:
        p_col = f"P_{col}"
        c_col = f"compat_{col}"
        data[p_col] = percentile_rank(data[col], ascending=True)
        direction = DESCRIPTOR_DIRECTIONS[col]
        data[c_col] = data[p_col] if direction > 0 else 1.0 - data[p_col]

    data["distortion_compatibility_score"] = data[[f"compat_{c}" for c in DISTORTION_DESCRIPTOR_COLS]].mean(axis=1)
    data["chemistry_compatibility_score"] = data[[f"compat_{c}" for c in CHEMISTRY_DESCRIPTOR_COLS]].mean(axis=1)

    weight_sum = args.distortion_weight + args.chemistry_weight
    if weight_sum <= 0:
        raise ValueError("The sum of distortion and chemistry weights must be positive.")
    wd = args.distortion_weight / weight_sum
    wc = args.chemistry_weight / weight_sum
    data["CHAOS_descriptor_compatibility_score"] = (
        wd * data["distortion_compatibility_score"] + wc * data["chemistry_compatibility_score"]
    )

    data["true_class"] = data.apply(lambda r: classify(r, args.efa_threshold, args.score_threshold), axis=1)
    data["is_high_EFA"] = data["EFA_percentile"] >= args.efa_threshold
    data["is_high_descriptor_compatibility"] = data["CHAOS_descriptor_compatibility_score"] >= args.score_threshold

    corr = safe_corr(data["CHAOS_descriptor_compatibility_score"], data["EFA_percentile"])
    class_counts = data["true_class"].value_counts().reindex(CLASS_ORDER).fillna(0).astype(int).reset_index()
    class_counts.columns = ["true_class", "count"]
    class_counts["fraction"] = class_counts["count"] / len(data)

    # Public plot table: no raw EFA by default.
    plot_cols = [
        "anonymous_id",
        "CHAOS_excel_row",
        args.name_col,
        "cation_set",
        "CHAOS_descriptor_compatibility_score",
        "EFA_percentile",
        "distortion_compatibility_score",
        "chemistry_compatibility_score",
        "true_class",
        "is_high_EFA",
        "is_high_descriptor_compatibility",
    ] + [f"compat_{c}" for c in DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS]
    plot_df = data[plot_cols].copy()

    # Rename for readability.
    rename_map = {
        args.name_col: "CHAOS_formula",
        "CHAOS_descriptor_compatibility_score": "X_CHAOS_descriptor_compatibility_score",
        "EFA_percentile": "Y_EFA_percentile",
        "lat_distortion_misfit_mean": "epsilon_bar",
        "lat_distortion_relax_distance_mean": "d_bar",
    }
    plot_df = plot_df.rename(columns=rename_map)

    origin_xy = plot_df[[
        "X_CHAOS_descriptor_compatibility_score",
        "Y_EFA_percentile",
        "true_class",
        "anonymous_id",
        "CHAOS_formula",
        "CHAOS_excel_row",
        "cation_set",
    ]].copy()

    origin_by_class = pad_columns_by_class(
        plot_df,
        "X_CHAOS_descriptor_compatibility_score",
        "Y_EFA_percentile",
        "true_class",
    )

    origin_thresholds = pd.DataFrame({
        "line_type": ["vertical_score_threshold", "horizontal_EFA_threshold"],
        "x1": [args.score_threshold, 0.0],
        "x2": [args.score_threshold, 1.0],
        "y1": [0.0, args.efa_threshold],
        "y2": [1.0, args.efa_threshold],
    })

    score_definition = pd.DataFrame([
        {"item": "EFA_percentile", "definition": "rank(EFA) scaled to [0, 1]; larger means higher entropy-forming ability"},
        {"item": "S_distortion", "definition": "mean[1-P(epsilon_bar), 1-P(d_bar)]"},
        {"item": "S_chemistry", "definition": "mean[1-P(delta_r_Ghosh), 1-P(delta_chi_Ghosh), P(Lambda_Ghosh), P(VEC)]"},
        {"item": "S_CHAOS", "definition": f"{wd:.3f}*S_distortion + {wc:.3f}*S_chemistry"},
        {"item": "high-EFA threshold", "definition": f"EFA_percentile >= {args.efa_threshold}"},
        {"item": "high descriptor compatibility threshold", "definition": f"S_CHAOS >= {args.score_threshold}"},
    ])

    component_score_cols = [
        "anonymous_id", "CHAOS_excel_row", args.name_col, "cation_set",
        args.efa_col, "EFA_percentile",
        "CHAOS_descriptor_compatibility_score", "distortion_compatibility_score", "chemistry_compatibility_score",
    ] + [f"P_{c}" for c in DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS] + [f"compat_{c}" for c in DISTORTION_DESCRIPTOR_COLS + CHEMISTRY_DESCRIPTOR_COLS]
    component_scores = data[component_score_cols].copy()
    if not args.include_raw_efa_in_internal_sheet:
        component_scores = component_scores.drop(columns=[args.efa_col])

    summary = pd.DataFrame([
        {"metric": "input_workbook", "value": str(input_path)},
        {"metric": "sheet", "value": args.sheet},
        {"metric": "rows_in_input", "value": len(df) if not args.public_only else "filtered by public release"},
        {"metric": "rows_used", "value": len(data)},
        {"metric": "public_only", "value": bool(args.public_only)},
        {"metric": "x_axis", "value": "CHAOS descriptor compatibility score"},
        {"metric": "y_axis", "value": "EFA percentile"},
        {"metric": "Pearson r(S_CHAOS, EFA percentile)", "value": corr["pearson_r"]},
        {"metric": "Pearson p-value", "value": corr["pearson_p"]},
        {"metric": "Spearman rho(S_CHAOS, EFA percentile)", "value": corr["spearman_rho"]},
        {"metric": "Spearman p-value", "value": corr["spearman_p"]},
    ])

    out_xlsx = outdir / "fig6a_descriptor_compatibility_vs_efa_analysis.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        score_definition.to_excel(writer, sheet_name="Score_Definition", index=False)
        class_counts.to_excel(writer, sheet_name="Class_Counts", index=False)
        plot_df.to_excel(writer, sheet_name="Plot_Data", index=False)
        origin_xy.to_excel(writer, sheet_name="OriginPro_XY", index=False)
        origin_by_class.to_excel(writer, sheet_name="OriginPro_By_Class", index=False)
        origin_thresholds.to_excel(writer, sheet_name="OriginPro_Thresholds", index=False)
        component_scores.to_excel(writer, sheet_name="Component_Scores", index=False)

        workbook = writer.book
        header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": "#1F4E79", "border": 1})
        pct_fmt = workbook.add_format({"num_format": "0.000"})
        sci_fmt = workbook.add_format({"num_format": "0.00E+00"})
        text_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
        for sheet_name, df_sheet in [
            ("Summary", summary),
            ("Score_Definition", score_definition),
            ("Class_Counts", class_counts),
            ("Plot_Data", plot_df),
            ("OriginPro_XY", origin_xy),
            ("OriginPro_By_Class", origin_by_class),
            ("OriginPro_Thresholds", origin_thresholds),
            ("Component_Scores", component_scores),
        ]:
            ws = writer.sheets[sheet_name]
            ws.freeze_panes(1, 0)
            for j, col in enumerate(df_sheet.columns):
                ws.write(0, j, col, header_fmt)
                width = max(12, min(38, len(str(col)) + 4))
                if any(k in str(col).lower() for k in ["percentile", "score", "fraction", "x_", "y_", "compat", "p_"]):
                    ws.set_column(j, j, width, pct_fmt)
                elif "p-value" in str(col).lower() or "p_value" in str(col).lower():
                    ws.set_column(j, j, width, sci_fmt)
                elif str(col).lower() in ["definition", "value"]:
                    ws.set_column(j, j, min(60, max(width, 30)), text_fmt)
                else:
                    ws.set_column(j, j, width)

    out_txt = outdir / "fig6a_descriptor_compatibility_vs_efa_report.txt"
    lines = []
    lines.append("Figure 6a: descriptor compatibility score vs EFA percentile")
    lines.append("=" * 78)
    lines.append("")
    lines.append("1. Purpose")
    lines.append("   This analysis builds a 2D map using a descriptor-only CHAOS compatibility")
    lines.append("   score on the x-axis")
    lines.append("   and EFA percentile on the y-axis.")
    lines.append("")
    lines.append("2. Data source")
    lines.append(f"   Input workbook: {input_path}")
    lines.append(f"   Sheet: {args.sheet}")
    lines.append(f"   Rows used: {len(data)}")
    lines.append(f"   Public-only mode: {args.public_only}")
    lines.append("")
    lines.append("3. Axes")
    lines.append("   y-axis: EFA_percentile = rank(EFA) scaled to [0, 1].")
    lines.append("   x-axis: S_CHAOS, a descriptor-only compatibility score.")
    lines.append("")
    lines.append("4. Descriptor score definition")
    lines.append("   S_distortion = mean[1-P(epsilon_bar), 1-P(d_bar)]")
    lines.append("   S_chemistry  = mean[1-P(delta_r_Ghosh), 1-P(delta_chi_Ghosh), P(Lambda_Ghosh), P(VEC)]")
    lines.append(f"   S_CHAOS = {wd:.3f}*S_distortion + {wc:.3f}*S_chemistry")
    lines.append("   Larger S_CHAOS means lower relaxation-induced distortion, lower chemical mismatch,")
    lines.append("   higher entropy-to-mismatch parameter, and higher VEC.")
    lines.append("")
    lines.append("5. Excluded quantities")
    lines.append("   EFA is used only for the y-axis percentile and high-EFA class labels.")
    lines.append("")
    lines.append("6. Correlation between x-axis and y-axis")
    lines.append(f"   Pearson r = {corr['pearson_r']:.4f}, p = {corr['pearson_p']:.3e}")
    lines.append(f"   Spearman rho = {corr['spearman_rho']:.4f}, p = {corr['spearman_p']:.3e}")
    lines.append("")
    lines.append("7. Quadrant/class counts")
    lines.append(class_counts.to_string(index=False))
    lines.append("")
    lines.append("8. Output files")
    lines.append(f"   Excel workbook: {out_xlsx}")
    lines.append(f"   TXT report:     {out_txt}")
    lines.append("")
    lines.append("9. Suggested interpretation")
    lines.append("   The figure is a percentile-ranked 2D map with an independent descriptor-only")
    lines.append("   compatibility score on the x-axis.")
    lines.append("   The upper-right region corresponds to entries that are both high-EFA and")
    lines.append("   structurally/chemically compatible according to CHAOS descriptors.")
    out_txt.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "script": Path(__file__).name,
        "input": str(input_path),
        "sheet": args.sheet,
        "outputs": {"excel": str(out_xlsx), "report": str(out_txt)},
        "raw_efa_in_public_plot_data": False,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Done. Excel: {out_xlsx}")
    print(f"Done. TXT:   {out_txt}")


if __name__ == "__main__":
    main()
