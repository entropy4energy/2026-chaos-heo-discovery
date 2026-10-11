# CHAOS EFA production analysis: locked 493-system cohort (2026-09-25)

This is a new, additive analysis package. No pre-existing workbook, figure,
Origin project, or manuscript file was changed. The source CHAOS workbook's
ten five-cation rows lack composition-specific verified EFA matches and are
excluded from every production calculation here. No new DFT/VASP calculation
or public release is included.

## Update of 2026-10-05: solubility parameter

The solubility parameter of the locked cohort was replaced on 2026-10-05 by
values recomputed with R* defined per atom (see
`../solubility_parameter/README.md`). `00_runbook/update_solubility_parameter.py`
wrote the new column into `00_cohort_lock/output/`, from the table copied to
`00_cohort_lock/input/solubility_parameter_503.csv`, and recorded the
replacement in `00_cohort_lock/output/solubility_parameter_update.json`. It
then reran folders 01-09 and 11 in place under `00_runbook/legacy_gkf.py`,
which gives the cross-validation folds of the first run on any machine, and
reassembled folders 12 and 13, `VALIDATION.json` and `MANIFEST.csv`. Folder
10 does not read the solubility parameter and was not rerun. Given the
archived column instead, the same script reproduces every metric of the
first run to within 1e-9. The numbers below are from the rerun, made with
Python 3.13, NumPy 2.5, pandas 3.0, SciPy 1.18, scikit-learn 1.9, matplotlib
3.11 and openpyxl 3.1 (exact versions in each `run_metadata.json`); the
first run used Python 3.9.6.

## Update of 2026-10-07: unreported fields removed

On 2026-10-07, the package was reduced to the quantities the manuscript
reports. Columns and analyses that it does not use were removed from the
locked cohort, its copies and source snapshots, and from the scripts that
read them: the analysis scripts of folders 01-09 and 11, the runbook and the
provenance scripts. The scripts of folders 03 to 05 were renamed to match.
`00_runbook/rerun_20261007.py` then reran folders 01-09 and 11 in place with
the functions of `update_solubility_parameter.py`, and reassembled folders
12 and 13, `VALIDATION.json` and `MANIFEST.csv`. Every metric in
`13_summary/output/final_metrics.csv` and every retained numeric value of the
per-figure outputs is the same as in the 2026-10-05 rerun. The
workbook-authoring tool's inspection dump of `locked_493.xlsx` was removed.
The cohort tables keep the column `enthalpy_mix_atom` so that the scripts'
column positions hold, but leave it empty, because the manuscript does not
use it. The deposited EFA source keeps only the 493 cohort systems, so row
numbers such as `efa_original_row` refer to the original 529-system source.
The copies of an earlier manuscript draft in `13_summary/input/`
were removed; they served only as the reference for the line numbers in
`13_summary/output/before_after_manuscript_numbers.csv`. The SHA-256 values
in `cohort_validation.json` and `solubility_parameter_update.json` refer to
the files as they were when those records were written.

## Update of 2026-10-10: Table S4 and text counts

`00_runbook/run_tableS4_and_text_checks.py` created
`14_tableS4_and_text_checks/`. It fits the five models of Supplementary Table
S4 with the archived model API of the Figure 7 analyses and its defaults
(five-fold out-of-fold predictions, random state 42). Three are the DFT-only,
chemistry-only and combined groups; the script checks their metrics against
`13_summary/output/final_metrics.csv` to 1e-9. The other two use element
presence, 15 binary features, one per metal of the cohort, equal to 1 when the
system contains that metal (`output/element_presence_features.csv`), alone or
with the DFT-only group. `output/table_s4_models.csv` gives R², Spearman rho,
ROC-AUC and the number of high-EFA systems among the 50 highest predicted
probabilities. `output/text_checks.json` holds the counts the manuscript
reports beside Figure 7d and Table S3: 71 entries reach a compatibility score
of 0.75 and 49 of them are high EFA; 48 of the 52 priority entries are high
EFA; Table S3 has 6 exact and 37 subset matches, and 40 of its 43 rows lie in
the top EFA quartile; 30 of the 52 priority entries appear in Table S3, and 18
of the other 22 contain Cd. The Table S3 rows are
`../literature_candidates/table_s3_submitted.csv`, the table as submitted. Two
rows that the audit tables of folder 10 list as subset matches,
(Co,Mg,Mn,Zn)O and (Co,Fe,Mn,Zn)O, are exact matches to reported nanocrystals
there. The script then rewrote `VALIDATION.json` and `MANIFEST.csv`; no
earlier output changed.

## Cohort and reproducibility

