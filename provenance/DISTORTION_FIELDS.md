# Distortion fields in the EFA analysis workbook (2026-09-24)

The merged workbook's five relevant columns map **by exact column name** to `raw_input/dft_properties.csv`:

| Workbook / raw-export field | Meaning in CHAOS schema | Unit shown in schema |
|---|---|---|
| `lat_distortion_misfit_mean` | Mean lattice-distortion misfit over POCC structures | dimensionless |
| `lat_distortion_misfit_stdev` | Standard deviation of that misfit | dimensionless |
| `lat_distortion_relax_distance_mean` | Mean atomic relaxation distance | Å |
| `lat_distortion_relax_distance_stdev` | Standard deviation of atomic relaxation distance | Å |
| `solubility_parameter` | Solubility parameter | not specified in inspected schema |

For each field, the merged workbook's value matches the same-name raw-export value numerically in **503/503 rows** (absolute difference below `1e-12`; see `distortion_match_summary.csv` and read-only `audit_distortion.py`). No further scaling, normalization, imputation, or unit conversion is detectable **between that CSV and this workbook**. This does not exclude processing before the CSV was exported. The MATLAB cleaning script `DATA/1.Raw_data_1002/Clean_Data.m` selects structural subsets and copies numeric columns; it does not document the original AFLUX query fields or temperature suffix.

**Temperature is unresolved from the archived raw export.** The CSV and workbook omit any `_0K` or `_300K` suffix, while the CHAOS schema (`13.CHAOS_README_FILES/20260519/README_AFLOW_CHAOS_SCHEMA.TXT`, entries near lines 3527–3640) defines both temperature variants for these five bases. The current `methods.tex` descriptor table labels the reported fields `_300K`, but that manuscript label alone is not source proof. It would be misleading to certify 300 K, or 0 K, from the files inspected. The original export URL/query, data-extraction script, or a row-level AUID comparison with the two temperature-specific CHAOS fields is required to close this point.

The manuscript methods define the misfit as a structural change between initial and relaxed POCC cells, then describe Boltzmann-weighted mean and standard deviation across supercells. Those scientific definitions are separate from the still-unresolved export temperature. No recalculation was carried out here.

## Addendum (2026-09-26): basis for reporting the fields as 300 K quantities

The temperature question above is closed on the following basis, recorded here rather than by editing the original note.

1. The archived export predates the schema revision that introduced the `_0K` and `_300K` suffixes (schema README dated 2025-12-22). The unsuffixed names are the names the fields carried when the export was made.
2. In the AFLOW source that produced these entries (`aflow_pocc.cpp`, development branch), the lattice-distortion, relaxation-distance and solubility routines take their supercell weights from the preceding `setPOccStructureProbabilities(temperature)` call, and every default temperature in that code path is 300 K. The unsuffixed fields therefore correspond to the 300 K weighting. The 0 K variant was added later, alongside the suffixes.
3. The values in this export do not match either currently released suffixed variant row for row. The mechanism is the mapped-subset renormalization described in the manuscript Methods: the mean and standard deviation are taken over the POCC supercells for which a structure mapping was found, with probabilities renormalized over that subset, and the set of mapped supercells has changed between the export and the current release at unchanged ensemble size (18 supercells in both).

The manuscript reports the fields as 300 K quantities on this basis. No value in the deposited table was recalculated.

## Addendum (2026-10-05): the fields are 1200 K quantities; the solubility parameter is replaced

The 2026-09-26 addendum is withdrawn, recorded here rather than by editing it.

1. Each CHAOS entry stores its POCC output, which lists every derived quantity for a series of temperatures. In all 503 rows of the prepared table, each of the five fields matches the 1200 K block of that output (relative difference below 1e-6); for four rows the misfit mean is the same at every temperature from 600 K up. The fields are 1200 K quantities, and the manuscript Methods now say so.
2. Point 3 of the 2026-09-26 addendum explained the mismatch with the released `_300K` fields by a change in the mapped subset. The released fields are weighted at 0 K or 300 K and the export at 1200 K. They are not expected to match, and the mismatch is no evidence of a change in the mapped subset.
3. The `solubility_parameter` of the export came from an AFLOW version with an error in the per-supercell lattice measure R*. The analysis now uses recomputed values; `solubility_parameter/README.md` gives the definition, and `analysis/00_runbook/update_solubility_parameter.py` records the replacement. The four distortion fields are unchanged.
