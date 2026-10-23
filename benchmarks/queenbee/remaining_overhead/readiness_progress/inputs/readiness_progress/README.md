<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Prepared readiness backoff comparison

This bundle and documentation are GPL version 2 or later; see repository
`COPYING`. Root alone stages/submits using the existing QB session. Preparation
performs no cluster access, builds or benchmark runs. Stage as
`/work/dmarce1/fftw3_hpx_remaining_20261023/readiness_progress` and verify
`sha256sum -c readiness_progress/SHA256SUMS` from its parent.

The job reuses immutable executables and requires completed PASS jobs1125925
and1125966. Exact expected executable hashes, prior artifact/input/install
manifests, transformed-source provenance and frozen bundle manifests are
verified before and after runs. Prior numerical, plan, communication and profile
checks are recomputed without modifying their evidence. No compilation occurs.

Four exclusive workq nodes use account `loni_graphshpx`, one rank/node64workers,
30 minutes and no mail. Six full1024³ double-complex in-place normal-layout
FFTW_ESTIMATE runs retain two warmups, seven samples and all numerical checks:

1. `mpi_start`: original unchanged MPI binary.
2. `lean_baseline1000`: unchanged clean lean rendezvous, backoff cap1000ms.
3. `lean_backoff10`: that same binary, only the cap changed to10ms.
4. `lean_baseline1000repeat`: that same clean cap1000ms control again.
5. `mpi_end`: the same original MPI binary again.
6. `hpx_profile10`: unchanged job1125966 diagnostic HPX binary, cap10ms.

All HPX cases retain explicit sendimm0, MPI/global background limits1,
MPI multithreading1 and default idle-loop threshold200000. All FFT payload
transport uses MPI/UCX `rc,sm,self`; TCP is forcibly disabled. Placement remains
one rank/node without binding and `numactl --interleave=all`. Lean loader paths
are isolated and audited. APEX and GPU discovery remain disabled. The inherited
MPI thread-level environment is recorded and preserved, including if already
set. The job neither forces MULTIPLE nor changes the original MPI baseline.
The identical clean assertion-enabled checker runs4ranks×2workers at caps1000
and10 before timing.

The last run writes four rank logs outside the timed phase. The frozen analyzer
is invoked with only that new HPX analysis log, validating all38metrics,28rank
samples, exact disjoint phase coverage and numerical/plan identities. Its
normalized plan hashes must match this job's clean cap10 control. Output reports
absolute within-run critical-rank phase means/medians and readiness tails; no
prior-allocation MPI profile is supplied or presented as a paired comparison.
The diagnostic remains separate from the five primary controls, with its own
perturbation ratio against clean cap10. Instrumentation can change scheduling.

Full commands, case table, raw/rank/analysis logs, source and archive provenance,
pre/post hashes, node metadata, MPI bookends, repeated clean baseline and failure
statuses are retained. `readiness_progress_comparison.json` validates42samples,
18numerical checks, all plans and both communication gates. A single fixed-order
cohort does not remove temporal variation or establish a performance gain.
Accounting is left for root's later single query; there is no Slurm polling.

Preparation checks: shell syntax and Python3.6 grammar PASS; prior1125966 checks
reproduced against downloaded real evidence; analyzer/result-wrapper wiring
passed a temporary fixture mapping old logs into the new case names. That fixture
was not a new runtime experiment and is not packaged. Independent script review
is requested before submission. Frozen prior bundles and production code are
unchanged.
