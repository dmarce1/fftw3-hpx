<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Prepared QueenBee candidate comparison

This bundle and its documentation are GPL version 2 or later; see the repository
`COPYING`. It is prepared for root-agent review and staging only. No cluster
build, job submission, execution, remote connection or new login was performed
while preparing it. `PREPARATION_CHECKS.txt` records shell syntax, Python 3.6
syntax/API audits, and synthetic parser acceptance/rejection checks. These do
not establish that the cluster job succeeds.

Stage the complete directory as
`/work/dmarce1/fftw3_hpx_remaining_20261023/candidates`. Its manifest uses paths
relative to that directory's parent, so run `sha256sum -c candidates/SHA256SUMS`
from `/work/dmarce1/fftw3_hpx_remaining_20261023`. The parent must already exist
for Slurm's output files. `job.sbatch` requests four exclusive workq nodes,
one rank and 64 workers per node, account `loni_graphshpx`, 45 minutes and no
mail. Root alone owns submission and the existing shared login budget. Lean
job 1125886 must have a PASS result and valid installed-artifact hashes; it has
no pending Slurm dependency in this script.

All nine runs retain the same unchanged 1024³ workload, in-place normal layout,
FFTW_ESTIMATE planning, 64 FFT workers, two warmups, seven samples, full-spectrum
check and both roundtrip checks. Runtime is MPI parcelport only, TCP forcibly
disabled, UCX `rc,sm,self`, original OpenMPI5.0.11, one rank/node, no CPU binding,
and `numactl --interleave=all`. HPX limits are MPI background workers=1, global
background workers=1, multithreaded MPI=1 and idle-backoff cap=1000 ms. APEX is
disabled in the environment for every case; GPU hardware discovery is disabled.
No cross-server TCP or Slurm polling loop is used.

The fixed run order is:

1. `mpi`: immutable executable from job1125395.
2. `pooled_current`: immutable validated pool executable from job1125605.
3. `pool_release`: same frozen pool source rebuilt with `-O3 -march=native
   -DNDEBUG` against the original installed HPX.
4. `lean_pool`: exactly that pool source and release flags, rebuilt against the
   lean HPX installation. All HPX-consuming C++ objects are rebuilt. The lean
   installation changes five instrumentation options together; a difference
   cannot identify the cost of one option.
5. `parallel_copy`: frozen parallel-copy source against original HPX.
6. `hybrid`: frozen direct-target/pooled-fallback source against original HPX.
7. `rendezvous`: frozen readiness protocol over the hybrid against original HPX.
8. `hybrid_diagnostic`: separate counter library and diagnostic driver.
9. `rendezvous_diagnostic`: its separate counter library and the same diagnostic
   driver.

Only the first seven are primary timings. The diagnostic copies retain the
same transforms and timer boundaries, but atomic counters and reporting can
perturb scheduling and cache state. Their timings must not substitute for the
clean variants. Single fixed-order runs also leave temporal/node effects as a
limitation; comparisons should be reported as this cohort's measured results.

`drivers/matched_3d.cpp` is an exact reference copy, hash-checked against both
current production and original staged source. Every primary build compiles
the unchanged production driver. The diagnostic-only driver uses the actual
private C-linkage declarations in `receive-diagnostics.hpp`. It resets each
locality immediately before the existing sample barrier, reports after the
maximum-time collective, then adds an outside-timer barrier before any inverse
can contaminate another locality's counters. `drivers/diagnostic.patch` records
its complete difference. Each diagnostic log must contain exactly 308 rows
(4 ranks × 7 samples × 11 metrics), without duplicates or missing keys. Counts
and bytes must satisfy remote=direct+fallback, owned allocations=fallback+self,
elided copies=direct, and final copies=fallback+self; no unpooled allocation
is expected in a live epoch. Both message and byte hit fractions are retained.

All bridge builds copy the existing pool archive and replace exactly
`hpx-comm.o`. `check_members.py` requires the other 31 members and their order
to be byte-identical. The original serial, thread, MPI and pool archives are
never rewritten. Original core/thread archives are linked unchanged, including
for lean HPX. Original MPI/pool binaries, previous manifests, input source,
configuration and flags are verified before and after. Each freshly built
bridge receives an assertion-enabled four-rank/two-worker MPI communication
gate before timing. Rendezvous uses its expanded mixed-API/overlap test source;
all other variants use the production communication test.

Lean metadata is obtained inside the allocation using the bundled
`hpx_cmake_flags.py`, GCC13.2, original Boost1.83/hwloc paths and original MPI.
Lean compilation and runtime use subshells to isolate compiler arrays,
exported flags and `LD_LIBRARY_PATH`. Both lean executables must resolve every
libhpx from the lean installation and MPI from the original MPI installation,
with no missing libraries or APEX. Original HPX candidates retain their original
metadata and loader environment.

Outputs live under `results/$SLURM_JOB_ID`. They include raw logs/full commands,
per-stage statuses, node/CPU/NUMA metadata, source provenance, driver patches,
compiled artifacts and hashes, archive-member proofs, lean dependency audits,
per-case numerical/timing/plan summaries, `candidate_comparison.json`, and
`FINAL_STATUS` plus `CANDIDATES_FINAL_STATUS`. The accounting placeholder is for
root to fill with one post-completion query. Failure propagates through
pipelines; PASS requires all gates, comparisons, counter identities and final
input-preservation checks. No benchmark has yet been executed by this bundle.
