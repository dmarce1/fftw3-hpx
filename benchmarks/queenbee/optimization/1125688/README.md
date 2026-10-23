<!--
Copyright (c) 2026 Dominic C. Marcello

This report is free software/documentation; you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This report is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this report; if not, write to the Free Software Foundation, Inc., 51 Franklin
Street, Fifth Floor, Boston, MA 02110-1301 USA.

-->

# Matched default-backoff comparison: job 1125688

The job completed successfully with four unchanged executables and no rebuild
or instrumentation. All four runs use the unchanged 1024³, four-rank,
64-worker, double-precision in-place driver, FFTW_ESTIMATE, two warmups and
seven forward samples. All 12 numerical checks pass at `1e-10`; normalized
forward and backward plans agree across all runs.

| Variant | Median (s) | Median / MPI |
|---|---:|---:|
| Stock FFTW MPI | 3.356002875 | 1.000000 |
| Serialization-buffer control | 5.576087256 | 1.661526 |
| Pooled receive | 4.203216089 | 1.252447 |
| Direct receive | 4.524689387 | 1.348238 |

All three HPX variants use exactly the same runtime options: MPI background
threads 1, global background threads 1, MPI multithreading enabled, and
`hpx.max_idle_backoff_time=1000` (1000 ms). MPI parcels are selected and TCP is
forced off. Open MPI uses UCX `rc,sm,self`. The serialization-buffer candidate
is the matching control for both receive implementations in this job.

Runs occurred in the table's fixed order on qbd028, qbd029, qbd053 and qbd054,
with one process per node, 64 workers, unbound processes and NUMA interleave.
Final accounting reports `COMPLETED`, exit `0:0`, 256 CPUs, and 11m23s elapsed;
all recorded steps completed cleanly and Slurm stderr is empty. This is one
allocation with a fixed run order, not randomized trials or a confidence
interval. The earlier 1 ms-backoff measurements are separate evidence in
[job 1125605](../1125605/README.md).

## Independent validation

[independent_validation.json](independent_validation.json) records an
independent parse of all 28 samples and 12 finite bounded numerical errors,
recalculated minimum/median/mean/maximum, exact saved-comparison agreement,
normalized plans, and identical HPX runtime argument lists. Both raw forward
and backward plans use pairwise distributed transposes for this case.

All 17 reused source, configuration, status and artifact records are byte
identical to the earlier evidence or frozen sources. Eight complete post-run
hash logs cover inputs, binaries, original libraries/sources, the candidate
archive, prototype inputs and both receive artifacts. In particular, the
candidate-source manifest has 4,963 matching post-run OK records. Binary
records match the earlier manifests; a separate read-only audit also checked
them against the previously downloaded executable files.

No binaries were downloaded again in this final text-only bundle. Final-job
preservation therefore relies on its recorded pre/post hash checks; the prior
local binary/archive validation is retained in job 1125605. This job reused
its previously gated artifacts and did not rerun the communication gates.
Frozen [pooled](../receive_prototypes/pooled_receive/hpx-comm.cpp) and
[direct](../receive_prototypes/direct_receive/hpx-comm.cpp) sources are linked
without duplicate copies; their exact hashes appear in
[PROTOTYPE_LINKS.json](PROTOTYPE_LINKS.json).

## Retained evidence

Raw benchmark/comparison logs and individual commands are byte-identical,
including complete printed plans. The exact executed job script, runtime and
benchmark arguments, final status, accounting, metadata and all reused hash
records are retained. `execution_events.log` extracts only complete
START/PASS/final-status lines from the duplicate aggregate job log.
`SOURCE_MAP.json` records each copied source and hash, the event extraction,
and explicit omissions. The downloaded archive independently hashes to
`9e7ac02bac1ae45081e067bd73ef46f4a1dd618be79708dff6163f1d546f92b3`.

`validate_final_evidence.py` is the GPL audit program used on the original
download. Run it from the repository root. Its arguments are the complete
final result directory, published
1125605 directory, frozen-prototype directory, original downloaded archive,
and output JSON path. The original archive and duplicate source snapshots
are omitted from this publication subset. Original remote hash records keep
their original paths. Verify this subset with `sha256sum -c SHA256SUMS` from
this directory.
