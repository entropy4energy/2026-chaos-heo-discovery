#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EFA quartile-class analysis for CHAOS.

Purpose
-------
This script compares structural and chemistry descriptors across
EFA quartiles: Q1 = low EFA, Q4 = high EFA.

It is designed for manuscript figures that hide raw EFA values.
The public plot-data sheet contains percentile-ranked descriptor values and
anonymous IDs; raw descriptor values are kept in an internal sheet.

Outputs
-------
- Main Excel workbook containing public plot data, raw internal data, quartile summaries,
  and trend tests.
- Additional OriginPro-ready Excel workbook containing one worksheet for each subplot.
- TXT report explaining the calculation workflow and key numerical trends.

This analysis uses EFA and the listed descriptors only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats

# Local-compatible Excel output. Requires openpyxl, which is also used by pandas to read .xlsx files.
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


LABELS = {
    "EFA": "EFA",
    "lat_distortion_misfit_mean": r"$\bar{\epsilon}$",
    "lat_distortion_relax_distance_mean": r"$\bar{d}$",
    "VEC": "VEC",
    "delta_radii_Ghosh08": r"$\delta r_{\mathrm{Ghosh}}$",
    "param_geo_radii_Ghosh08": r"$\Lambda_{\mathrm{Ghosh}}$",
    "delta_electronegativity_Ghosh": r"$\delta\chi_{\mathrm{Ghosh}}$",
}

DEFAULT_EFA_QUARTILE_DESCRIPTORS = [
    "lat_distortion_misfit_mean",
    "lat_distortion_relax_distance_mean",
    "VEC",
    "delta_radii_Ghosh08",
    "param_geo_radii_Ghosh08",
    "delta_electronegativity_Ghosh",
]

EFA_QUARTILE_DEFINITION = {
    "Q1": "low EFA",
    "Q2": "intermediate-low EFA",
    "Q3": "intermediate-high EFA",
    "Q4": "high EFA",
}


# Short names used for OriginPro worksheet names. Each worksheet corresponds to one subplot.
ORIGIN_DESCRIPTOR_SHORT = {
    "EFA": "EFA",
    "lat_distortion_misfit_mean": "epsilon_bar",
    "lat_distortion_relax_distance_mean": "d_bar",
    "VEC": "VEC",
    "delta_radii_Ghosh08": "delta_r_Ghosh",
    "param_geo_radii_Ghosh08": "Lambda_Ghosh",
    "delta_electronegativity_Ghosh": "delta_chi_Ghosh",
}

