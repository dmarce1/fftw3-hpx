# Remaining-overhead profiles: job 1125891

Copyright (c) 2026 Dominic C. Marcello

This program and its accompanying notes are free software; you can redistribute
them and/or modify them under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the License, or
(at your option) any later version. They are distributed in the hope that they
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
License for more details. You should have received a copy of the GNU General
Public License along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

The completed diagnostic cohort identifies exchange as the main remaining
elapsed-time difference. It does not show a slower FFT worker phase or sustained
receive-buffer allocation churn. The final HPX receive copy is a concrete
remaining cost; the other exchange scopes combine transport, progress and
scheduling and cannot be called pure network time.

The [job status](1125891/FINAL_STATUS) is PASS, exit 0. All five cases completed
seven samples and three numerical checks each; their normalized forward and
backward plans match. The largest recorded relative error was
5.93e-15, below the unchanged 1e-10 tolerance. Each diagnostic run contains all
784 metric records and 28 rank/sample totals. The analyzer verified that each
reported SAMPLE equals the largest elapsed rank for that sample, with no pending
or late scopes, no nested job envelopes and no separate send/receive scopes.

## Exact additive mean decomposition

For each repetition, select its actual slowest rank and take every component
from that rank. Average those seven component values. This preserves additivity:
the components sum to the mean of the seven max-rank forward times. Independent
component medians are never summed.

| Disjoint component, seconds | MPI mean | HPX pooled mean |
| --- | ---: | ---: |
| FFTW worker phases | 0.812956 | 0.799517 |
| Pairwise staging copies + allocation/free | 0.998708 | 1.024521 |
| Exchange excluding final receive copy | 0.320390 | 0.565287 |
| Final receive copy | 0 | 0.572967 |
| Unattributed residual | 1.212394 | 1.202874 |
| **Total** | **3.344448** | **4.165165** |

Exact values and the selected rank for every sample are in
[analysis_summary.json](analysis_summary.json). Rounded table values may differ
in the final displayed digit when added. The
[PNG](critical_rank_decomposition.png) and [SVG](critical_rank_decomposition.svg)
use the exact values.

The mean gap is **0.820718 seconds**. The inclusive exchange means are 0.320390
seconds for MPI and 1.138254 seconds for HPX, a difference of **0.817864 seconds**,
or 99.65% of the mean gap. Other component differences nearly cancel. The final
HPX receive copy alone averages 0.572967 seconds, about 69.8% of that observed
gap. This identifies optimization opportunity; it is not a promised speedup,
because changing reception also changes scheduling, overlap and placement.

Residual is explicitly unassigned: it includes serial FFT work, uninstrumented
transpose work and diagnostic overhead. The separately measured local-child
plan scope overlaps other scopes and is not added again. Likewise, pairwise
chunk, pool, queue and task-body measurements are inclusive or overlapping.

## Descriptive medians and allocation counts

These are component medians from the seven actual critical ranks, not additive
decompositions of the median total.

| Metric, seconds | MPI median | HPX median |
| --- | ---: | ---: |
| Forward max-rank total | 3.339834 | 4.045907 |
| FFTW worker-phase envelope | 0.814012 | 0.803434 |
| Pairwise staging copies | 1.008829 | 1.030398 |
| Inclusive exchange | 0.316094 | 1.032726 |
| Final receive copy | — | 0.569850 |
| Receive wait | — | 0.380499 |
| Referenced-send completion wait | — | 0.086823 |
| Send initiation | — | 0.010897 |
| Job enqueue envelope | 0.000345 | 0.000534 |
| Job join envelope | 0.044625 | 0.030895 |

Receive wait, send completion, initiation and final copy are all inside HPX
exchange. They must not be added on top of exchange or combined as independent
medians to reconstruct it. Every rank/sample receives six 1 GiB payloads.

Across all 28 HPX rank/samples, the cache served **166 of 168 allocations**
(98.81%). There were two misses and two heap deletions, both on sample 0 at
ranks 1 and 2. All later samples had six hits per rank and no misses. No selected
critical rank performed a heap allocation. The two observed heap-allocation
calls took 0.000311489 and 0.000011132 seconds, respectively. This excludes
sustained allocator churn as the main recurring cost in this run; it does not
measure later first-touch page faults or UCX registration independently, nor
establish their contribution to the first-sample outlier.

Observed worker-body CPU totals are similar: critical-rank means of 48.586
CPU-seconds for MPI and 49.110 for HPX. FFTW worker envelopes are also similar,
so these data do not support worker scheduling as the dominant wall-time gap.
Queue-delay sums are larger for HPX (mean 0.098585 versus 0.038299 seconds), but
those delays overlap across tasks and are not added to the envelope.

