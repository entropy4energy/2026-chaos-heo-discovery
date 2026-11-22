# Figure 5 Data

Figure 5 plots the 503 rows of the prepared table, `raw_input/data_1002_delete_cf88_227.xlsx`, the same rows as Figures 2 to 4. Panels a and b plot the Ghosh size mismatch against the Ghosh electronegativity mismatch, panels c and d the first two principal components of the 19 chemical descriptors, and panel e the magnitudes of the loadings on PC1. The mean lattice misfit and its standard deviation are the color variables of panels a and c and of panels b and d.

- `pca_scores.csv`: one row per system. `delta_electronegativity_Ghosh` and `delta_radii_Ghosh08` are the coordinates of panels a and b, `PC1_score` and `PC2_score` those of panels c and d, and the two misfit columns are the colors. `imputed_descriptors` counts the descriptors of the system that were missing from the table.
- `pca_loadings.csv`: the loadings of the 19 descriptors on PC1 and PC2, ordered by the magnitude of the PC1 loading as in panel e. `figure_label` is the label of the bar; in the radius labels, "vdw" and "Pauling" denote periodic-table atomic and covalent radii.
- `pca_variance.csv`: the variance explained by each of the 19 components.
- `figure5_pca.py`: computes the three tables from the prepared table. `python3 figure5_pca.py --check` recomputes them and compares with the files (pandas, NumPy and openpyxl).

Only the 19 chemical descriptors enter the analysis. Nine Tc-containing systems lack the Pearson electronegativity mismatch, the Saxena radius mismatch and the Saxena Λ, and these 27 values are replaced by the mean of their descriptor before the analysis; the prepared table keeps them empty. Each descriptor is standardized with its mean and population standard deviation, and the standardized matrix is decomposed by singular value decomposition. PC1 and PC2 explain 52.9% and 9.8% of the variance.
