<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Prepared receive-progress runtime comparison

This bundle and documentation are GPL version 2 or later; see the repository
`COPYING`. It is a prepared-only bounded runtime experiment. Root owns review,
staging, submission and all QB access. No executable is built or modified.
Stage as `/work/dmarce1/fftw3_hpx_remaining_20261023/progress`, verify
`sha256sum -c progress/SHA256SUMS` from its parent, and explicitly supply the
root-selected setting:

```sh
sbatch --export=ALL,FFTW_SENDIMM=0 progress/job.sbatch
```

There is no default. Only literal `0` or `1` is accepted; root selected `0`
after the preceding sendimm trial. Every lean launch, including communication
checks, receives that same explicit value. No dynamic evaluation or automatic
winner selection is used. The script requires job1125925's completed PASS,
recomputes all its numerical/plan summaries in scratch space, checks its two
communication gates and archive-member proof, and verifies every original
input/artifact manifest before any timing. It preserves the frozen confirmation
and candidate bundles.

The allocation is four exclusive workq nodes, one rank and 64 workers per node,
account `loni_graphshpx`, 30 minutes and no mail. Exactly six primary cases run:

| Order | Label | Executable / runtime |
|---|---|---|
| 1 | mpi_start | Original MPI executable from job1125395 |
| 2 | pool_release | Original-HPX release pool executable from job1125899 |
| 3 | lean_baseline1000 | Job1125925 lean rendezvous, backoff cap 1000 ms |
| 4 | lean_backoff1 | The same lean executable, cap 1 ms |
| 5 | lean_baseline1000repeat | The same lean executable, cap restored to 1000 ms |
| 6 | mpi_end | The same MPI executable as the first run |

The idle-loop threshold remains its audited HPX default of 200000; there is no
`hpx.max_idle_loop_count` override. The only changed setting among the three
lean cases is `hpx.max_idle_backoff_time`. MPI and global background-worker
limits stay one; multithreaded MPI stays enabled. The release-pool control keeps
its original HPX loader and default sendimm=0. Original/lean loader paths are
isolated in subshells. The lean benchmark and assertion checker must resolve
HPX only from lean and MPI from the original MPI prefix, with no APEX or missing
libraries. Both cap settings pass a four-rank/two-worker assertion-enabled
communication gate before the first timing.

Every case uses the unchanged original driver: 1024³, double complex, in-place
normal layout, FFTW_ESTIMATE, 64 FFT workers, two warmups and seven samples. The
same full-spectrum and initial/final roundtrip checks remain outside timing.
All inter-node FFT traffic uses the MPI parcelport/UCX `rc,sm,self`; HPX TCP is
forcibly disabled. Placement is one rank/node, no CPU binding, with
`numactl --interleave=all`. APEX and GPU hardware discovery are disabled in the
environment for every case. No compiler, build or Slurm polling loop is used.

The hypothesis is that a readiness-header wait can reach an idle-backoff path
without an active bulk connection. This experiment tests the cap for the
rendezvous bridge; the earlier pool result does not settle that question.
Neither the hypothesis nor this preparation establishes a speedup. MPI
bookends and the repeated lean baseline expose temporal variation but cannot
remove all fixed-order effects.

`case_table.tsv`, full command files and `commands.log` record the executable
and settings of every case. `progress_comparison.json` is compact: all six
seven-sample sets, medians/ranges, 18 numerical checks, plan hashes, and each
HPX median relative to both MPI bookends. It separately reports MPI end/start,
lean baseline repeat/initial, and cap1 relative to both lean baselines. It does
not pool the control runs into a single number. Raw logs retain full plans.

Outputs also retain selection/provenance, node/NUMA metadata, immutable archive
proofs, source/driver/flags and executable hashes, pre/post verification logs,
and `FINAL_STATUS`/`PROGRESS_FINAL_STATUS`. Accounting is a placeholder for root
to fill after completion with one query. Prior binary/archive files are hashed
in place and never changed. PASS requires all checks and final preservation
checks; pipeline failures propagate. `PREPARATION_CHECKS.txt` records local
static/synthetic checks and independent review, not cluster execution.
