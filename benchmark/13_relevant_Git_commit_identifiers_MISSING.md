# Benchmark-time Git commit identifiers: missing

No frozen commit manifest or `.git` history was present in the inspected benchmark archive. The model `checkpoint_revision` values in `systems.yaml` identify weights, not the Git state of the benchmark runner, chaos-agent, chaosgpt, chaos-mcp, or OpenCode/configuration at execution time. Current repository HEAD values would not prove the benchmark-time state and are therefore not substituted here.

Needed to close this gap: the full commit SHA and repository URL for each component actually used, plus the run date or block to which each applies. Identify any uncommitted changes or state that cannot be reconstructed.
