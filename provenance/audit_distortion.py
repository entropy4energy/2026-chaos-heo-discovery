#!/usr/bin/env python3
"""Read-only fieldwise comparison of merged and raw DFT distortion values."""

import argparse
import csv
from pathlib import Path

from openpyxl import load_workbook


FIELDS = (
    "lat_distortion_misfit_mean",
    "lat_distortion_misfit_stdev",
    "lat_distortion_relax_distance_mean",
    "lat_distortion_relax_distance_stdev",
    "solubility_parameter",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--combined", type=Path, required=True)
    ap.add_argument("--dft-source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    ws = load_workbook(args.combined, read_only=True, data_only=True)["combined"]
    values = ws.values
    header = next(values)
    rows = [dict(zip(header, row)) for row in values]
    with args.dft_source.open(newline="") as handle:
        raw = {row["name"]: row for row in csv.DictReader(handle)}
    results = []
    for field in FIELDS:
        matched = 0
        missing = 0
        max_difference = 0.0
        for row in rows:
            value = raw.get(row["name"], {}).get(field)
            if value in (None, "") or row[field] is None:
                missing += 1
                continue
            difference = abs(float(row[field]) - float(value))
            max_difference = max(max_difference, difference)
            matched += difference < 1e-12
        results.append({"field": field, "merged_rows": len(rows),
                        "numeric_matches_at_1e-12": matched,
                        "missing_comparisons": missing,
                        "maximum_absolute_difference": max_difference})
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    for result in results:
        print(result)


if __name__ == "__main__":
    main()
