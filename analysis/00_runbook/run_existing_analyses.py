"""Run unchanged archived analysis scripts on the locked 493-row workbook.

All source files are copied into newly created task folders before execution.
The source hierarchy is read-only; rerunning this wrapper refuses to overwrite
an existing analysis folder.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
PAPER = Path("GROUP_SHARE/PROJECT_FOLDER")
LOCKED = ROOT / "00_cohort_lock/output/locked_493.xlsx"
EFA = PAPER / "8.EFA_DEED/3.figure_EFA"
VALIDATION = PAPER / "11.validation_experiment_EFA_nod2h_noDEED/3. figure"
PRED = EFA / "6.Predictive model/efa_predictive_capability_final/scripts"

ANALYSES = [
    ("01_fig6a_compatibility", [VALIDATION / "fig6a_descriptor_compatibility_vs_efa_package/01_analyze_fig6a_descriptor_compatibility_vs_efa.py"]),
    ("02_fig6b_pca", [EFA / "8.chaos all descriptor PCA/01_analyze_pca_efa_chaos_descriptors_H_L_S_AK.py"]),
    ("03_fig6c_si_quartiles", [EFA / "4.quartile class analysis/01_analyze_efa_dhull_quartile_classes_with_originpro.py"]),
    ("04_fig6d_distortion", [EFA / "2.distortion descriptors correction/01_analyze_efa_dhull_lattice_distortion_correlations.py"]),
    ("05_fig6d_chemistry", [EFA / "3.chemistry descriptors correction/01_analyze_efa_dhull_chemical_descriptor_correlations.py"]),
    ("06_fig7a_regression", [PRED / "panel_a_predicted_vs_observed_logEFA.py", PRED / "efa_screening_common.py"]),
    ("07_fig7b_classification", [PRED / "panel_b_highEFA_ROC_PR_curves.py", PRED / "efa_screening_common.py"]),
    ("08_fig7c_enrichment", [PRED / "panel_c_highEFA_enrichment_lift.py", PRED / "efa_screening_common.py"]),
    ("09_fig7d_prioritization", [VALIDATION / "fig7d_predEFA_descriptor_compatibility_package/01_analyze_fig7d_predEFA_descriptor_compatibility.py"]),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    assert LOCKED.exists(), LOCKED
    for folder, sources in ANALYSES:
        task = ROOT / folder
        if task.exists():
            raise FileExistsError(f"Refusing to replace prior output: {task}")
        code, inputs, output = (task / component for component in ("code", "input", "output"))
        for item in (code, inputs, output):
            item.mkdir(parents=True)
        copied_input = inputs / LOCKED.name
        shutil.copy2(LOCKED, copied_input)
        snapshots = []
        for source in sources:
            assert source.is_file(), source
            destination = code / source.name
            shutil.copy2(source, destination)
            snapshots.append({"source": str(source), "snapshot": str(destination.relative_to(ROOT)), "sha256": sha256(destination)})
        cmd = [sys.executable, str(code / sources[0].name), "--input", str(copied_input), "--outdir", str(output)]
        environment = dict(os.environ)
        environment["MPLCONFIGDIR"] = str(output / "matplotlib_cache")
        print("RUN", folder, flush=True)
        completed = subprocess.run(cmd, cwd=code, env=environment, text=True, capture_output=True)
        (task / "run_stdout.txt").write_text(completed.stdout, encoding="utf-8")
        (task / "run_stderr.txt").write_text(completed.stderr, encoding="utf-8")
        (task / "run_metadata.json").write_text(json.dumps({
            "command": cmd, "returncode": completed.returncode,
            "input_sha256": sha256(copied_input), "script_snapshots": snapshots,
            "python": sys.version, "working_directory": str(code),
        }, indent=2), encoding="utf-8")
        if completed.returncode:
            print(completed.stdout[-2500:], file=sys.stderr)
            print(completed.stderr[-5000:], file=sys.stderr)
            raise RuntimeError(f"Failed: {folder}")
        print("DONE", folder, "outputs", len(list(output.rglob("*"))), flush=True)


if __name__ == "__main__":
    main()
