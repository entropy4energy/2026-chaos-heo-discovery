#!/usr/bin/env python3
"""Freeze the composition-verified 493-row EFA paper cohort.

All writes are confined to this new dated production directory. Source files
are read-only. The Excel file is authored separately by build_workbooks.mjs
from the typed JSON produced here.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


PACKAGE = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(
    "LOCAL_CLOUD/"
    "2.S4E_Group/PROJECT_FOLDER"
)
CORRECTED = Path(
    "LOCAL_WORKDIR/outputs/"
    "chaos_efa_join_20260925/chaos_data_with_efa_deed.xlsx"
)
LIB5 = SOURCE_ROOT / "8.EFA_DEED/1.data/lib5_efa_deed.xlsx"
OLD = SOURCE_ROOT / "8.EFA_DEED/1.data/chaos_data_with_efa_deed.xlsx"
MERGED_FIELDS = ["EFA"]
METAL_COLS = ["Metal1", "Metal2", "Metal3", "Metal4"]
ELEMENT_COLS = ["Elements 0", "Elements 1", "Elements 2", "Elements 3"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def key(values) -> str:
    return ",".join(sorted(str(v).strip() for v in values if pd.notna(v)))


def main() -> None:
    input_dir = PACKAGE / "00_cohort_lock/input"
    output_dir = PACKAGE / "00_cohort_lock/output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_excel(CORRECTED, sheet_name="combined")
    legacy = pd.read_excel(OLD, sheet_name="combined")
    source = pd.read_excel(LIB5, sheet_name="cleaned")
    assert len(raw) == len(legacy) == 503
    # the original source has 529 four-cation systems; the deposited copy keeps
    # the 493 of the cohort
    assert len(source) in (529, 493)
    assert len(raw.columns) == 44
    assert raw.columns[:40].tolist() == legacy.columns.tolist()

    source = source.copy()
    source["_key"] = source[ELEMENT_COLS].apply(key, axis=1)
    assert source["_key"].nunique() == len(source), "EFA source has duplicate cation sets"
    lookup = source.set_index("_key")

    locked_mask = (
        raw["cation_count"].eq(4)
        & raw["match_count"].eq(1)
        & raw["Metal5"].isna()
        & raw["efa_join_status"].eq("Exact four-cation match")
    )
    locked = raw.loc[locked_mask].copy()
    excluded = raw.loc[~locked_mask].copy()
    assert len(locked) == 493
    assert len(excluded) == 10
    assert excluded["cation_count"].eq(5).all()
    assert excluded[MERGED_FIELDS].isna().all().all()
    assert locked[MERGED_FIELDS].notna().all().all()
    assert locked["EFA"].gt(0).all()
    assert locked["full_cation_key"].nunique() == 493
    assert locked["full_cation_key"].tolist() == [
        key(row) for row in locked[METAL_COLS].itertuples(index=False, name=None)
    ]
    assert set(locked["full_cation_key"]).issubset(set(lookup.index))

    for field in MERGED_FIELDS:
        from_source = lookup.loc[locked["full_cation_key"], field].to_numpy(dtype=float)
        from_locked = locked[field].to_numpy(dtype=float)
        assert np.allclose(from_locked, from_source, rtol=0, atol=1e-10), field
        from_legacy = legacy.loc[locked.index, field].to_numpy(dtype=float)
        assert np.allclose(from_locked, from_legacy, rtol=0, atol=1e-10), field

    # The scripts depend on positions H:L and S:AK, so preserve original
    # column order. Row order also remains that of the source combined sheet.
    locked.insert(0, "_temporary_original_excel_row", locked.index + 2)
    row_map = locked[["_temporary_original_excel_row", "full_cation_key"]].rename(
        columns={"_temporary_original_excel_row": "source_combined_excel_row"}
    )
    locked.drop(columns="_temporary_original_excel_row", inplace=True)
    locked.reset_index(drop=True, inplace=True)

    for src, name in [
        (CORRECTED, "corrected_503_reference.xlsx"),
        (LIB5, "lib5_efa_deed_source.xlsx"),
        (OLD, "legacy_503_comparator.xlsx"),
    ]:
        shutil.copy2(src, input_dir / name)

    locked.to_csv(output_dir / "locked_493.csv", index=False, float_format="%.15g")
    row_map.to_csv(output_dir / "source_row_mapping.csv", index=False)
    excluded[
        ["full_cation_key", "name", "cation_count", "efa_join_status"]
    ].to_csv(output_dir / "excluded_ten_quinaries.csv", index=False)
    (output_dir / "locked_493_typed.json").write_text(
        locked.to_json(orient="split", index=False, double_precision=15),
        encoding="utf-8",
    )

    audit = {
        "cohort_name": "493 exact-composition quaternary EFA entries",
        "selection_rule": (
            "cation_count=4; Metal5 blank; match_count=1; exact full-cation "
            "set in lib5 cleaned; positive EFA"
        ),
        "n_source_rows": int(len(raw)),
        "n_locked_rows": int(len(locked)),
        "n_excluded_quinaries": int(len(excluded)),
        "n_unique_cation_sets": int(locked["full_cation_key"].nunique()),
        "high_EFA_count": int(
            (
                (locked["EFA"].rank(method="average") - 1)
                / (len(locked) - 1)
                >= 0.75
            ).sum()
        ),
        "config_entropy_unique_counts": {
            c: int(locked[c].nunique(dropna=False))
            for c in locked.columns
            if c.startswith("S_config_")
        },
        "source_paths_and_hashes": {
            str(p): sha256(p) for p in (CORRECTED, LIB5, OLD)
        },
    }
    assert audit["high_EFA_count"] == 124
    assert len(audit["config_entropy_unique_counts"]) == 6
    assert all(v == 1 for v in audit["config_entropy_unique_counts"].values())
    (output_dir / "cohort_validation.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
