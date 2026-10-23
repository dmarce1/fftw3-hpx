<!--
Copyright (c) 2026 Dominic C. Marcello

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

-->

# Temporary remaining-overhead diagnostics

This directory instruments a disposable copy of commit `4cd4e9b9961bf50295df9eb0b905e0bf45a13659`, whose pooled bridge SHA-256 is `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c`. This is diagnostic code; the production driver and tracked sources remain unchanged. The original four transformer/helper files remain frozen here. Job 1125882 stopped at transformation because QueenBee's Python 3.6 lacks `Path.is_relative_to`; it produced no diagnostic benchmark evidence. The corrected transfer is `../inputs_v2/profile/`, where the containment check uses `Path.parents`. Its three C/C++ helpers are byte-identical to the compiled originals.

```sh
python3 -I ../inputs_v2/profile/instrument.py /path/to/disposable/source --threads --pairwise
```

Transfer `instrument.py`, `remaining_profile.h`, `remaining_profile.cpp`, and `remaining_mpi_profile.cpp` together. The transformer refuses a Git working tree, linked input files, a different bridge, repeated instrumentation, and missing/ambiguous source anchors. It computes all edits before writing and emits `remaining_profile_manifest.json` with before/after/generated hashes. The snapshot changes only the bridge, driver, pthread loop and two pairwise transpose implementations; it adds the three profile helpers under `benchmarks/`.

The corrected job and exact compiler arguments are in `../inputs_v2/profile_job.sbatch` and `../inputs_v2/common.sh`. Use the existing HPX component/application flags and the matching configured build headers. Compile the shared helper with C++20 and `-pthread`, then link its object directly into both diagnostic executables. Link the PMPI interposer object only into MPI. The helper objects must precede the static libraries. Both new bridges and all diagnostic objects use `-O3 -march=native -DNDEBUG`; assertion-enabled correctness tests are separate.

Replace only these members in copies of the existing archives, using the exact names returned by `ar t`:

| Archive | Replaced members |
| --- | --- |
| HPX | `hpx-comm.o`, `transpose-pairwise.o` |
| MPI | `transpose-pairwise.o` |
| pthread | `libfftw3_threads_la-threads.o` in the current build; derive and verify the name instead of assuming `threads.o` |

The shared serial FFT archive remains byte-identical. Verify archive membership and all other member hashes after replacement; `ar r` with a different filename appends a member and does not replace the existing routines. The `pool_release` control rebuilds the exact uninstrumented pooled bridge with `-DNDEBUG` and the unchanged driver, distinguishing release-flag changes from diagnostic overhead. Original MPI and pooled binaries remain additional controls.

Every case retains the same 1024³ in-place double-complex forward transform, four ranks/localities, 64 FFT workers, `FFTW_ESTIMATE`, two warmups, seven samples, and three analytic/roundtrip correctness checks. The runtime profile is MPI parcelport, TCP force-disabled, one MPI background thread, one global background thread, multithreaded MPI enabled and 1000 ms idle-backoff cap. Driver hooks add no transform, collective, barrier or workload change. Reset occurs before the existing pre-sample barrier, process-CPU sampling immediately before the existing wall clock, and reporting after the existing max-rank reduction. Printing and analysis are outside the timed transform.

## Records and scopes

Every rank emits 28 `PROFILE_DETAIL` records per sample, each with call count, byte count and wall seconds. `PROFILE_DETAIL_TOTAL` reports that rank's original transform duration, process CPU seconds and outstanding/late scope guards. The original `SAMPLE` remains the maximum elapsed rank for that repetition.

