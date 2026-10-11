# Solubility Parameter

The analysis uses the solubility parameter

    delta_s = G <R*> var(R*)        (GPa A^3)

where G is the average shear modulus of the constituent cations, and <R*> and var(R*) are the Boltzmann-weighted mean and variance of R*_s over all POCC supercells of the ensemble at 1200 K. For each supercell s, R*_s = (V_s / n_s)^(1/3) is the edge of the cube with the volume per atom of the relaxed supercell. Because R*_s is defined per atom, delta_s is not divided by the number of atoms in the primitive cell.

## What Replaced What

The archived CHAOS export in `raw_input/` carries a `solubility_parameter` column from an earlier AFLOW version. That version combined the supercell as built, in one cell setting, with the relaxed supercell in another (the reduced cell) as if the two shared a basis, so R*_s changed with the cell setting rather than with the relaxation. The archived values are 370 to 1.2 million times the values here (median 3,500), and the two sets rank the 503 systems differently (Spearman 0.26).

The values here were computed from the relaxed supercells of each ensemble. The development version of AFLOW's POCC module computes the same quantity from the same structures, and the two agree to 1e-12 on the ensembles checked. The CHAOS database will serve the corrected values under `solubility_parameter_0K` and `solubility_parameter_300K` after its next recompute.

## Files

- `solubility_parameter_503.csv`: one row per system of the prepared 503-row table (`raw_input/data_1002_delete_cf88_227.xlsx`). Columns: `name` (the CHAOS entry name), `n_supercells` (18 for four cations, 49 for five), `solubility_parameter_1200K` (the value used in the paper), `solubility_parameter_300K` (for comparison with the database's `_300K` field), `solubility_parameter_archived` (the value in `raw_input/`, superseded). Values are rounded to 15 decimals.
- `data_1002_delete_cf88_227_solubility_updated.xlsx`: the prepared 503-row table of Figures 2 to 4 with `solubility_parameter` replaced by the 1200 K value; every other cell as in `raw_input/` (three differ in the last binary digit, from the rewrite).
- `correlations_figures_2b_4b.csv`: Pearson and Spearman coefficients of the 1200 K values with the four distortion descriptors (Figure 2b) and the chemical descriptors (Figure 4b), over the 503 rows.

`analysis/00_runbook/update_solubility_parameter.py` writes the last two files and puts the 1200 K column into the locked 493-row cohort, then reruns the analysis package (see `analysis/README.md`).
