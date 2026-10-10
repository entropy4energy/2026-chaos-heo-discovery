# 2026 CHAOS HEO Discovery

This repository provides the analysis dataset, scripts and provenance record for the manuscript: **"CHAOS: A First-Principles Database for High-Entropy Oxide Discovery"**.

The repository is the record for the results reported in the manuscript. It holds the descriptor table the figures were computed from, the scripts that compute them, the provenance of that table, and the CHAOS-Agent benchmark archive. Nothing here requires the live database to reproduce. Data beyond these results, such as other CHAOS entries and quantities the manuscript does not use, are in the CHAOS database, which is available to registered users.

- **Input data:** a fixed extract of CHAOS property records for 503 equimolar rocksalt high-entropy oxide systems, with lattice-distortion and multi-scale chemical descriptors. For the 493 four-cation systems among them, it also holds the entropy-forming ability used in Figures 6 and 7.
- **Analysis scripts:** the per-figure Python scripts, the runbook that executed them, and the cohort-locking and manifest scripts.
- **Output:** figure-ready tables, per-panel plot data and reported metrics, plus the CHAOS-Agent benchmark questions, reference answers, per-attempt records and scores.

## Repository Structure

- `analysis/`: the production analysis package. Locked cohort, per-figure `input/`, `code/` and `output/`, run metadata, `MANIFEST.csv` and `VALIDATION.json`. Has its own README.
- `provenance/`: how the descriptor table was built, what was verified, and what could not be recovered. Start with `CREATION_PROCEDURE_20260925.md`.
- `corrected_workbook/`: the merged descriptor workbook after the five-cation join correction.
- `raw_input/`: the 503 prepared rows of the archived CHAOS property export, and `Clean_Data.m`, the MATLAB script of the first cleaning step of the full export.
- `solubility_parameter/`: the solubility parameter used in the analysis, which replaces the archived column, with its definition and the updated 503-row table of Figures 2 to 4.
- `figure5_pca/`: the data of Figure 5: mismatch descriptors, principal-component scores, loadings and explained variances, with the script that computes them from the prepared table. Has its own README.
- `literature_candidates/`: source tables for the supplementary candidate table, 43 retained rows, 4 removed rows, the full audit, and `table_s3_submitted.csv`, the table as submitted.
- `benchmark/`: the CHAOS-Agent benchmark archive. Has its own README and `MISSING_AND_LIMITATIONS.md`. The run records keep the queries, model messages, answers and scores; the text CHAOS returned to the models is replaced by its length and SHA-256.
- `CITATION.cff`: citation metadata.
- `REVIEW_LICENSE.md`: review-period reuse statement.

## The Cohort

The entropy-forming-ability cohort is 493 rocksalt (AB_cF8_225) systems with four cations at equal occupancy. `analysis/00_cohort_lock/output/locked_493.xlsx` is the sole input to Figures 6 and 7, Figure S2 and Tables S3 and S4. Figures 2 to 5 use all 503 rows of the prepared table.

The cohort was reduced from a prepared 503-row table. Ten rows carried five-cation compositions whose entropy-forming ability values were those of their four-cation parents: the historical merge extracted only the first four cations into its join keys and matched on the sorted four-element set, so each five-cation row inherited its parent's record. `provenance/JOIN_DIAGNOSIS_CONFIRMED_20260925.md` documents this from the original MATLAB source. The ten rows are listed in `analysis/00_cohort_lock/output/excluded_ten_quinaries.csv`. No corrected five-cation values were substituted, because the source EFA library contains only four-cation records. Four of the removed compositions also appear in the literature comparison and are listed in `literature_candidates/literature_table_4_removed.csv`.

## The Descriptors

The lattice-distortion quantities appear in the deposited table under the names used in the archived export:

| Field | Quantity |
|---|---|
| `lat_distortion_misfit_mean` | Mean lattice-distortion misfit over POCC supercells (dimensionless) |
| `lat_distortion_misfit_stdev` | Standard deviation of that misfit |
| `lat_distortion_relax_distance_mean` | Mean atomic relaxation distance (Angstrom) |
| `lat_distortion_relax_distance_stdev` | Standard deviation of that distance |
| `solubility_parameter` | Solubility parameter (GPa Angstrom^3); replaced in the analysis, see `solubility_parameter/` |

Three properties of these quantities matter when comparing them with anything else.

They are 1200 K quantities. In all 503 rows of the prepared table, each of the five values matches the 1200 K block of the POCC output stored with its entry (relative difference below 1e-6). The current CHAOS schema serves 0 K and 300 K variants of each field with a `_0K` or `_300K` suffix; the export predates those suffixes and carries the unsuffixed names.

The four distortion fields are averages over a subset. Each is a Boltzmann-weighted mean or standard deviation over the POCC supercell representatives for which a structural mapping between the ideal and relaxed cells could be established, with the supercell probabilities renormalized over that subset rather than over the full ensemble. A supercell for which no mapping is found is absent from the average.

The solubility parameter in the analysis is not the archived one. The archived column came from an AFLOW version with an error in the per-supercell lattice measure R*. The analysis uses values recomputed from the relaxed supercells with R* defined per atom, weighted over every supercell; `solubility_parameter/README.md` gives the definition and both sets of values.

## Relation to the Live Database