| Scope | Meaning |
| --- | --- |
| `exchange_wall` | Full HPX bridge sendrecv or MPI `PMPI_Sendrecv`; the latter cannot expose internal wait phases. Bytes count outgoing user payload. |
| `send_initiation_wall` | HPX channel set, reference/self-copy payload preparation and send initiation. |
| `receive_wait_wall` | HPX channel get plus receive future wait, including asynchronous delivery progress. |
| `send_completion_wait_wall` | HPX outgoing completion future wait after incoming data is ready. |
| `receive_memcpy_wall` | Final HPX received-payload copy into the FFTW user buffer. |
| `pool_allocate_wall`, `heap_allocate_wall` | Pool allocation envelope and nested actual new-array allocation; asynchronous with the foreground wait. |
| `pool_hit`, `pool_miss`, `pool_keep`, `pool_delete` | Allocation/return events and payload bytes. Cache replacement deletion bytes describe the incoming return size; this fixed-block workload uses equal sizes. |
| `pool_deallocate_wall` | Pool return and possible displaced-array deletion. |
| `run_jobs_wall` | Entire HPX callback dispatcher or pthread noncallback dispatch envelope. |
| `enqueue_wall`, `inline_work_wall`, `join_wall` | Dispatch setup/enqueue, caller's final task, and joining other tasks. |
| `task_wall_sum`, `queue_delay_sum` | Sum of actual task-body wall times and queued-to-start delays; tasks overlap. |
| `task_thread_cpu_observed`, `task_cpu_migration` | Thread CPU over task bodies, with cross-OS-thread observations discarded/counted. |
| `nested_jobs` | Concurrent/nested dispatch envelopes; invalidates the simple disjoint decomposition. |
| `separate_send_wall`, `separate_receive_wall` | Unexpected separate bridge send/recv use; invalidates the intended sendrecv-only decomposition. |
| `pairwise_chunks_wall` | Full pairwise chunk exchange routine, including its nested copy/exchange scopes. |
| `pairwise_copy_wall`, `pairwise_allocate_wall`, `pairwise_free_wall` | The identical MPI/HPX pairwise source's memcpy/memmove and temporary FFTW allocation/release operations. |
| `local_transpose_children_wall` | Four local child-plan call sites; these may include threaded work. |

Task CPU is valid only for the audited nonyielding FFTW callback bodies with no nested jobs and no OS-thread migrations. A same-thread resumption after suspension cannot be detected by OS-thread identity alone; these counters are not a general HPX task CPU clock. Full-process CPU remains valid across waits. The pthread worker's task scope includes its queue-counter completion bookkeeping; HPX ends that counter immediately before entering the task scope, a small diagnostic overhead difference.

Only the following wall scopes are disjoint for the verified nonnested forward plan:

```
transform = run_jobs + exchange + pairwise_copy + pairwise_allocate
          + pairwise_free + residual
run_jobs = enqueue + inline_work + join + dispatcher_remainder
HPX exchange = send_initiation + receive_wait + send_completion_wait
             + receive_memcpy + exchange_remainder
```

Residual includes serial FFT work, uninstrumented transpose work and instrumentation overhead. Pool, task, queue, chunk and child-plan times overlap the scopes above and must not be added again. Pool allocation can be large inside receive wait even when final-copy time is small. A receive wait includes scheduling and incoming communication; it is not pure network time. A send-completion wait includes source-lifetime completion, not just MPI progress. These scopes identify where elapsed time occurs without establishing its cause.

## Analysis and validation

```sh
python3 -I analyze.py /path/to/benchmark_mpi_profile.log /path/to/benchmark_hpx_profile.log --json /path/to/profile_analysis.json
```

The analyzer requires all 28 metrics for every rank/sample; seven samples; three passing numerical checks; expected configuration and data size; original sample statistics; exact agreement between each `SAMPLE` and the maximum rank total; no pending/late scopes, nested jobs or separate send/recv calls; nonnegative decompositions; and identical forward/backward plans after replacing `hpx-` with `mpi-`. The JSON retains all rank/sample records, selects each repetition's actual slowest rank, and reports component medians from those ranks. Independently computed medians do not necessarily sum to the median total.

First compare instrumented versus uninstrumented controls to quantify perturbation. Then compare CPU task totals and `run_jobs`/join/queue time, pairwise copies, exchange phases and hit/miss rates. Receive-copy bytes/time yields observed copy bandwidth; process CPU/wall yields average occupied CPU cores. Compare rank imbalance and the actual critical rank rather than adding maxima from unrelated ranks. Do not infer network speed or memory bandwidth from broad wait envelopes.

Local validation completed before the first job: the eight individual objects (bridge, helper, interposer, pthread loop, both pairwise implementations and both drivers) compiled with release flags. Commands and logs are in `compile_check/`. `check_analyzer.py` exercises both backends using explicitly labelled synthetic metric fixtures laid over existing benchmark records: positive cases plus twelve rejected malformed cases per backend. Those fixtures are parser tests, not measured diagnostic evidence. The disposable `transform_check/` helper source was refreshed during compile checking; its earlier generated manifest is not the final transfer manifest. Use the job's fresh `remaining_profile_manifest.json` for provenance.

The v2 job 1125884 compiled and linked all diagnostic outputs, then stopped before any benchmark because `subprocess.check_output(text=True)` is unsupported on Python 3.6. The immutable v3 workflow is `../inputs_v3/`: it uses `universal_newlines=True`, verifies original archive member names and replacement object digests, validates the failed job stage and transformed-source hashes, and reuses copies of the compiled artifacts only after those gates pass. No v1/v2 input files were modified.
