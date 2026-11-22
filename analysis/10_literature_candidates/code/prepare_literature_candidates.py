"""Audit, but do not edit, the manuscript's literature-supported candidate rows."""

from __future__ import annotations

import re
from pathlib import Path
import shutil

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "10_literature_candidates"
SOURCE = Path("MANUSCRIPT_SOURCE/Table/evidence-graded candidate table.tex")
FIG6A = ROOT / "01_fig6a_compatibility/output/fig6a_descriptor_compatibility_vs_efa_analysis.xlsx"
LOCKED = ROOT / "00_cohort_lock/output/locked_493.xlsx"


def main() -> None:
    if TASK.exists() and any((TASK / "output").glob("*")):
        raise FileExistsError(f"Refusing to replace {TASK}")
    for component in ("input", "code", "output"):
        (TASK / component).mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE, TASK / "input/evidence-graded_candidate_table_original.tex")
    shutil.copy2(LOCKED, TASK / "input/locked_493.xlsx")
    shutil.copy2(FIG6A, TASK / "input/fig6a_analysis_493.xlsx")
    shutil.copy2(Path(__file__), TASK / "code/prepare_literature_candidates.py")
    data = pd.read_excel(TASK / "input/fig6a_analysis_493.xlsx", sheet_name="Plot_Data")
    locked = pd.read_excel(TASK / "input/locked_493.xlsx", sheet_name="combined")
    data["full_cation_key"] = locked.full_cation_key
    match = data.set_index("full_cation_key")
    assert match.index.is_unique
    records = []
    for lineno, line in enumerate((TASK / "input/evidence-graded_candidate_table_original.tex").read_text(encoding="utf-8").splitlines(), 1):
        if not line.lstrip().startswith("$("):
            continue
        first = line.split("&", 1)[0]
        metals = re.findall(r"\\mathrm\{([A-Z][a-z]?)\}", first)
        if not metals:
            continue
        if metals[-1] == "O":
            metals = metals[:-1]
        cells = line.split("&")
        if len(cells) < 3 or not re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", cells[1]):
            continue  # wrapped reported-composition cell, not a new CHAOS row
        key = ",".join(sorted(metals))
        original_efa = float(cells[1].strip())
        original_score = float(cells[2].strip())
        present = key in match.index
        row = match.loc[key] if present else None
        records.append({
            "manuscript_source_line": lineno, "composition": f"({','.join(metals)})O",
            "full_cation_key": key, "cation_count": len(metals),
            "in_locked_493": bool(present),
            "original_table_EFA_percentile": original_efa,
            "production_493_EFA_percentile": float(row.Y_EFA_percentile) if present else None,
            "original_table_compatibility_score": original_score,
            "production_493_compatibility_score": float(row.X_CHAOS_descriptor_compatibility_score) if present else None,
            "suggested_action": "retain and update EFA percentile" if present else "remove: no verified five-cation EFA match",
            "source_line_text": line,
        })
    result = pd.DataFrame(records)
    if len(result) != 47 or result.in_locked_493.sum() != 43:
        raise AssertionError(result[["full_cation_key", "in_locked_493"]].to_string(index=False))
    result.to_csv(TASK / "output/literature_table_all_47_audit.csv", index=False)
    result[result.in_locked_493].to_csv(TASK / "output/literature_table_43_retained.csv", index=False)
    result[~result.in_locked_493].to_csv(TASK / "output/literature_table_4_removed.csv", index=False)
    with pd.ExcelWriter(TASK / "output/literature_candidates_493_audit.xlsx", engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="All_47_Audit", index=False)
        result[result.in_locked_493].to_excel(writer, sheet_name="Retain_43", index=False)
        result[~result.in_locked_493].to_excel(writer, sheet_name="Remove_4", index=False)
    print("candidate rows", len(result), "retained", int(result.in_locked_493.sum()), "removed", int((~result.in_locked_493).sum()))


if __name__ == "__main__":
    main()
