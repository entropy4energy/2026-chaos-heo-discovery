# Missing evidence and qualifications

1. OpenCode configuration and version: not found. File 11 is a missing-item record.
2. Deployed chaos-mcp configuration and exact deployed tool schemas: not found. File 12 contains only the benchmark runner's reimplemented schemas.
3. Benchmark-time Git commit IDs for the runner and relevant CHAOS repositories: not found. File 13 lists what is needed.
4. Two-independent-expert gold answers and prose reference answers: not present. File 04 preserves machine-authored structured gold, AUIDs, and query hashes without claiming independent adjudication.
5. Blinded expert grading: no ratings were collected. Original automatic scores and later 17-row reclassification are in file 07.
6. Ten recorded attempts lack a row in runs_tidy.csv and therefore have no archived score. Their run IDs are listed below.
7. The old by-task README reports 1,382 executions, but 1,452 raw run files and 1,442 tidy score rows are present. The documentation and the ten-run score gap are not reconciled.
8. The source status reports no immutable randomized run_manifest.csv, no stability block, and reduced ablation repetitions. No missing runs were generated here.

## Ten attempts without tidy scores

- `HEO-R-010-A__A3__r1`
- `HEO-R-010-A__A4__r1`
- `HEO-R-011-A__A1__r1`
- `HEO-R-011-A__A2__r1`
- `HEO-R-011-A__A3__r1`
- `HEO-R-011-A__A4__r1`
- `HEO-R-012-A__A1__r1`
- `HEO-R-012-A__A2__r1`
- `HEO-R-012-A__A3__r1`
- `HEO-R-012-A__A4__r1`
