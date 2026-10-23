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

# Confirmation job 1125925: earlier timing gain was not reproduced

All five cases passed seven timed samples, three numerical checks and matching normalized FFT plans. The original-HPX rendezvous implementation did **not** reproduce the preceding allocation's 9.7% overhead: in this confirmation it was **32.2% slower than MPI** and **2.8% slower than the release pooled baseline**. The same source with lean HPX had **18.1% overhead** against MPI. Adding `sendimm=1` to that exact lean executable made it **2.14 times as slow** as its default setting.

| Case, in executed order | Median seconds | Minimum | Maximum | Median / MPI |
| --- | ---: | ---: | ---: | ---: |
| MPI | 3.277329 | 3.249534 | 3.319075 | 1.0000 |
| Release pooled bridge, original HPX | 4.217723 | 4.011060 | 4.957835 | 1.2869 |
| Rendezvous bridge, original HPX | 4.334013 | 3.882292 | 5.108549 | 1.3224 |
| Rendezvous bridge, lean HPX | 3.869754 | 3.625488 | 4.068316 | 1.1808 |
| Same lean executable, `sendimm=1` | 8.298037 | 8.202337 | 8.333456 | 2.5320 |

The selected source was frozen before this run. Both the earlier favorable candidate result and this unfavorable confirmation are retained; see [candidate job 1125899](../candidate/README.md). These are fixed-order cohorts on different allocations, not randomized trials or confidence intervals. Lean HPX changes multiple compiled facilities together. Neither its result nor the large `sendimm` regression identifies a single underlying mechanism.

## Workload and controls

The unchanged [matched driver](raw/1125925/matched_3d.cpp) has SHA256 `9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41`. Each case uses a 1024³ double-complex in-place forward transform, normal slabs, FFTW_ESTIMATE, two warmups and seven timed forward executions. A sample is the maximum rank time. The full-spectrum and initial/final roundtrip checks retain tolerance `1e-10`; planning, synchronization, inverse transforms, normalization and verification are outside the forward timer.

The allocation used qbd007, qbd008, qbd043 and qbd044, one rank/locality per node and 64 FFT workers each. Launches use no CPU binding and `numactl --interleave=all`. HPX uses MPI transport and bootstrap with TCP forced off; both global and MPI background-worker limits are one, MPI multithreading is enabled, and maximum idle backoff is 1000 ms. Open MPI 5.0.11 uses UCX `rc,sm,self`. See [runtime settings](raw/1125925/runtime.txt), [environment](raw/1125925/metadata.txt), [loader environments](raw/1125925/library_environments.txt) and the per-case `.command` files.

The MPI executable, release pooled executable and original-HPX rendezvous executable are reused unchanged from the preceding validated jobs. The lean bridge and driver were compiled with `-O3 -march=native -DNDEBUG` using lean HPX headers and libraries, while keeping the serial/threaded FFTW archives. Only `hpx-comm.o` changed in the copied 32-member HPX archive. The two lean benchmark commands are identical after removing the single `--hpx:ini=hpx.parcel.mpi.sendimm=1` token: both execute the same binary. The [lean build report](../lean_hpx/README.md) describes its compile-time differences; both lean dependency checks confirm the lean HPX prefix, original Open MPI prefix and absence of APEX.

## Correctness, reuse and source proof

[SUMMARY.json](SUMMARY.json) independently recomputes all 35 timed samples, 15 numerical checks, timing statistics and normalized plan comparisons from the five raw benchmark logs. Every paired comparison agrees exactly with the originally emitted JSON; all four HPX plans also match byte-for-byte. Separate four-locality communication gates passed for lean defaults and lean `sendimm=1`, with two workers per locality. The original-runtime candidate's prior communication gates and numerical/plan results were revalidated from the completed job's evidence by [prior validation](raw/1125925/prior_all_checks.log).

The [selected source](raw/1125925/objects/selected_lean/source-hpx-comm.cpp) is byte-identical to the integrated rendezvous bridge, SHA256 `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`. [SOURCE_VERIFICATION.json](SOURCE_VERIFICATION.json) records that comparison, the driver/check-source hashes, the nine frozen input hashes, and the copied prior-job receipts. The [executed job](raw/1125925/job.sbatch), common helper and provenance bytes match the frozen [input bundle](inputs/confirmation/README.md). That bundle preserves its preparation-stage wording; the completed job's result is established by its runtime receipts.

Preservation logs contain all 49 fixed inputs, three reused executables and five new artifacts, plus 85 prior-artifact/dependency/input checks both before and after the job. Ordered archive membership is unchanged and the other 31 members are byte-identical. A second independent source/provenance review confirmed these records. Binary and archive files were deliberately not downloaded into this text-only tree: their hashes remain cluster receipts, not independently rehashed local binaries.

[FINAL_STATUS](raw/1125925/FINAL_STATUS) reports `PASS`, exit zero and stage `complete`; every one of the 29 recorded stages passed, and [Slurm stderr](raw/confirmation-1125925.err) is empty. Final Slurm accounting was intentionally pending at packaging time; the original [pending receipt](raw/1125925/accounting_pending.txt) remains unchanged. Any later batched accounting capture belongs to the [parent report](../README.md).

## Recompute and package contents

From this directory, using Python 3.6 or newer:

```sh
python3 -I recompute.py raw/1125925 --summarizer tools/summarize.py > recomputed.json
cmp SUMMARY.json recomputed.json
sha256sum -c SHA256SUMS
(cd inputs && sha256sum -c confirmation/SHA256SUMS)
```

The raw benchmark logs, commands, communication gates, loader checks, selection, statuses and manifests are copied without modification. The nine frozen input files and their original manifest are preserved under `inputs/confirmation/`. [SOURCE_MAP.json](SOURCE_MAP.json) records every published source path/hash and every exclusion. Repeated full-plan comparison JSON, its aggregate copies and duplicate giant stdout are omitted with their exact hashes; the five benchmark logs already retain every printed plan, and the parser reconstructs all four comparisons. [SHA256SUMS](SHA256SUMS) covers every published file except itself. There are no executables, object files or archives in this package.