Whole-process CPU is substantially higher for HPX: critical-rank means of
129.058 CPU-seconds versus 51.113, averaging about 30.99 versus 15.28 occupied
CPU cores during the measured interval. The measured worker bodies explain
little of that difference. This supports extra CPU activity outside those
bodies, but does not separately attribute it to idle polling, parcel progress,
MPI, allocation or another runtime subsystem. Task CPU interpretation is limited
to the audited nonyielding callbacks; all migration and nested-job counters were
zero. A thread-ID check alone is not a general HPX task CPU clock.

## Controls and diagnostic perturbation

All cases ran in the fixed order below within one four-node allocation. Each
used the unchanged 1024³ in-place double-complex transform, four ranks/localities,
64 FFT workers, FFTW_ESTIMATE, two warmups and seven samples. HPX used the MPI
parcelport, TCP disabled, one MPI and one global background thread, multithreaded
MPI, and the 1000 ms idle-backoff cap. Placement was one process per node,
no CPU binding and NUMA interleave across all domains.

| Case, in execution order | Median seconds | Mean seconds |
| --- | ---: | ---: |
| Uninstrumented MPI | 3.354244 | 3.353423 |
| Existing pooled HPX control | 4.049495 | 4.085174 |
| Same pooled source with -DNDEBUG | 4.041729 | 4.265868 |
| Profiled MPI | 3.339834 | 3.344448 |
| Profiled pooled HPX with -DNDEBUG | 4.045907 | 4.165165 |

The profiled HPX median is 0.10% above the same-flags release control; the
profiled MPI median is 0.43% below its control. The release HPX control median is
0.19% below the existing pooled binary. These small differences, with visible
sample variation and fixed order, do not prove zero instrumentation overhead,
an assertion speedup, or statistical significance. Profiling performs clocks
and atomic bookkeeping inside measured work. Reporting is outside the timer,
after the existing max-rank reduction; the driver adds no transform or barrier.
Diagnostic numbers explain this cohort and do not replace primary timings from
other allocations or configurations.

## Failure history and reuse provenance

Job [1125882](1125882/FINAL_STATUS) failed before transformation because actual
QueenBee Python3.6 does not provide `Path.is_relative_to`. Job
[1125884](1125884/FINAL_STATUS) compiled and linked all outputs, then failed
before any benchmark because Python3.6 does not support subprocess `text=True`.
The exact tracebacks, executed scripts and compile/link receipts are retained.
Neither failed job produced benchmark measurements.

The immutable v3 job reused byte-identical copies of job1125884's binaries and
objects without recompilation. Before launching any benchmark it verified the
expected failure, all 16 completed build/instrument/link stages, eight transformed
or generated source hashes, fixed original inputs, HPX flags, and copied artifact
digests. Hashes of the reused artifacts were first recorded at this guarded
reuse step; the failed job had stopped before its final artifact manifest.

The [archive proof](1125891/archive_members.log) verifies unchanged ordered
member sets and exact replacement-object digests: release HPX changes only
`hpx-comm.o` (31 unchanged); profiled HPX changes that bridge and
`transpose-pairwise.o` (30 unchanged); MPI changes only
`transpose-pairwise.o` (31 unchanged); pthreads changes only
`libfftw3_threads_la-threads.o` (8 unchanged). All preservation and input rechecks
passed after the cohort. Slurm stderr files are empty. The package preserves
status and receipts; it does not invent missing scheduler accounting records.

## Contents and reproduction

`1125891/` contains all five raw benchmark logs and launch commands, executed
scripts, environment/node inventory, raw profile/source manifests, complete
archive proofs, reuse hashes and preservation logs. The failed-job directories
retain their original text receipts. `inputs/v1`, `inputs/v2` and `inputs/v3`
preserve the exact successive input bundles; their internal manifests retain
the original remote path spelling. Use the package-wide manifest for this layout.
The v2/v3 C/C++ helpers and transformer are byte-identical. The historical
instrumentation notes under `tools/` describe the scope implementation; their
old relative paths refer to the original working layout.

From this directory, regenerate the validated analysis and figure with:

```sh
python3 tools/analyze.py 1125891/benchmark_mpi_profile.log 1125891/benchmark_hpx_profile.log --json /tmp/fftw_profile_analysis.json
python3 tools/summarize_profiles.py /tmp/fftw_profile_analysis.json
python3 tools/plot_decomposition.py
```

The last command requires Matplotlib. The original analyzer's focused validation
summary and test source are retained; they were already passing and were not
rerun as a broad test suite during packaging. The independent reduction checked
raw log hashes, controls/statistics/plans, critical-rank selection and exact
component sums. The figure was visually inspected.

No executables, objects, archives or full copied source trees are included.
Duplicated full comparison JSON and the verbose successful job log are omitted;
their original digests remain in [SOURCE_MAP.json](SOURCE_MAP.json), alongside
the byte-identical copy map. [SHA256SUMS](SHA256SUMS) covers every published file.
