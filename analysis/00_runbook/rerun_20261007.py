#!/usr/bin/env python3
"""Rerun the analyses after the 2026-10-07 removal of unreported fields.

On 2026-10-07 the deposited tables, workbooks and scripts were reduced to the
quantities the manuscript reports: columns and analyses that the manuscript
does not use were removed from the locked cohort, its copies and source
snapshots, and from the scripts that read them; the per-figure scripts of
folders 03 to 05 were renamed accordingly. enthalpy_mix_atom is left empty and
the 36 source systems outside the cohort are removed; every other retained value
is unchanged. This script then

1. records the trimmed scripts in each folder's run_metadata.json (snapshot
   path and SHA-256);
2. reruns folders 01 to 09 and 11 in place, on the cleaned locked_493.xlsx,
   with update_solubility_parameter.py's step_analyses (same folder), so the
   commands, environment, cross-validation folds and path handling are those
   of the 2026-10-05 rerun;
3. reassembles 12_rankings and 13_summary with its step_assemble; and
4. rewrites VALIDATION.json and MANIFEST.csv with its step_verify.

Every number in 13_summary/output/final_metrics.csv and every retained value
of the per-figure outputs is the same as in the 2026-10-05 rerun.

    python3 rerun_20261007.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

RUNBOOK = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("update_solubility_parameter", RUNBOOK / "update_solubility_parameter.py")
usp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(usp)
ROOT = usp.ROOT
NOTE = "2026-10-07, rerun after the removal of fields the manuscript does not report (00_runbook/rerun_20261007.py)"


def record_scripts() -> None:
    for folder in usp.ANALYSES:
        task = ROOT / folder
        path = task / "run_metadata.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        main_script, *helpers = sorted((task / "code").glob("*.py"), key=lambda p: p.name.startswith("efa_screening_common"))
        snapshots = []
        for script in [main_script, *helpers]:
            snapshots.append({"snapshot": str(script.relative_to(ROOT)), "sha256": usp.sha256(script)})
        metadata["script_snapshots"] = snapshots
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def note_rerun() -> None:
    for folder in usp.ANALYSES + ["11_model_robustness"]:
        path = ROOT / folder / "run_metadata.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["rerun"] = [
            "2026-10-05, solubility parameter replaced (00_runbook/update_solubility_parameter.py)",
            NOTE,
        ]
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def verify() -> None:
    usp.step_verify()
    validation = ROOT / "VALIDATION.json"
    result = json.loads(validation.read_text(encoding="utf-8"))
    result["unreported_fields_removed"] = NOTE
    validation.write_text(json.dumps(result, indent=2), encoding="utf-8")
    manifest = ROOT / "MANIFEST.csv"
    lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.startswith("VALIDATION.json,"):
            lines[i] = f"VALIDATION.json,runbook/metadata,{validation.stat().st_size},{usp.sha256(validation)}\r\n" \
                if line.endswith("\r\n") else \
                f"VALIDATION.json,runbook/metadata,{validation.stat().st_size},{usp.sha256(validation)}\n"
    manifest.write_text("".join(lines), encoding="utf-8")


def main() -> None:
    record_scripts()
    usp.step_analyses()
    note_rerun()
    usp.step_assemble()
    for path in ROOT.rglob("__pycache__"):
        shutil.rmtree(path)
    verify()


if __name__ == "__main__":
    main()
