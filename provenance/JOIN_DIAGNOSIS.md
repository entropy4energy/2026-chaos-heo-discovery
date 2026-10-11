# EFA join diagnosis (read-only audit, 2026-09-24)

## Finding

The advisor's diagnosis is supported by the available files. The merged workbook `chaos_data_with_efa_deed.xlsx` has 503 data rows: 493 four-cation rows (`0.25x` occupancy in `name`) and ten five-cation rows (`0.2x`). Its join columns are only `Metal1`–`Metal4`; there is no `Metal5`. For each five-cation row, those four columns identify an existing four-cation row. The stored `efa_original_row` points to that four-cation composition in `lib5_efa_deed.xlsx` (`raw` sheet). The merged `EFA` values are identical to the source four-cation row and the four-cation row in the merged workbook at full stored precision in **10/10 cases**. This is stronger than agreement to six decimal places.

The ten rows are (Co,Cu,Mn,Ni,Zn)O, (Co,Cu,Mg,Ni,Zn)O, (Fe,Mg,Mn,Ni,Zn)O, (Co,Cu,Fe,Mg,Zn)O, (Ca,Cd,Mg,Ni,Zn)O, (Cu,Mg,Mn,V,Zn)O, (Co,Mg,Sn,Sr,Ti)O, (Fe,Nb,Sn,Ti,V)O, (Mg,Nb,Sn,Ti,V)O, and (Mg,Nb,Sn,V,Zn)O. `join_evidence.csv` gives the merged Excel row, four-metal key, matched parent row, original EFA-sheet row, and every compared value. The five-cation composition is retained in `name`, but the fifth metal is absent from the join key.

The independent raw DFT export `dft_properties.csv` contains a distinct `entropy_forming_ability` value for each of these ten five-cation names. This field is **not** treated here as an interchangeable replacement for the merged `EFA` column: even four-cation values in the two sources may differ slightly, and the processing lineage is not established. The correct five-cation `EFA` values were **not** inferred or inserted.

## What is and is not proved

The workbook contains a demonstrable four-cation-parent misassignment of the merged EFA values in the ten five-cation rows. A join on `Metal1`–`Metal4` explains the complete pattern. The exact original join implementation has not been verified because the identified `merge_efa_deed_data.m` file in the older analysis directory was not readable from the local OneDrive copy during this audit. This note therefore confirms the erroneous match and its likely key failure, not a line-by-line reconstruction of the historical script.

No source workbook, manuscript, figure, or Origin project was changed. Correcting the data requires the original five-cation EFA source records and a composition- or AUID-safe mapping. Any dependent numerical analyses and figures should be rechecked **after** that mapping is supplied; this audit does not silently substitute values.

## Sources and reproducibility

- Merged workbook: `PROJECT_FOLDER/DATA/4.efa_deed/chaos_data_with_efa_deed.xlsx`, sheet `combined`.
- Four-cation EFA source: `PROJECT_FOLDER/DATA/4.efa_deed/lib5_efa_deed.xlsx`, sheet `raw`.
- Independent DFT field: `raw_input/dft_properties.csv`.
- `audit_join.py` is a new read-only **audit** script; it is not claimed to be the original workbook-generation script. Run `python audit_join.py --combined <merged.xlsx> --efa-source <lib5_efa_deed.xlsx> --dft-source <dft_properties.csv> --output join_evidence.csv` with `openpyxl` installed.

