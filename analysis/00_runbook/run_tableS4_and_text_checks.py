"""Table S4 models and the counts the manuscript text reports beside Figure 7d
and Table S3 (2026-10-10).

Table S4 compares five ridge and logistic models, all with the archived model
API of the Figure 7 analyses (06_fig7a_regression/code/efa_screening_common.py)
and its defaults: median imputation and standardization inside each fold,
five-fold out-of-fold predictions, KFold for regression and StratifiedKFold for
classification, random state 42. Three models are the Figure 7 feature groups
(DFT only, Chemistry only, Combined); their metrics must equal those in
13_summary/output/final_metrics.csv. The other two use element presence: 15
binary features, one per metal of the cohort, equal to 1 when the system
contains that metal, alone or together with the DFT-only group.

The text checks count, from 12_rankings/output/all_493_ranked.csv and the
submitted Table S3 (literature_candidates/table_s3_submitted.csv): the entries
whose descriptor compatibility reaches 0.75 and how many of them are high EFA;
the high-EFA entries of the 52-entry priority region; the exact and subset
matches of Table S3 and how many lie in the top EFA quartile; and the priority
entries that appear in Table S3, those that do not, and how many of the latter
contain Cd.

It then rewrites VALIDATION.json and MANIFEST.csv with rerun_20261007.py's
verify (same folder) and adds this folder's summary to VALIDATION.json.

    python3 analysis/00_runbook/run_tableS4_and_text_checks.py
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
RUNBOOK = ROOT / "00_runbook"
TASK = ROOT / "14_tableS4_and_text_checks"
LOCKED = ROOT / "00_cohort_lock/output/locked_493.xlsx"
COMMON_SOURCE = ROOT / "06_fig7a_regression/code/efa_screening_common.py"
RANKED = ROOT / "12_rankings/output/all_493_ranked.csv"
TABLE_S3 = REPO / "literature_candidates/table_s3_submitted.csv"
METRICS = ROOT / "13_summary/output/final_metrics.csv"
METAL_COLUMNS = ["Metal1", "Metal2", "Metal3", "Metal4"]
PACKAGES = ["numpy", "pandas", "scipy", "scikit-learn", "matplotlib", "openpyxl"]
NOTE = "2026-10-10, Table S4 models and text counts (00_runbook/run_tableS4_and_text_checks.py)"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, RUNBOOK / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def model_rows(common, df: pd.DataFrame, groups: dict) -> list:
    rows = []
    for name, cols in groups.items():
        pred, _ = common.regression_oof(df, cols)
        reg = common.regression_metrics(df.log10_EFA, pred)
        prob, _ = common.classification_oof(df, cols)
        cls = common.classification_metrics(df.high_EFA, prob)
        n = int(np.ceil(0.10 * len(df)))
        hits = int(df.high_EFA.iloc[np.argsort(-prob)[:n]].sum())
        informative = [c for c in cols if df[c].nunique(dropna=False) > 1]
        rows.append({"model": name, "feature_count": len(cols),
                     "informative_feature_count": len(informative),
                     "R2": reg["R2"], "Spearman_rho": reg["Spearman_rho"],
                     "ROC_AUC": cls["ROC_AUC"], "top_n": n, "top_n_high_EFA": hits})
    return rows


def text_checks(ranked: pd.DataFrame, table: pd.DataFrame) -> dict:
    compatible = ranked[ranked.compatibility_score >= 0.75]
    region = ranked[ranked.predicted_priority_region.astype(bool)]
    in_table = region.full_cation_key.isin(table.full_cation_key)
    outside = region[~in_table]
    top_quartile = table.EFA_percentile >= 0.75
    exact = table.cation_set_match == "exact"
    return {
        "compatibility_at_least_0.75": {"entries": len(compatible),
                                        "high_EFA": int(compatible.high_EFA_observed.sum())},
        "figure7d_priority_region": {"entries": len(region),
                                     "high_EFA": int(region.high_EFA_observed.sum())},
        "table_s3": {"rows": len(table), "exact": int(exact.sum()),
                     "subset": int((table.cation_set_match == "subset").sum()),
                     "top_EFA_quartile": int(top_quartile.sum()),
                     "exact_in_top_EFA_quartile": int((exact & top_quartile).sum())},
        "priority_region_and_table_s3": {"in_table_s3": int(in_table.sum()),
                                         "not_in_table_s3": len(outside),
                                         "not_in_table_s3_with_Cd": int(outside.full_cation_key.str.split(",").map(lambda s: "Cd" in s).sum()),
                                         "not_in_table_s3_keys": sorted(outside.full_cation_key)},
    }


def main() -> None:
    if TASK.exists():
        raise FileExistsError(f"Do not replace existing output: {TASK.relative_to(REPO)}")
    for part in ("code", "input", "output"):
        (TASK / part).mkdir(parents=True)
    shutil.copy2(LOCKED, TASK / "input/locked_493.xlsx")
    shutil.copy2(RANKED, TASK / "input/all_493_ranked.csv")
    shutil.copy2(TABLE_S3, TASK / "input/table_s3_submitted.csv")
    shutil.copy2(COMMON_SOURCE, TASK / "code/efa_screening_common.py")
    shutil.copy2(Path(__file__), TASK / "code/run_tableS4_and_text_checks.py")
    spec = importlib.util.spec_from_file_location("efa_screening_common", TASK / "code/efa_screening_common.py")
    common = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(common)

    df = common.load_screening_dataframe(TASK / "input/locked_493.xlsx")
    assert len(df) == 493 and int(df.high_EFA.sum()) == 124
    metals = sorted(set(df[METAL_COLUMNS].values.ravel()))
    assert len(metals) == 15
    presence = pd.DataFrame({f"has_{m}": df[METAL_COLUMNS].eq(m).any(axis=1).astype(float) for m in metals})
    assert presence.sum(axis=1).eq(4).all()
    df = pd.concat([df, presence], axis=1)
    features = common.get_feature_groups(df)
    element = list(presence.columns)
    groups = {"DFT only": features["DFT only"], "Chemistry only": features["Chemistry only"],
              "Combined": features["Combined"], "Element presence": element,
              "Element presence + DFT only": element + features["DFT only"]}
    rows = model_rows(common, df, groups)

    reported = pd.read_csv(METRICS).set_index("metric").value
    for row in rows[:3]:
        name = row["model"]
        assert abs(row["R2"] - reported[f"{name}_R2"]) < 1e-9, name
        assert abs(row["Spearman_rho"] - reported[f"{name}_Spearman_rho"]) < 1e-9, name
        assert abs(row["ROC_AUC"] - reported[f"{name}_ROC_AUC"]) < 1e-9, name
        assert row["top_n_high_EFA"] == int(reported[f"{name}_top10_true_high_EFA_hits"]), name

    checks = text_checks(pd.read_csv(TASK / "input/all_493_ranked.csv"),
                         pd.read_csv(TASK / "input/table_s3_submitted.csv"))

    pd.DataFrame(rows).to_csv(TASK / "output/table_s4_models.csv", index=False)
    pd.concat([df[["full_cation_key"]], presence.astype(int)], axis=1).to_csv(
        TASK / "output/element_presence_features.csv", index=False)
    (TASK / "output/text_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    metadata = {
        "command": ["python3", "analysis/00_runbook/run_tableS4_and_text_checks.py"],
        "returncode": 0,
        "input_sha256": load("update_solubility_parameter").sha256(TASK / "input/locked_493.xlsx"),
        "python": sys.version,
        "packages": {name: importlib.metadata.version(name) for name in PACKAGES},
        "reported_models_reproduced": "DFT only, Chemistry only and Combined match 13_summary/output/final_metrics.csv to 1e-9",
    }
    (TASK / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    for row in rows:
        print(f"{row['model']:28s} R2 {row['R2']:.3f}  rho {row['Spearman_rho']:.3f}  "
              f"AUC {row['ROC_AUC']:.3f}  top {row['top_n']} {row['top_n_high_EFA']}")
    print(json.dumps({k: v for k, v in checks.items() if k != "priority_region_and_table_s3"}))
    print(json.dumps({k: v for k, v in checks["priority_region_and_table_s3"].items() if k != "not_in_table_s3_keys"}))
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path)
    verify(rows, checks)


def verify(rows: list, checks: dict) -> None:
    rerun = load("rerun_20261007")
    rerun.verify()
    validation = ROOT / "VALIDATION.json"
    result = json.loads(validation.read_text(encoding="utf-8"))
    result["tableS4_and_text_checks"] = {
        "note": NOTE,
        "models": {row["model"]: {"R2": round(row["R2"], 3), "Spearman_rho": round(row["Spearman_rho"], 3),
                                  "ROC_AUC": round(row["ROC_AUC"], 3), "top_50_high_EFA": row["top_n_high_EFA"]}
                   for row in rows},
        "compatibility_at_least_0.75": checks["compatibility_at_least_0.75"],
        "table_s3": checks["table_s3"],
        "priority_region_in_table_s3": checks["priority_region_and_table_s3"]["in_table_s3"],
    }
    validation.write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest = ROOT / "MANIFEST.csv"
    lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("VALIDATION.json,"):
            end = "\r\n" if line.endswith("\r\n") else "\n"
            lines[i] = f"VALIDATION.json,runbook/metadata,{validation.stat().st_size},{rerun.usp.sha256(validation)}{end}"
    manifest.write_text("".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