The CHAOS database is available to registered users through its search API and the CHAOS-Agent interface; instructions for access are given at https://s4e.ai/chaos.html. Queries require an approved account, and scripted access an API key. It is extended over time and its derived quantities are periodically recomputed, so values retrieved from it may differ from the extract deposited here. Where they differ, the extract in this repository is the record for the published results. The released distortion fields are weighted at 0 K or 300 K and the deposited ones at 1200 K, so the two are not expected to agree. Until the database's next recompute, its solubility parameters are those of the AFLOW version with the R* error.

Each CHAOS entry has an identifier made of the prefix of the laboratory that calculated it, a colon and 16 hexadecimal digits, such as `s4e:0171c43afba95d07`. The API printed it under the key `auid` when the benchmark was run, and the benchmark records use that name; the API now prints it as `chaos_id`. A query `chaos_id(s4e:...)` or `auid(s4e:...)` returns the entry.

## Reproducing the Figures

`analysis/00_runbook/` holds the scripts in the order they were run: `prepare_cohort.py`, `run_existing_analyses.py`, `run_model_robustness.py`, `prepare_literature_candidates.py`, `assemble_production.py`, `build_workbooks.mjs` and `verify_and_manifest.py`, then `update_solubility_parameter.py` (2026-10-05) `rerun_20261007.py` (2026-10-07) and `run_tableS4_and_text_checks.py` (2026-10-10). On 2026-10-07 the runbook scripts were adjusted to the reduced tables.

Folders `01_` through `14_` each contain `input/`, `code/` and `output/`, and in folders `01_` to `09_`, `11_` and `14_`, `run_metadata.json` records the script hashes, the command and the exit status. To rerun one analysis, copy its script and invoke it with `--input input/locked_493.xlsx --outdir output` in a new directory rather than overwriting the archived outputs. The Figure 7 models use five-fold out-of-fold splits with random state 42. With scikit-learn 1.6 or later, run them through `analysis/00_runbook/legacy_gkf.py` to get the folds of the production run.

`analysis/13_summary/output/final_metrics.csv` lists every number reported in Figures 6 and 7 and in the text that describes them, and `before_after_manuscript_numbers.csv` records what each was before the cohort was locked. `analysis/14_tableS4_and_text_checks/` holds the models of Table S4 and the counts the text reports beside Figure 7d and Table S3. Figures 2 to 4 were plotted from the 503-row prepared table, `raw_input/data_1002_delete_cf88_227.xlsx`, with the solubility parameter of `solubility_parameter/data_1002_delete_cf88_227_solubility_updated.xlsx`. The solubility-parameter entries of Figures 2b and 4b are in `solubility_parameter/correlations_figures_2b_4b.csv`. Figure 5 plots the same 503 rows; `figure5_pca/README.md` gives its tables and the script that computes them.

The package was first run on 2026-09-25 with the archived solubility parameter. On 2026-10-05, `analysis/00_runbook/update_solubility_parameter.py` replaced that column of the locked cohort with the recomputed values and reran every analysis that reads the cohort; the numbers in `final_metrics.csv` are from that rerun.

On 2026-10-07, the deposit was reduced to the quantities the manuscript reports. Columns and analyses that the manuscript does not use were removed from the tables, workbooks and scripts, `raw_input/` was reduced to the 503 prepared rows, and `analysis/00_runbook/rerun_20261007.py` reran the analysis package on the reduced cohort. Every value in `final_metrics.csv` and every retained numeric value of the analysis outputs is unchanged. The SHA-256 values recorded before this date, in `analysis/00_cohort_lock/output/` and `provenance/`, refer to the files as they were then.

On 2026-10-10, `analysis/00_runbook/run_tableS4_and_text_checks.py` added `analysis/14_tableS4_and_text_checks/`, with the models of Table S4 and the counts the text reports beside Figure 7d and Table S3, and `literature_candidates/table_s3_submitted.csv`. Apart from `analysis/README.md`, `analysis/VALIDATION.json` and `analysis/MANIFEST.csv`, no earlier file changed.

`analysis/MANIFEST.csv` gives the size and SHA-256 of all 175 files in that package, and `analysis/VALIDATION.json` records the assertions that were checked. `benchmark/SHA256SUMS.txt` covers the benchmark archive.

## Paths and Host Names

Absolute paths on the machine where the analysis was run have been replaced: the analysis package's own root by `analysis`, and other locations by the placeholders `LOCAL_WORKDIR`, `GROUP_SHARE`, `LOCAL_CLOUD`, `MANUSCRIPT_SOURCE`, `BENCHMARK_ROOT`, `PROJECT_FOLDER` and `LOCAL_HOME`. The laboratory GPU hosts in the benchmark records are named `gpu_node_a` and `gpu_node_b`. Hashes that referred to the edited files, `analysis/MANIFEST.csv` and `benchmark/SHA256SUMS.txt` were recomputed after these replacements. Cell values and numerical results are unchanged.

## Software Notes

The CHAOS entries were generated with a development build of AFLOW carrying the partially-occupied lattice-distortion, solubility and thermodynamic modules. The AFLOW source is available at https://github.com/entropy4energy/AFLOW-src.

`benchmark/MISSING_AND_LIMITATIONS.md` is the authoritative statement of what the benchmark archive does and does not contain. Three components were not recoverable at the time of deposit: the OpenCode configuration and version, the deployed tool schemas as opposed to the runner's reimplementation of them, and the benchmark-time commit identifiers. The archive also records that gold answers are machine-authored rather than independently adjudicated, that no blinded expert grading was collected, and that ten recorded attempts have no archived score.

## Review Status

This repository is prepared for manuscript review. Please see `REVIEW_LICENSE.md` for the review-period reuse statement.
