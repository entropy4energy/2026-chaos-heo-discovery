#!/usr/bin/env python3
"""Principal-component analysis of Figure 5 from the prepared 503-row table.

    python3 figure5_pca.py           # write the three tables next to this file
    python3 figure5_pca.py --check   # recompute and compare with the tables

Reads raw_input/data_1002_delete_cf88_227.xlsx (sheets "ele descriptors" and
"DFT properties"). The 19 chemical descriptors are the only inputs. A missing
value is replaced by the mean of the finite values of its descriptor, each
descriptor is standardized with its mean and population standard deviation
(denominator N = 503), and the standardized matrix is decomposed by singular
value decomposition. Explained variances are squared singular values divided
by N - 1. The sign of PC1 makes the delta_radius_covalent_PT loading positive
and the sign of PC2 makes the param_geo_radii_Ghosh08 loading positive, which
are the orientations plotted in Figure 5.
"""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "raw_input" / "data_1002_delete_cf88_227.xlsx"

# descriptor, label of the Figure 5e bar
DESCRIPTORS = [
    ("delta_electronegativity_Allen", "delta_chi-Allen"),
    ("delta_electronegativity_Ghosh", "delta_chi-Ghosh"),
    ("delta_electronegativity_Pauling", "delta_chi-Pauling"),
    ("delta_electronegativity_Pearson", "delta_chi-Pearson"),
    ("delta_radii_Ghosh08", "delta_r-Ghosh"),
    ("delta_radii_Pyykko", "delta_r-Pyykko"),
    ("delta_radii_Slatter", "delta_r-Slater"),
    ("delta_radius_covalent_PT", "delta_r-Pauling"),
    ("delta_radius_covalent", "delta_r-Cordero"),
    ("delta_radius_PT", "delta_r-vdw"),
    ("delta_radius_Saxena", "delta_r-Saxena"),
    ("param_geo_radii_Ghosh08", "Lambda-Ghosh"),
    ("param_geo_radii_Pyykko", "Lambda-Pyykko"),
    ("param_geo_radii_Slatter", "Lambda-Slater"),
    ("param_geo_radius_covalent_PT", "Lambda-Pauling"),
    ("param_geo_radius_covalent", "Lambda-Cordero"),
    ("param_geo_radius_PT", "Lambda-vdw"),
    ("param_geo_radius_Saxena", "Lambda-Saxena"),
    ("VEC", "VEC"),
]
SIGN_REFERENCE = ("delta_radius_covalent_PT", "param_geo_radii_Ghosh08")
COLOR = ["lat_distortion_misfit_mean", "lat_distortion_misfit_stdev"]


def analyze() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    chem = pd.read_excel(SOURCE, sheet_name="ele descriptors").set_index("name")
    dft = pd.read_excel(SOURCE, sheet_name="DFT properties").set_index("name")
    assert len(chem) == 503 and chem.index.equals(dft.index)
    names = [d for d, _ in DESCRIPTORS]
    raw = chem[names].astype(float)
    filled = raw.fillna(raw.mean())
    z = (filled - filled.mean()) / filled.std(ddof=0)
    _, s, vt = np.linalg.svd(z.to_numpy(), full_matrices=False)
    for k, ref in enumerate(SIGN_REFERENCE):
        if vt[k, names.index(ref)] < 0:
            vt[k] = -vt[k]
    variance = s**2 / (len(z) - 1)
    scores = z.to_numpy() @ vt[:2].T

    table_scores = pd.DataFrame({
        "name": z.index,
        "PC1_score": scores[:, 0],
        "PC2_score": scores[:, 1],
        "delta_electronegativity_Ghosh": chem["delta_electronegativity_Ghosh"].to_numpy(),
        "delta_radii_Ghosh08": chem["delta_radii_Ghosh08"].to_numpy(),
        COLOR[0]: dft[COLOR[0]].to_numpy(),
        COLOR[1]: dft[COLOR[1]].to_numpy(),
        "imputed_descriptors": raw.isna().sum(axis=1).to_numpy(),
    })
    table_loadings = pd.DataFrame({
        "descriptor": names,
        "figure_label": [label for _, label in DESCRIPTORS],
        "PC1_loading": vt[0],
        "PC2_loading": vt[1],
    })
    table_loadings["PC1_rank"] = table_loadings["PC1_loading"].abs().rank(ascending=False).astype(int)
    table_loadings = table_loadings.sort_values("PC1_rank").reset_index(drop=True)
    table_variance = pd.DataFrame({
        "component": [f"PC{k + 1}" for k in range(len(variance))],
        "explained_variance": variance,
        "explained_variance_ratio": variance / variance.sum(),
    })
    return table_scores, table_loadings, table_variance


def main() -> None:
    tables = dict(zip(("pca_scores.csv", "pca_loadings.csv", "pca_variance.csv"), analyze()))
    if "--check" in sys.argv[1:]:
        for name, new in tables.items():
            old = pd.read_csv(HERE / name)
            assert list(old.columns) == list(new.columns) and len(old) == len(new), name
            for column in new.columns:
                if new[column].dtype.kind == "f":
                    assert np.allclose(old[column], new[column], rtol=0, atol=1e-12, equal_nan=True), (name, column)
                else:
                    assert (old[column] == new[column]).all(), (name, column)
        print("figure5_pca: tables reproduced")
        return
    for name, table in tables.items():
        table.to_csv(HERE / name, index=False)
    ratio = tables["pca_variance.csv"]["explained_variance_ratio"]
    print(f"PC1 {ratio[0]:.4%}, PC2 {ratio[1]:.4%}")


if __name__ == "__main__":
    main()
