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

# Receive-storage comparison: job 1125605

The complete job passed, including three assertion-enabled communication gates
before six uninstrumented benchmark runs. Every run uses the unchanged 1024³,
four-rank, 64-worker, double-precision in-place driver with FFTW_ESTIMATE,
two warmups and seven forward samples. All 18 numerical checks pass at `1e-10`,
and normalized forward/backward plans agree across all six cases.

| Variant | Runtime | Median (s) | Median / MPI |
|---|---|---:|---:|
| Stock FFTW MPI | Common placement/UCX controls | 3.305405 | 1.0000 |
| Original HPX | Default progress/backoff | 13.488788 | 4.0808 |
| Serialization-buffer candidate | MPI/global background limits 1; default backoff | 5.698481 | 1.7240 |
| Candidate backoff control | Same limits; backoff 1 | 6.294205 | 1.9042 |
| Pooled receive | Same limits; backoff 1 | 4.364491 | 1.3204 |
| Direct receive | Same limits; backoff 1 | 5.004054 | 1.5139 |

MPI multithreading remains enabled for the selected runtime. Both receive
prototypes must be compared with **candidate_selected_backoff1**, the control
with identical runtime flags. Pooling reduces that control's median by 30.66%;
direct receive reduces it by 20.50%. Changing the candidate's backoff alone
increases its median by 10.45% in this allocation. The default-backoff candidate
therefore is not the isolated receive-prototype comparison control. The original
HPX row also uses different progress settings and is a whole-configuration
reference. [runtime_selection.json](runtime_selection.json) records selection
from the cleanly completed tuning case in the otherwise failed job 1125437.

The runs occurred in the table's fixed order within one allocation on qbd028,
qbd029, qbd053 and qbd054. Processes were unbound, NUMA-interleaved across all
domains, with one process per node. HPX used MPI parcels with TCP forced off;
Open MPI used UCX `rc,sm,self`. These are not randomized trials or confidence
intervals. No direct-receive hit-rate, page-fault or registration counter was
collected. A separate default-backoff follow-up is not part of these results.

## Independent validation

[independent_validation.json](independent_validation.json) records a fresh
local parse of all raw logs: 42 samples, recalculated minimum/median/mean/maximum,
18 finite bounded errors, all plans, matching commands and saved comparisons.
Each of the three communication logs contains four PASS records, two cycles
and seven check categories per cycle; compilation forced assertions, and all
gates finished before timing. They used four ranks and two workers per rank.

Both downloaded prototype archives were re-read member by member: each has 32
unique members, and only `hpx-comm.o` differs from the recorded candidate-member
hashes. The other 31 hashes agree exactly. Frozen source snapshots, bridge
objects, archives and five new executables were rehashed. All three reused
original executables match the primary download. Prototype sources are linked
in [PROTOTYPE_LINKS.json](PROTOTYPE_LINKS.json), avoiding duplicate source copies.

The complete candidate-source manifest equals the primary manifest and has
4,963 post-run OK records. Original library/source and binary manifests also
have complete post-run checks. The original candidate archive and full remote
source tree were not independently downloaded here: their preservation relies
on those authenticated job records. The before-member hashes are recorded
remote evidence; actual after-member hashes were recomputed locally. These
validation layers are distinguished explicitly in the JSON.

## Retained evidence

Raw benchmark, communication and comparison logs are byte-identical, including
full printed plans for plotting and reanalysis. Individual launch/build
commands, the exact executed script, runtime selection, flags, accounting,
status and all source/artifact hash records are included. The concise
`execution_events.log` extracts only START/PASS/final-status lines from the
aggregate job log; its source hash is recorded in `SOURCE_MAP.json`. The
aggregate job log repeats the retained raw logs and is omitted, as are full
shell xtrace, binaries, archives and object files.

`validate_receive_evidence.py` is the GPL audit program used on the original
download. It takes the complete receive result directory, complete primary
result directory, published frozen-prototype directory and output JSON path.
It requires omitted binary artifacts for its binary checks; the publication
subset alone is not that complete input bundle. Verify all published files
with `sha256sum -c SHA256SUMS` from this directory. Original remote hash records
retain their original paths and do not describe only the publication subset.
