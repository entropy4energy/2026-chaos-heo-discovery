"""Independent seed and constant-feature checks using the archived model API."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "11_model_robustness"
LOCKED = ROOT / "00_cohort_lock/output/locked_493.xlsx"
COMMON_SOURCE = ROOT / "06_fig7a_regression/code/efa_screening_common.py"


def main() -> None:
    if TASK.exists():
        raise FileExistsError(f"Do not replace existing robustness output: {TASK}")
    for part in ("code", "input", "output"):
        (TASK / part).mkdir(parents=True)
    shutil.copy2(LOCKED, TASK / "input/locked_493.xlsx")
    shutil.copy2(COMMON_SOURCE, TASK / "code/efa_screening_common.py")
    shutil.copy2(Path(__file__), TASK / "code/run_model_robustness.py")
    spec = importlib.util.spec_from_file_location("efa_screening_common", TASK / "code/efa_screening_common.py")
    common = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(common)
    df = common.load_screening_dataframe(TASK / "input/locked_493.xlsx")
    assert len(df) == 493 and int(df.high_EFA.sum()) == 124
    features = common.get_feature_groups(df)
    full = features["Combined"]
    config = [col for col in full if col.startswith("S_config_")]
    reduced = [col for col in full if col not in config]
    assert len(full) == 30 and len(config) == 6 and len(reduced) == 24
    assert all(df[col].nunique(dropna=False) == 1 for col in config)
    rows = []
    for seed in range(20):
        pred, _ = common.regression_oof(df, full, random_state=seed)
        reg = common.regression_metrics(df.log10_EFA, pred)
        prob, _ = common.classification_oof(df, full, random_state=seed)
        cls = common.classification_metrics(df.high_EFA, prob)
        n = int(np.ceil(0.10 * len(df)))
        hit = int(df.high_EFA.iloc[np.argsort(-prob)[:n]].sum())
        rows.append({"seed": seed, "N": 493, "high_EFA_count": 124,
                     "combined_R2": reg["R2"], "combined_Spearman_rho": reg["Spearman_rho"],
                     "combined_ROC_AUC": cls["ROC_AUC"], "combined_top10_n": n,
                     "combined_top10_hits": hit, "combined_top10_precision": hit / n})
        print("seed", seed, flush=True)
    seed42 = {}
    for name, cols in (("original_30", full), ("corrected_24", reduced)):
        pred, _ = common.regression_oof(df, cols, random_state=42)
        prob, _ = common.classification_oof(df, cols, random_state=42)
        seed42[name] = {"feature_count": len(cols),
                        "regression": common.regression_metrics(df.log10_EFA, pred),
                        "classification": common.classification_metrics(df.high_EFA, prob),
                        "prediction_regression": pred.tolist(),
                        "prediction_classification": prob.tolist()}
    reg_diff = float(np.max(np.abs(np.array(seed42["original_30"]["prediction_regression"]) - np.array(seed42["corrected_24"]["prediction_regression"]))))
    cls_diff = float(np.max(np.abs(np.array(seed42["original_30"]["prediction_classification"]) - np.array(seed42["corrected_24"]["prediction_classification"]))))
    result = {"constant_config_columns": config, "full_columns": full, "reduced_columns": reduced,
              "seed42_max_abs_prediction_difference_regression": reg_diff,
              "seed42_max_abs_prediction_difference_classification": cls_diff,
              "numerically_identical_at_1e_10": bool(reg_diff < 1e-10 and cls_diff < 1e-10)}
    if not result["numerically_identical_at_1e_10"]:
        raise AssertionError(result)
    pd.DataFrame(rows).to_csv(TASK / "output/twenty_seed_metrics.csv", index=False)
    pd.DataFrame([result]).drop(columns=["full_columns", "reduced_columns"]).to_csv(TASK / "output/feature_group_check.csv", index=False)
    (TASK / "output/feature_group_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with pd.ExcelWriter(TASK / "output/model_robustness.xlsx", engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Twenty_Seeds", index=False)
        pd.DataFrame([{"model": name, "feature_count": data["feature_count"],
                       "R2": data["regression"]["R2"],
                       "Spearman_rho": data["regression"]["Spearman_rho"],
                       "ROC_AUC": data["classification"]["ROC_AUC"]}
                      for name, data in seed42.items()]).to_excel(writer, sheet_name="30_vs_24", index=False)


if __name__ == "__main__":
    main()