`00_cohort_lock/output/locked_493.xlsx` is the sole paper-cohort input. Its
`combined` sheet preserves the original column order and the 493 four-cation
rows. Each row has a unique, complete four-cation set, exactly one matching
record in the original EFA source, and a verified EFA value. The ten excluded
rows and source workbooks are retained as
separate provenance inputs. See `cohort_validation.json` for SHA-256 hashes
and assertions. The underlying original 503-row workbook is copied only for
comparison, not used to produce paper figures.

The numbered folders mirror the group's Figure 6 and Figure 7 analyses.
Each has `input/`, `code/`, and `output/`. Folders 01-09 contain snapshots
of the archived analysis scripts, reduced on 2026-10-07 to the analyses the
manuscript reports, and their 493-row outputs. Their `run_metadata.json`
records script hashes, commands, and exit status. Default five-fold out-of-fold modeling settings were retained
and the Figure 7 scripts used random state 42. Run a copied script directly
with `--input input/locked_493.xlsx --outdir output` in a *new* directory if
the analysis needs repeating; do not overwrite this package.

## Contents

| Folder | Content |
| --- | --- |
| `00_cohort_lock` | 493-row workbook, row mapping, 10 excluded rows, source snapshots, validation record |
| `01_fig6a_compatibility` | EFA-percentile versus compatibility-score landscape |
| `02_fig6b_pca` | descriptor-space PCA and loadings |
| `03_fig6c_si_quartiles` | Figure 6c / SI quartiles and Origin-ready worksheets |
| `04_fig6d_distortion` | lattice-distortion correlation matrices |
| `05_fig6d_chemistry` | chemistry-descriptor correlation matrices |
| `06_fig7a_regression` | out-of-fold regression and Figure 7a PNG/PDF |
| `07_fig7b_classification` | ROC/precision-recall data and Figure 7b PNG/PDF |
| `08_fig7c_enrichment` | ranked enrichment data and Figure 7c PNG/PDF |
| `09_fig7d_prioritization` | Figure 7d priority-region data and Origin-ready worksheets |
| `10_literature_candidates` | read-only audit of current SI candidate table: 43 retain, 4 remove |
| `11_model_robustness` | 20 seeds, 30-versus-24 feature identity test |
| `12_rankings` | full 493-system rankings, top-50 lists, 52-system priority list |
| `13_summary` | final metrics, figure-source index, before/after manuscript numbers, overview workbook |
| `14_tableS4_and_text_checks` | Table S4 models, element-presence features, counts reported beside Figure 7d and Table S3 |

The most convenient entry point is
`13_summary/output/CHAOS_EFA493_production_summary.xlsx`.
All figure-source CSVs are in each figure folder's `output/figure_source_csv/`;
the index provides their exact workbook sheet origins. Source workbooks and
editable Origin-ready tables are also preserved, not converted into images.

## Key production checks

The default 493-row models give DFT-only, chemistry-only, and combined
regression R² values of 0.342, 0.537, and 0.595; combined Spearman rho is
0.806. Chemistry-only and combined ROC-AUC are 0.878 and 0.922. Of the top
50 entries ranked by chemistry-only predicted high-EFA probability, 42 are
truly high EFA, a precision of 84.0% and 3.34-fold enrichment; the combined
ranking gives the same 42. The predicted
Figure 7d priority region contains 52 entries, 48 of them (92.3%) high EFA,
against 49 of the 71 entries (69.0%) whose descriptor compatibility alone
reaches 0.75.

Across seeds 0-19, combined R² spans 0.573-0.613, rho 0.797-0.816,
ROC-AUC 0.916-0.932, and top-10% precision 84-92%. With only four-cation
systems, all six configurational-entropy columns are constant. Excluding
them gives 24 rather than 30 combined input columns, with numerically
identical predictions at the documented tolerance in the seed-42 check.

## Interpretation and manuscript cautions

`13_summary/output/before_after_manuscript_numbers.csv` compares the latest
read-only manuscript values, a separately rerun 503-row comparator, and
these final 493-row values. Do not use the 503-row comparator as paper data.
The manuscript's Figure 7d count (56) differs even from the archived
script's direct 503-row recheck (57); use the 493-row result (52) and state
that the precision refers to the *joint* high-EFA/high-compatibility class.
The original Figure 6a helper also parses AFLOW PAW/POCC tags as element
symbols in its `cation_set` and `CHAOS_formula` labels. Its numeric plot
values are unchanged; the exported CSV figure-source sheets replace those
labels with the verified `full_cation_key` and formula from the locked cohort.

`12_rankings` lists the observed EFA next to the out-of-fold predictions.
No manuscript edits or figure replacements were made here.

## Manifest

`MANIFEST.csv` lists every file in this new package, its role, byte size, and
SHA-256 hash, except that the manifest's own self-referential hash is blank.
`VALIDATION.json` records final consistency checks. No files were replaced in
the pre-existing paper directories.
