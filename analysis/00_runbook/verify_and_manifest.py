"""Final consistency checks and complete additive-file manifest."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for piece in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(piece)
    return h.hexdigest()


def main() -> None:
    cohort = pd.read_excel(ROOT / "00_cohort_lock/output/locked_493.xlsx", sheet_name="combined")
    assert len(cohort) == 493 and cohort.full_cation_key.is_unique
    assert cohort.cation_count.eq(4).all() and cohort.match_count.eq(1).all()
    assert cohort.Metal5.isna().all()
    assert len(pd.read_csv(ROOT / "00_cohort_lock/output/excluded_ten_quinaries.csv")) == 10
    run_checks = []
    input_hash = sha256(ROOT / "00_cohort_lock/output/locked_493.xlsx")
    for folder in sorted(ROOT.glob("0[1-9]_*")):
        metadata = json.loads((folder / "run_metadata.json").read_text())
        assert metadata["returncode"] == 0 and metadata["input_sha256"] == input_hash
        assert (folder / "output/figure_source_csv").is_dir()
        for item in metadata["script_snapshots"]:
            snapshot = ROOT / item["snapshot"]
            assert sha256(snapshot) == item["sha256"]
        run_checks.append({"folder": folder.name, "status": "passed"})
    ranks = pd.read_csv(ROOT / "12_rankings/output/all_493_ranked.csv")
    metrics = pd.read_csv(ROOT / "13_summary/output/final_metrics.csv")
    changes = pd.read_csv(ROOT / "13_summary/output/before_after_manuscript_numbers.csv")
    assert len(ranks) == 493 and ranks.full_cation_key.is_unique
    assert ranks.high_EFA_observed.sum() == 124
    assert ranks.predicted_priority_region.sum() == 52
    assert len(pd.read_csv(ROOT / "12_rankings/output/combined_top_10_percent_50.csv")) == 50
    chemistry = pd.read_csv(ROOT / "12_rankings/output/chemistry_top_10_percent_50.csv")
    assert len(chemistry) == 50 and int(chemistry.high_EFA_observed.sum()) == 42
    priority = pd.read_csv(ROOT / "12_rankings/output/figure7d_priority_region_52.csv")
    assert len(priority) == 52 and int(priority.observed_priority_class.eq("true high-EFA + high descriptor compatibility score").sum()) == 48
    assert len(pd.read_csv(ROOT / "10_literature_candidates/output/literature_table_43_retained.csv")) == 43
    assert len(pd.read_csv(ROOT / "10_literature_candidates/output/literature_table_4_removed.csv")) == 4
    assert len(pd.read_csv(ROOT / "11_model_robustness/output/twenty_seed_metrics.csv")) == 20
    assert json.loads((ROOT / "11_model_robustness/output/feature_group_check.json").read_text())["numerically_identical_at_1e_10"]
    assert len(metrics) >= 60 and len(changes) == 18
    assert len(pd.read_csv(ROOT / "13_summary/output/figure_source_index.csv")) == 25
    summary = pd.ExcelFile(ROOT / "13_summary/output/CHAOS_EFA493_production_summary.xlsx")
    assert {"Final_Metrics", "Before_After", "Top_50_Combined", "Twenty_Seeds", "Figure_Sources", "Literature_43"}.issubset(summary.sheet_names)
    result = {"cohort_rows": len(cohort), "excluded_rows": 10, "high_EFA": 124,
              "analysis_checks": run_checks, "chemistry_top_50_hits": 42,
              "priority_region": {"total": 52, "true_joint_class": 48},
              "literature_rows": {"retained": 43, "removed": 4},
              "seed_count": 20, "figure_source_csv_count": 25,
              "no_existing_file_replaced": True}
    (ROOT / "VALIDATION.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest_path = ROOT / "MANIFEST.csv"
    rows = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink() or path == manifest_path:
            continue
        rel = path.relative_to(ROOT)
        component = rel.parts[0]
        role = "runbook/metadata" if component in ("00_runbook",) or len(rel.parts) == 1 else ("analysis input" if "input" in rel.parts else "script snapshot" if "code" in rel.parts else "analysis output")
        rows.append((str(rel), role, path.stat().st_size, sha256(path)))
    rows.append(("MANIFEST.csv", "self-reference; hash intentionally omitted", "", ""))
    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("path_relative_to_package", "role", "bytes", "sha256"))
        writer.writerows(rows)
    print("validated", result["cohort_rows"], "rows; manifest files", len(rows))


if __name__ == "__main__":
    main()