ORIGIN_EFA_QUARTILE_HEADERS = {
    "Q1": "Q1_low_EFA",
    "Q2": "Q2_int_low_EFA",
    "Q3": "Q3_int_high_EFA",
    "Q4": "Q4_high_EFA",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze EFA quartile trends in CHAOS descriptors.")
    parser.add_argument("--input", required=True, help="Input Excel workbook, e.g. locked_493.xlsx")
    parser.add_argument("--sheet", default="combined", help="Input sheet name. Default: combined")
    parser.add_argument("--outdir", default="efa_quartile_outputs", help="Output directory")
    parser.add_argument("--efa-col", default="EFA", help="EFA column name. Default: EFA")
    parser.add_argument(
        "--family-cols",
        nargs="*",
        default=["Metal1", "Metal2", "Metal3", "Metal4"],
        help="Columns used to define compositional family. Default: Metal1 Metal2 Metal3 Metal4",
    )
    parser.add_argument(
        "--efa-descriptors",
        nargs="*",
        default=DEFAULT_EFA_QUARTILE_DESCRIPTORS,
        help="Descriptors compared across EFA quartiles.",
    )
    return parser.parse_args()


def check_columns(df: pd.DataFrame, required: Iterable[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Available columns: {list(df.columns)}")


def percentile_rank(series: pd.Series) -> pd.Series:
    """Return percentile ranks scaled to [0, 1] using average ranks for ties."""
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


def quartile_from_percentile(p: pd.Series) -> pd.Series:
    labels = []
    for v in p:
        if pd.isna(v):
            labels.append(np.nan)
        elif v < 0.25:
            labels.append("Q1")
        elif v < 0.50:
            labels.append("Q2")
        elif v < 0.75:
            labels.append("Q3")
        else:
            labels.append("Q4")
    return pd.Series(labels, index=p.index)


def make_family(row: pd.Series, family_cols: List[str]) -> str:
    metals = []
    for c in family_cols:
        if c in row.index and pd.notna(row[c]):
            val = str(row[c]).strip()
            if val and val.lower() != "nan":
                metals.append(val)
    return "-".join(sorted(metals)) if metals else "unknown_family"


def clean_value(v):
    """Convert pandas/numpy scalar values into JSON-serializable workbook values."""
    if pd.isna(v):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def df_to_matrix(df: pd.DataFrame) -> List[List[object]]:
    rows = [list(df.columns)]
    for _, row in df.iterrows():
        rows.append([clean_value(x) for x in row.tolist()])
    return rows


def write_excel_workbook(out_xlsx: Path, sheets: Dict[str, pd.DataFrame]) -> None:
    """Write multiple dataframes to an Excel workbook without artifact_tool.

    This version is local-machine friendly and only needs pandas + openpyxl.
    It preserves the same sheet names expected by the plotting script.
    """
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)

        # Basic formatting for readability.
        header_fill = PatternFill(fill_type="solid", fgColor="1F4E79")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        text_alignment = Alignment(vertical="top", wrap_text=True)

        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31]
            ws = writer.book[safe_name]
            ws.freeze_panes = "A2"

            # Header style
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment

            # Column widths
            for col_idx, col_name in enumerate(df.columns, start=1):
                col_letter = get_column_letter(col_idx)
                width = min(max(len(str(col_name)) + 3, 12), 36)
                lower = str(col_name).lower()
                if any(token in lower for token in ["definition", "description", "label", "family"]):
                    width = min(max(width, 24), 44)
                ws.column_dimensions[col_letter].width = width

            # Light wrapping for text-heavy sheets.
            if len(df) <= 5000:
                for row in ws.iter_rows(min_row=2):
                    for cell in row:
                        if isinstance(cell.value, str) and len(cell.value) > 20:
                            cell.alignment = text_alignment

def summarize_quartiles(long_raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (axis, quartile, desc_col, desc_label), group in long_raw.groupby(
        ["quartile_axis", "quartile", "descriptor_column", "descriptor_label"], dropna=False
    ):
        x = pd.to_numeric(group["raw_value"], errors="coerce").dropna()
        p = pd.to_numeric(group["descriptor_percentile"], errors="coerce").dropna()
        records.append(
            {
                "quartile_axis": axis,
                "quartile": quartile,
                "quartile_order": int(group["quartile_order"].iloc[0]),
                "quartile_definition": str(group["quartile_definition"].iloc[0]),
                "descriptor_column": desc_col,
                "descriptor_label": desc_label,
                "count": int(len(x)),
                "raw_mean": float(x.mean()) if len(x) else np.nan,
                "raw_std": float(x.std(ddof=1)) if len(x) > 1 else np.nan,
                "raw_median": float(x.median()) if len(x) else np.nan,
                "raw_q25": float(x.quantile(0.25)) if len(x) else np.nan,
                "raw_q75": float(x.quantile(0.75)) if len(x) else np.nan,
                "percentile_mean": float(p.mean()) if len(p) else np.nan,
                "percentile_median": float(p.median()) if len(p) else np.nan,
            }
        )
    out = pd.DataFrame(records)
    return out.sort_values(["quartile_axis", "descriptor_column", "quartile_order"]).reset_index(drop=True)


def calc_tests(long_raw: pd.DataFrame) -> pd.DataFrame:
    records = []
    for (axis, desc_col, desc_label), group in long_raw.groupby(["quartile_axis", "descriptor_column", "descriptor_label"]):
        g = group.dropna(subset=["raw_value", "quartile_order"]).copy()
        if len(g) < 3:
            continue

        # Spearman trend vs quartile index.
        spearman = stats.spearmanr(g["quartile_order"], g["raw_value"])
        groups = [
            pd.to_numeric(g.loc[g["quartile"] == q, "raw_value"], errors="coerce").dropna().values
            for q in ["Q1", "Q2", "Q3", "Q4"]
        ]
        if all(len(arr) > 0 for arr in groups):
            kruskal = stats.kruskal(*groups)
        else:
            kruskal = None

        q1 = groups[0]
        q4 = groups[3]
        if len(q1) > 0 and len(q4) > 0:
            mwu = stats.mannwhitneyu(q1, q4, alternative="two-sided")
            q4_minus_q1_mean = float(np.mean(q4) - np.mean(q1))
            q4_minus_q1_median = float(np.median(q4) - np.median(q1))
        else:
            mwu = None
            q4_minus_q1_mean = np.nan
            q4_minus_q1_median = np.nan

        records.append(
            {
                "quartile_axis": axis,
                "descriptor_column": desc_col,
                "descriptor_label": desc_label,
                "N": int(len(g)),
                "spearman_rho_vs_quartile": float(spearman.statistic),
                "spearman_p_value": float(spearman.pvalue),
                "kruskal_H": float(kruskal.statistic) if kruskal is not None else np.nan,
                "kruskal_p_value": float(kruskal.pvalue) if kruskal is not None else np.nan,
                "q4_minus_q1_mean": q4_minus_q1_mean,
                "q4_minus_q1_median": q4_minus_q1_median,
                "q1_vs_q4_mannwhitney_U": float(mwu.statistic) if mwu is not None else np.nan,
                "q1_vs_q4_mannwhitney_p_value": float(mwu.pvalue) if mwu is not None else np.nan,
            }
        )
    return pd.DataFrame(records).sort_values(["quartile_axis", "descriptor_column"]).reset_index(drop=True)


def build_long_tables(data: pd.DataFrame, efa_descriptors: List[str]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    raw_records = []
    public_records = []

    axes = [
        ("EFA quartile", "EFA_quartile", EFA_QUARTILE_DEFINITION, efa_descriptors),
    ]

    for axis_name, quartile_col, definitions, descriptors in axes:
        for desc in descriptors:
            p_col = f"{desc}_percentile"
            for _, row in data.iterrows():
                quartile = row[quartile_col]
                if pd.isna(quartile):
                    continue
                q_order = int(str(quartile).replace("Q", ""))
                base = {
                    "anonymous_id": row["anonymous_id"],
                    "compositional_family": row["compositional_family"],
                    "quartile_axis": axis_name,
                    "quartile": quartile,
                    "quartile_order": q_order,
                    "quartile_definition": definitions.get(quartile, ""),
                    "descriptor_column": desc,
                    "descriptor_label": LABELS.get(desc, desc),
                    "descriptor_percentile": row[p_col],
                }
                public_records.append(base.copy())
                raw = base.copy()
                raw["raw_value"] = row[desc]
                raw_records.append(raw)

    public_df = pd.DataFrame(public_records)
    raw_df = pd.DataFrame(raw_records)
    return public_df, raw_df



def sanitize_sheet_name(name: str, existing: set[str]) -> str:
    """Return a unique Excel sheet name with <=31 characters."""
    bad_chars = ['\\', '/', '*', '?', ':', '[', ']']
    clean = str(name)
    for ch in bad_chars:
        clean = clean.replace(ch, '_')
    clean = clean[:31]
    base = clean
    i = 1
    while clean in existing:
        suffix = f"_{i}"
        clean = (base[: 31 - len(suffix)] + suffix)
        i += 1
    existing.add(clean)
    return clean


def build_originpro_subplot_sheets(raw_plot: pd.DataFrame) -> Tuple[Dict[str, pd.DataFrame], pd.DataFrame]:
    """Create one OriginPro-ready worksheet for every subplot.

    Each subplot worksheet has:
      - Columns A-D: descriptor percentile distributions by quartile.
        These can be directly selected in OriginPro 2024 for violin/box plots.
      - Columns F-I: summary values for overlaying mean/median markers if desired.

    The worksheets intentionally use descriptor percentiles rather than raw values,
    preserving the manuscript strategy of hiding raw EFA values.
    """
    sheets: Dict[str, pd.DataFrame] = {}
    manifest_records = []
    used_names: set[str] = set()

    for axis_name, group in raw_plot.groupby("quartile_axis", sort=False):
        prefix = "EFAq"
        headers = ORIGIN_EFA_QUARTILE_HEADERS

        descriptors_in_axis = list(dict.fromkeys(group["descriptor_column"].tolist()))
        for desc in descriptors_in_axis:
            desc_group = group[group["descriptor_column"] == desc].copy()
            desc_label = desc_group["descriptor_label"].iloc[0] if len(desc_group) else LABELS.get(desc, desc)
            desc_short = ORIGIN_DESCRIPTOR_SHORT.get(desc, desc)
            sheet_name = sanitize_sheet_name(f"{prefix}_{desc_short}", used_names)

            quartile_values = {}
            for q in ["Q1", "Q2", "Q3", "Q4"]:
                vals = pd.to_numeric(
                    desc_group.loc[desc_group["quartile"] == q, "descriptor_percentile"],
                    errors="coerce",
                ).dropna().reset_index(drop=True)
                quartile_values[headers[q]] = vals
            max_len = max((len(v) for v in quartile_values.values()), default=0)
            for key, vals in quartile_values.items():
                quartile_values[key] = vals.reindex(range(max_len))
            sheet_df = pd.DataFrame(quartile_values)

            # Summary block for mean/median overlay. Add blank separator column so Origin users can select A-D easily.
            summary_records = []
            for x, q in enumerate(["Q1", "Q2", "Q3", "Q4"], start=1):
                vals = pd.to_numeric(
                    desc_group.loc[desc_group["quartile"] == q, "descriptor_percentile"],
                    errors="coerce",
                ).dropna()
                summary_records.append(
                    {
                        "Quartile": q,
                        "X_position": x,
                        "Mean_percentile": float(vals.mean()) if len(vals) else np.nan,
                        "Median_percentile": float(vals.median()) if len(vals) else np.nan,
                        "N": int(len(vals)),
                    }
                )
            summary_df = pd.DataFrame(summary_records)

            # Combine distributions and summary side-by-side.
            combined = sheet_df.copy()
            combined[""] = np.nan
            for col in summary_df.columns:
                combined[col] = summary_df[col].reindex(range(max_len))

            sheets[sheet_name] = combined
            manifest_records.append(
                {
                    "worksheet": sheet_name,
                    "quartile_axis": axis_name,
                    "descriptor_column": desc,
                    "descriptor_label": desc_label,
                    "plot_y_values": "descriptor_percentile",
                    "distribution_columns_for_Origin": "A:D",
                    "summary_columns_for_mean_overlay": "F:J",
                    "Q1_N": int(summary_df.loc[summary_df["Quartile"] == "Q1", "N"].iloc[0]),
                    "Q2_N": int(summary_df.loc[summary_df["Quartile"] == "Q2", "N"].iloc[0]),
                    "Q3_N": int(summary_df.loc[summary_df["Quartile"] == "Q3", "N"].iloc[0]),
                    "Q4_N": int(summary_df.loc[summary_df["Quartile"] == "Q4", "N"].iloc[0]),
                }
            )

    manifest_df = pd.DataFrame(manifest_records)
    return sheets, manifest_df


def write_originpro_workbook(out_xlsx: Path, raw_plot: pd.DataFrame) -> None:
    """Write a separate OriginPro-ready Excel workbook with one worksheet per subplot."""
    subplot_sheets, manifest = build_originpro_subplot_sheets(raw_plot)

    readme = pd.DataFrame(
        [
            {"item": "purpose", "description": "One worksheet per quartile-analysis subplot for OriginPro 2024."},
            {"item": "plot columns", "description": "In each subplot worksheet, select columns A-D to draw violin/box plots."},
            {"item": "values", "description": "Columns A-D contain descriptor percentile values, not raw EFA values."},
            {"item": "summary columns", "description": "Columns F-J contain quartile, x-position, mean, median, and N for optional mean/median overlays."},
            {"item": "EFA quartile worksheets", "description": "Sheet names beginning with EFAq_ compare descriptors across EFA Q1-Q4."},
        ]
    )

    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        readme.to_excel(writer, sheet_name="README", index=False)
        manifest.to_excel(writer, sheet_name="Worksheet_Index", index=False)
        for sheet_name, df in subplot_sheets.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)

        header_fill = PatternFill(fill_type="solid", fgColor="1F4E79")
        header_font = Font(bold=True, color="FFFFFF")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        number_format = "0.000"

        for ws in writer.book.worksheets:
            ws.freeze_panes = "A2"
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = header_alignment
            for col_idx in range(1, ws.max_column + 1):
                col_letter = get_column_letter(col_idx)
                header_value = ws.cell(row=1, column=col_idx).value
                if header_value is None:
                    ws.column_dimensions[col_letter].width = 3
                elif str(header_value) in ["Mean_percentile", "Median_percentile"]:
                    ws.column_dimensions[col_letter].width = 18
                    for row_idx in range(2, ws.max_row + 1):
                        ws.cell(row=row_idx, column=col_idx).number_format = number_format
                elif col_idx <= 4 and ws.title not in ["README", "Worksheet_Index"]:
                    ws.column_dimensions[col_letter].width = 22
                    for row_idx in range(2, ws.max_row + 1):
                        ws.cell(row=row_idx, column=col_idx).number_format = number_format
                else:
                    ws.column_dimensions[col_letter].width = min(max(len(str(header_value)) + 3, 12), 42)

def write_report(
    out_txt: Path,
    args: argparse.Namespace,
    n_raw: int,
    n_used: int,
    summary: pd.DataFrame,
    tests: pd.DataFrame,
    outputs: Dict[str, str],
) -> None:
    def get_mean(axis: str, desc: str, q: str) -> float:
        s = summary[
            (summary["quartile_axis"] == axis)
            & (summary["descriptor_column"] == desc)
            & (summary["quartile"] == q)
        ]
        return float(s["raw_mean"].iloc[0]) if len(s) else float("nan")

    def trend(axis: str, desc: str) -> float:
        s = tests[(tests["quartile_axis"] == axis) & (tests["descriptor_column"] == desc)]
        return float(s["spearman_rho_vs_quartile"].iloc[0]) if len(s) else float("nan")

    lines = []
    lines.append("EFA quartile-class analysis: calculation report")
    lines.append("=" * 72)
    lines.append("")
    lines.append("1. Data source")
    lines.append(f"   Input workbook: {args.input}")
    lines.append(f"   Sheet: {args.sheet}")
    lines.append(f"   Raw rows in sheet: {n_raw}")
    lines.append(f"   Rows used after dropping missing/non-numeric EFA: {n_used}")
    lines.append("")
    lines.append("2. Quartile definitions")
    lines.append("   EFA quartile: Q1 = low EFA, Q2 = intermediate-low EFA, Q3 = intermediate-high EFA, Q4 = high EFA.")
    lines.append("   Quartiles are assigned using percentile ranks scaled to [0, 1].")
    lines.append("")
    lines.append("3. Descriptors compared across EFA quartiles")
    for d in args.efa_descriptors:
        lines.append(f"   {d} -> {LABELS.get(d, d)}")
    lines.append("")
    lines.append("4. Key EFA-quartile trends: raw means from Q1 to Q4")
    for desc in args.efa_descriptors:
        lines.append(
            f"   {LABELS.get(desc, desc)}: Q1 mean = {get_mean('EFA quartile', desc, 'Q1'):.6g}; "
            f"Q4 mean = {get_mean('EFA quartile', desc, 'Q4'):.6g}; "
            f"Spearman trend vs quartile = {trend('EFA quartile', desc):.3f}"
        )
    lines.append("")
    lines.append("5. Statistical tests")
    lines.append("   For each descriptor, the Excel workbook reports Spearman correlation against quartile index,")
    lines.append("   Kruskal-Wallis tests across Q1-Q4, and Mann-Whitney U tests comparing Q1 and Q4.")
    lines.append("   These tests are intended as trend diagnostics; the manuscript figure should emphasize")
    lines.append("   percentile-ranked distributions to avoid exposing system-specific raw values.")
    lines.append("")
    lines.append("6. Output files")
    for key, path in outputs.items():
        lines.append(f"   {key}: {path}")
    lines.append("")
    lines.append("7. Suggested manuscript interpretation")
    lines.append("   High-EFA quartiles show lower lattice-distortion metrics, lower Ghosh radius mismatch,")
    lines.append("   and higher Λ_Ghosh/VEC compared with low-EFA quartiles. These class-based distributions")
    lines.append("   provide a ranking while hiding individual EFA values.")
    out_txt.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_excel(input_path, sheet_name=args.sheet)
    n_raw = len(df)

    required = [args.efa_col] + args.efa_descriptors
    required_unique = list(dict.fromkeys(required))
    check_columns(df, required_unique)

    data = df.copy()
    for col in required_unique:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    data = data.dropna(subset=[args.efa_col]).reset_index(drop=True)
    n_used = len(data)

    family_cols_existing = [c for c in args.family_cols if c in data.columns]
    data["compositional_family"] = data.apply(lambda row: make_family(row, family_cols_existing), axis=1)
    data["anonymous_id"] = [f"CHAOS_{i+1:04d}" for i in range(n_used)]

    # Percentiles for targets and all descriptors used in plotting.
    data["EFA_percentile"] = percentile_rank(data[args.efa_col])
    data["EFA_quartile"] = quartile_from_percentile(data["EFA_percentile"])

    all_descriptors = list(dict.fromkeys(args.efa_descriptors))
    for desc in all_descriptors:
        data[f"{desc}_percentile"] = percentile_rank(data[desc])

    public_plot, raw_plot = build_long_tables(data, args.efa_descriptors)
    quartile_summary = summarize_quartiles(raw_plot)
    trend_tests = calc_tests(raw_plot)

    # A compact public wide table, useful for checking without exposing raw values.
    public_wide_cols = [
        "anonymous_id",
        "compositional_family",
        "EFA_percentile",
        "EFA_quartile",
    ] + [f"{d}_percentile" for d in all_descriptors]
    public_wide = data[public_wide_cols].copy()

    # Summary highlights for easy manuscript extraction.
    highlight_rows = []
    for axis, descriptors in [("EFA quartile", args.efa_descriptors)]:
        for desc in descriptors:
            sub = quartile_summary[(quartile_summary["quartile_axis"] == axis) & (quartile_summary["descriptor_column"] == desc)]
            means = {row["quartile"]: row["raw_mean"] for _, row in sub.iterrows()}
            highlight_rows.append(
                {
                    "quartile_axis": axis,
                    "descriptor_column": desc,
                    "descriptor_label": LABELS.get(desc, desc),
                    "Q1_raw_mean": means.get("Q1", np.nan),
                    "Q2_raw_mean": means.get("Q2", np.nan),
                    "Q3_raw_mean": means.get("Q3", np.nan),
                    "Q4_raw_mean": means.get("Q4", np.nan),
                    "Q4_minus_Q1_raw_mean": means.get("Q4", np.nan) - means.get("Q1", np.nan),
                }
            )
    highlights = pd.DataFrame(highlight_rows)

    config = pd.DataFrame(
        [
            {"parameter": "input_workbook", "value": str(input_path)},
            {"parameter": "sheet", "value": args.sheet},
            {"parameter": "rows_raw", "value": n_raw},
            {"parameter": "rows_used", "value": n_used},
            {"parameter": "EFA_column", "value": args.efa_col},
            {"parameter": "EFA_quartile_descriptors", "value": ", ".join(args.efa_descriptors)},
            {"parameter": "percentile_definition", "value": "(rank - 1) / (N - 1), average rank for ties"},
            {"parameter": "public_plot_sheet", "value": "Contains only percentiles and anonymous IDs; no raw EFA values."},
        ]
    )

    out_xlsx = outdir / "efa_quartile_class_analysis.xlsx"
    write_excel_workbook(
        out_xlsx,
        {
            "Plot_Public_Long": public_plot,
            "Plot_Public_Wide": public_wide,
            "Plot_Internal_Raw": raw_plot,
            "Quartile_Summary": quartile_summary,
            "Trend_Tests": trend_tests,
            "Manuscript_Highlights": highlights,
            "Config": config,
        },
    )

    # Third output file: OriginPro-ready workbook with one worksheet per subplot.
    # In each worksheet, columns A-D contain Q1-Q4 descriptor-percentile distributions
    # that can be directly selected in OriginPro 2024 for violin/box plots.
    out_origin_xlsx = outdir / "efa_quartile_class_originpro_subplots.xlsx"
    write_originpro_workbook(out_origin_xlsx, raw_plot)

    out_txt = outdir / "efa_quartile_class_analysis_report.txt"
    outputs = {
        "Main Excel workbook": str(out_xlsx),
        "OriginPro subplot Excel workbook": str(out_origin_xlsx),
        "TXT report": str(out_txt),
    }
    write_report(out_txt, args, n_raw, n_used, quartile_summary, trend_tests, outputs)

    manifest = {
        "script": Path(__file__).name,
        "input": str(input_path),
        "sheet": args.sheet,
        "rows_raw": n_raw,
        "rows_used": n_used,
        "outputs": outputs,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("Done. Outputs written to:")
    for key, value in outputs.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
