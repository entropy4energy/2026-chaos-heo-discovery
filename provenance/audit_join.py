#!/usr/bin/env python3
"""Read-only audit of the ten five-cation rows in the EFA merge.

This is an audit script, not the (currently unavailable) original merge script.
It never edits an input workbook. Requires openpyxl.
"""

import argparse
import csv
from pathlib import Path

from openpyxl import load_workbook


FIELDS = ("EFA",)


def table(path, sheet):
    ws = load_workbook(path, read_only=True, data_only=True)[sheet]
    rows = ws.values
    header = next(rows)
    return [(number, dict(zip(header, values))) for number, values in enumerate(rows, 2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined", type=Path, required=True)
    ap.add_argument("--efa-source", type=Path, required=True)
    ap.add_argument("--dft-source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    combined = table(args.combined, "combined")
    efa = dict(table(args.efa_source, "raw"))
    with args.dft_source.open(newline="") as handle:
        dft = {row["name"]: row for row in csv.DictReader(handle)}
    parents = {}
    for row_number, row in combined:
        if "0.25x" in row["name"]:
            parents[tuple(row[f"Metal{k}"] for k in range(1, 5))] = (row_number, row)

    records = []
    for row_number, row in combined:
        if "0.2x" not in row["name"]:
            continue
        key = tuple(row[f"Metal{k}"] for k in range(1, 5))
        source_row_number = int(row["efa_original_row"])
        source = dict(zip(
            ("species_0", "species_1", "species_2", "species_3", "species_4",
             "composition_0", "composition_1", "composition_2", "composition_3",
             "composition_4", "element_0", "element_1", "element_2", "element_3",
             *FIELDS),
            list(efa[source_row_number].values())[:14 + len(FIELDS)],
        ))
        parent_number, parent = parents.get(key, ("", {}))
        record = {
            "combined_excel_row": row_number,
            "five_cation_name": row["name"],
            "four_metal_join_key": ",".join(key),
            "parent_combined_excel_row": parent_number,
            "parent_name": parent.get("name", ""),
            "efa_source_excel_row": source_row_number,
            "efa_source_elements": ",".join(str(source[f"element_{i}"]) for i in range(4)),
            "raw_dft_entropy_forming_ability": dft.get(row["name"], {}).get("entropy_forming_ability", ""),
        }
        for field in FIELDS:
            record[f"combined_{field}"] = row[field]
            record[f"efa_source_{field}"] = source[field]
            record[f"matches_efa_source_{field}"] = row[field] == source[field]
            record[f"parent_combined_{field}"] = parent.get(field, "")
            record[f"matches_parent_combined_{field}"] = row[field] == parent.get(field)
        records.append(record)

    if len(records) != 10:
        raise ValueError(f"Expected ten five-cation rows; found {len(records)}")
    if len(parents) != 493:
        raise ValueError(f"Expected 493 four-cation rows; found {len(parents)}")
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)
    print(f"Audited {len(records)} five-cation rows and {len(parents)} four-cation rows")
    for field in FIELDS:
        print(field, "source matches", sum(r[f"matches_efa_source_{field}"] for r in records),
              "parent matches", sum(r[f"matches_parent_combined_{field}"] for r in records))


if __name__ == "__main__":
    main()
