# CHAOS-Agent benchmark evidence archive

This archive repackages existing evidence only. No model or database queries were run, no DFT/VASP calculations were started, and no general CHAOS database dump was included. Files 01 to 13 are the thirteen components of the benchmark record. A file marked MISSING records a documented gap, not fabricated contents.

Source: the existing CHAOS-InteractBench data as of 2026-10-05, with the changes listed below.

Counts checked: 60 locked tasks; 49 data questions; 11 decline/clarification questions; 1,452 unique raw attempts; 1,442 unique tidy score rows; 10 raw attempts with no tidy score; 17 later scoring-guard reclassifications.

The 49 data questions are task definitions, not 49 total attempts. The 11 abstention questions retain their recorded per-attempt outcomes in file 03. Prompt, response and error traces and the original tidy scores are in file 08, joined on `run_id`. Original grading and later reclassification are kept separate in file 07.

Files 06 to 08 are `.tar.gz` packages; `tar -tzf FILENAME` lists their contents. The run transcripts hold the raw model output; what CHAOS returned to the models was removed (below). File 04 contains machine-authored structured references rather than independently adjudicated prose answers. See `MISSING_AND_LIMITATIONS.md` before citing performance or deployed-product claims.

## Changes to the source data

AUID is the key under which the CHAOS API printed an entry's identifier during the benchmark; it now prints it as `chaos_id` (top-level README, Relation to the Live Database).

Files 01, 02, 04, 07 and 08 named 59 AUIDs of superseded CHAOS records. On 2026-10-04 each was replaced by the current AUID of the same calculation. CHAOS had kept the old record of each recalculated calculation next to the new one. The same fault had put two records each of Dy8O20Ti4 and La4O12Ti3 into the Ti-O gold of tasks HEO-C-009 and HEO-H-002, and both gold lists were re-ranked without the old records. No score changed, because all 32 answered runs of the two tasks score R = 0 against both the old and the corrected lists.

On 2026-10-05, the scorer in file 06 stopped checking AUIDs against the live CHAOS API, which has required a key since 2026-09-27. It reads `auid_existence_2026-08.tsv`, packed next to it, which lists the 501 AUIDs the benchmark names and whether CHAOS served them during the benchmark (499 served, 2 never in CHAOS). With this table the scorer reproduces the recorded P and H scores of all 1,442 scored runs.

The text CHAOS returned to the models was removed from file 08 because it held 56,357 distinct CHAOS records. Each tool message now gives the length of the removed text and its SHA-256, and for a JSON answer the record count and the field names. The AUID lists of the tool calls are replaced by their lengths. Queries, status codes, timings, model messages, answers and scores are kept, so scoring the edited records gives the same scores for all 1,452 runs. The complete records are kept by the authors.
