"""Assemble verified metrics, rankings and figure tables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CURRENT_MANUSCRIPT = Path("MANUSCRIPT_SOURCE")

FIGURES = {
    "01_fig6a_compatibility": ("fig6a_descriptor_compatibility_vs_efa_analysis.xlsx", ["Plot_Data", "OriginPro_XY", "OriginPro_By_Class", "OriginPro_Thresholds"]),
    "02_fig6b_pca": ("pca_efa_chaos_descriptor_space_H_L_S_AK_analysis.xlsx", ["PCA_Scores_Public", "PCA_Explained_Variance", "PCA_Loadings_Wide"]),
    "03_fig6c_si_quartiles": ("efa_quartile_class_analysis.xlsx", ["Plot_Public_Long", "Quartile_Summary", "Trend_Tests"]),
    "04_fig6d_distortion": ("efa_lattice_descriptor_correlations.xlsx", ["Heatmap_Spearman", "Correlation_Long"]),
    "05_fig6d_chemistry": ("efa_chemical_descriptor_correlations.xlsx", ["Heatmap_Spearman", "Correlation_Long_All"]),
    "06_fig7a_regression": ("panel_a_predicted_vs_observed_logEFA_data.xlsx", ["OOF_Predictions", "CV_Metrics"]),
    "07_fig7b_classification": ("panel_b_highEFA_ROC_PR_data.xlsx", ["Curve_Data", "OOF_Probabilities", "Classifier_Metrics"]),
    "08_fig7c_enrichment": ("panel_c_highEFA_enrichment_lift_data.xlsx", ["Enrichment_Curve", "TopK_Highlights"]),
    "09_fig7d_prioritization": ("fig7d_predEFA_descriptor_compatibility_analysis.xlsx", ["Plot_Data_Public", "OriginPro_XY", "OriginPro_By_Class", "OriginPro_Thresholds"]),
}


def table(folder: str, sheet: str) -> pd.DataFrame:
    return pd.read_excel(ROOT / folder / "output" / FIGURES[folder][0], sheet_name=sheet)


def json_value(value):
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def workbook_sheet(name: str, frame: pd.DataFrame) -> dict:
    return {"name": name, "columns": frame.columns.tolist(),
            "data": [[json_value(item) for item in row] for row in frame.itertuples(index=False, name=None)]}


def source_exports(locked: pd.DataFrame) -> pd.DataFrame:
    index = []
    for folder, (filename, sheets) in FIGURES.items():
        output_dir = ROOT / folder / "output/figure_source_csv"
        output_dir.mkdir(parents=True, exist_ok=True)
        for sheet in sheets:
            df = table(folder, sheet)
            if folder == "01_fig6a_compatibility" and sheet in ("Plot_Data", "OriginPro_XY"):
                # The archived Figure 6a helper misreads PAW/POCC tags in the raw
                # AFLOW name as extra elements. Preserve its score, replace only
                # its label with the authoritative four-cation worksheet key.
                if len(df) != len(locked):
                    raise AssertionError("Figure 6a row count changed")
                df["full_cation_key_verified"] = locked.full_cation_key.to_numpy()
                df["candidate_formula_verified"] = "(" + locked.full_cation_key.str.replace(",", ",") + ")O"
                if "cation_set" in df:
                    df = df.drop(columns=["cation_set"])
                if "CHAOS_formula" in df:
                    df = df.drop(columns=["CHAOS_formula"])
            destination = output_dir / f"{sheet}.csv"
            df.to_csv(destination, index=False)
            index.append({"figure": folder, "source_workbook": f"{folder}/output/{filename}",
                          "sheet": sheet, "csv": str(destination.relative_to(ROOT)), "rows": len(df)})
    frame = pd.DataFrame(index)
    frame.to_csv(ROOT / "13_summary/output/figure_source_index.csv", index=False)
    return frame


def rankings(locked: pd.DataFrame) -> pd.DataFrame:
    a = table("01_fig6a_compatibility", "Plot_Data")
    d = table("09_fig7d_prioritization", "Plot_Data_Public")
    reg = table("06_fig7a_regression", "OOF_Predictions")
    cls = table("07_fig7b_classification", "OOF_Probabilities")
    combined_reg = reg[reg.feature_group.eq("Combined")].reset_index(drop=True)
    combined_cls = cls[cls.feature_group.eq("Combined")].reset_index(drop=True)
    chem_cls = cls[cls.feature_group.eq("Chemistry only")].reset_index(drop=True)
    anon = pd.Series([f"CHAOS_{i + 1:04d}" for i in range(len(locked))])
    for frame in (a, d, combined_reg, combined_cls, chem_cls):
        if not frame.anonymous_id.reset_index(drop=True).equals(anon):
            raise AssertionError("Out-of-fold rows no longer match locked cohort order")
    if not np.allclose(a.Y_EFA_percentile, d.observed_EFA_percentile):
        raise AssertionError("Figure 6a/7d observed percentile mismatch")
    if not np.allclose(a.X_CHAOS_descriptor_compatibility_score, d.descriptor_compatibility_score):
        raise AssertionError("Figure 6a/7d compatibility score mismatch")
    result = pd.DataFrame({
        "anonymous_id": anon, "locked_excel_row": np.arange(2, len(locked) + 2),
        "source_503_excel_row": pd.read_csv(ROOT / "00_cohort_lock/output/source_row_mapping.csv").source_combined_excel_row,
        "full_cation_key": locked.full_cation_key,
        "candidate_formula": d.candidate_formula,
        "EFA_observed_internal": locked.EFA,
        "observed_EFA_percentile": d.observed_EFA_percentile,
        "high_EFA_observed": d.true_high_EFA.astype(int),
        "compatibility_score": d.descriptor_compatibility_score,
        "predicted_EFA_percentile_oof": d.predicted_EFA_percentile,
        "predicted_log10_EFA_oof_combined": combined_reg.predicted_log10_EFA_oof,
        "predicted_high_EFA_probability_oof_combined": combined_cls.predicted_probability_high_EFA_oof,
        "predicted_high_EFA_probability_oof_chemistry": chem_cls.predicted_probability_high_EFA_oof,
        "predicted_priority_region": d.predicted_priority_region.astype(int),
        "observed_priority_class": d.true_class,
    })
    result["rank_by_combined_high_EFA_probability"] = result.predicted_high_EFA_probability_oof_combined.rank(method="first", ascending=False).astype(int)
    result["rank_by_chemistry_high_EFA_probability"] = result.predicted_high_EFA_probability_oof_chemistry.rank(method="first", ascending=False).astype(int)
    result["rank_by_predicted_EFA_percentile"] = result.predicted_EFA_percentile_oof.rank(method="first", ascending=False).astype(int)
    result["rank_by_compatibility_score"] = result.compatibility_score.rank(method="first", ascending=False).astype(int)
    result = result.sort_values("rank_by_combined_high_EFA_probability").reset_index(drop=True)
    destination = ROOT / "12_rankings/output"
    result.to_csv(destination / "all_493_ranked.csv", index=False)
    result.head(50).to_csv(destination / "combined_top_10_percent_50.csv", index=False)
    result.sort_values("rank_by_chemistry_high_EFA_probability").head(50).to_csv(destination / "chemistry_top_10_percent_50.csv", index=False)
    result[result.predicted_priority_region.eq(1)].sort_values("predicted_EFA_percentile_oof", ascending=False).to_csv(destination / "figure7d_priority_region_52.csv", index=False)
    with pd.ExcelWriter(destination / "rankings_493.xlsx", engine="openpyxl") as writer:
        result.to_excel(writer, sheet_name="All_493", index=False)
        result.head(50).to_excel(writer, sheet_name="Combined_Top_50", index=False)
        result.sort_values("rank_by_chemistry_high_EFA_probability").head(50).to_excel(writer, sheet_name="Chemistry_Top_50", index=False)
        result[result.predicted_priority_region.eq(1)].to_excel(writer, sheet_name="Fig7d_Priority_52", index=False)
    assert len(result) == 493 and int(result.high_EFA_observed.sum()) == 124
    assert int(result.predicted_priority_region.sum()) == 52
    return result


def metric_rows(locked: pd.DataFrame) -> pd.DataFrame:
    landscape = table("01_fig6a_compatibility", "Summary").set_index("metric")["value"]
    classes = table("01_fig6a_compatibility", "Class_Counts")
    reg = table("06_fig7a_regression", "CV_Metrics")
    cls = table("07_fig7b_classification", "Classifier_Metrics")
    top = table("08_fig7c_enrichment", "TopK_Highlights")
    d = table("09_fig7d_prioritization", "Summary").iloc[0]
    pca = table("02_fig6b_pca", "PCA_Explained_Variance")
    corr = table("04_fig6d_distortion", "Correlation_Long")
    rows = [
        ("cohort", "N_four_cation_systems", 493, "count", "00_cohort_lock"),
        ("cohort", "high_EFA_count", 124, "count", "07_fig7b_classification"),
        ("Figure6a", "S_CHAOS_EFA_percentile_Spearman_rho", float(landscape["Spearman rho(S_CHAOS, EFA percentile)"]), "", "01_fig6a_compatibility"),
        ("Figure6b", "PC1_variance_percent", 100 * pca.iloc[0].explained_variance_ratio, "%", "02_fig6b_pca"),
        ("Figure6b", "PC2_variance_percent", 100 * pca.iloc[1].explained_variance_ratio, "%", "02_fig6b_pca"),
    ]
    for _, line in classes.iterrows():
        rows.append(("Figure6a", f"class_count_{line.true_class}", line["count"], "count", "01_fig6a_compatibility"))
    for _, line in reg.iterrows():
        for key in ("n_features", "R2", "Spearman_rho", "RMSE", "MAE"):
            rows.append(("Figure7a", f"{line.feature_group}_{key}", line[key], "count" if key == "n_features" else "", "06_fig7a_regression"))
    for _, line in cls.iterrows():
        for key in ("ROC_AUC", "Average_precision", "Brier_score"):
            rows.append(("Figure7b", f"{line.feature_group}_{key}", line[key], "", "07_fig7b_classification"))
    for _, line in top[top.top_fraction_percent.eq(10)].iterrows():
        for key in ("top_n", "true_high_EFA_hits", "precision_in_top_k", "enrichment_factor"):
            rows.append(("Figure7c", f"{line.feature_group}_top10_{key}", line[key], "", "08_fig7c_enrichment"))
    for key in ("predicted_priority_region_count", "predicted_priority_region_precision_for_true_both", "predicted_priority_region_enrichment_for_true_both", "true_high_EFA_and_high_compatibility_prevalence"):
        rows.append(("Figure7d", key, d[key], "", "09_fig7d_prioritization"))
    focus = corr[(corr.target_column.eq("EFA")) & (corr.descriptor_column.eq("lat_distortion_misfit_mean")) & (corr.method.eq("Spearman"))]
    if len(focus) != 1:
        raise AssertionError("Cannot identify epsilon-EFA Spearman coefficient")
    rows.append(("Figure6d", "Spearman_EFA_epsilon_bar", focus.iloc[0].coefficient, "", "04_fig6d_distortion"))
    chemistry = table("05_fig6d_chemistry", "Correlation_Long_All")
    for descriptor in ("VEC", "delta_radii_Ghosh08", "param_geo_radii_Ghosh08"):
        item = chemistry[(chemistry.target_column.eq("EFA")) & (chemistry.descriptor_column.eq(descriptor)) & (chemistry.method.eq("Spearman"))]
        assert len(item) == 1, descriptor
        rows.append(("Figure6d", f"Spearman_EFA_{descriptor}", item.iloc[0].coefficient, "", "05_fig6d_chemistry"))
    seeds = pd.read_csv(ROOT / "11_model_robustness/output/twenty_seed_metrics.csv")
    for key in ("combined_R2", "combined_Spearman_rho", "combined_ROC_AUC", "combined_top10_precision"):
        rows.append(("sensitivity", f"{key}_min_seeds_0_to_19", seeds[key].min(), "", "11_model_robustness"))
        rows.append(("sensitivity", f"{key}_max_seeds_0_to_19", seeds[key].max(), "", "11_model_robustness"))
    frame = pd.DataFrame(rows, columns=["section", "metric", "value", "unit", "analysis_folder"])
    frame.to_csv(ROOT / "13_summary/output/final_metrics.csv", index=False)
    return frame


def main() -> None:
    for folder in ("12_rankings", "13_summary"):
        for part in ("input", "code", "output"):
            (ROOT / folder / part).mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(__file__), ROOT / folder / "code/assemble_production.py")
    locked_source = ROOT / "00_cohort_lock/output/locked_493.xlsx"
    for folder in ("12_rankings", "13_summary"):
        shutil.copy2(locked_source, ROOT / folder / "input/locked_493.xlsx")
    for file in ("results.tex", "methods.tex", "SI.tex"):
        shutil.copy2(CURRENT_MANUSCRIPT / file, ROOT / "13_summary/input" / file)
    locked = pd.read_excel(locked_source, sheet_name="combined")
    assert len(locked) == 493 and locked.full_cation_key.is_unique
    figure_index = source_exports(locked)
    ranks = rankings(locked)
    metrics = metric_rows(locked)
    literature = pd.read_csv(ROOT / "10_literature_candidates/output/literature_table_43_retained.csv")
    sensitivity = pd.read_csv(ROOT / "11_model_robustness/output/twenty_seed_metrics.csv")
    sheets = [workbook_sheet("Final_Metrics", metrics),
              workbook_sheet("Top_50_Combined", ranks.head(50).drop(columns=["EFA_observed_internal"])),
              workbook_sheet("Twenty_Seeds", sensitivity),
              workbook_sheet("Figure_Sources", figure_index),
              workbook_sheet("Literature_43", literature.drop(columns=["source_line_text"]))]
    (ROOT / "13_summary/output/summary_workbook.json").write_text(json.dumps({"sheets": sheets}, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print("assembled", len(metrics), "metrics", len(figure_index), "figure tables")


if __name__ == "__main__":
    main()
