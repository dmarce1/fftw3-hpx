<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Prepared lean rendezvous diagnostic job

This bundle and documentation are GPL version 2 or later; see repository
`COPYING`. Stage it as
`/work/dmarce1/fftw3_hpx_remaining_20261023/lean_profile`, then verify
`sha256sum -c lean_profile/SHA256SUMS` from its parent. Root alone owns staging,
submission and the existing QB login budget. This preparation performs no
cluster access, build or submission. The frozen earlier bundles are unchanged.

The job requests four exclusive workq nodes, one rank and 64 workers per node,
account `loni_graphshpx`, 30 minutes and no mail. It requires completed PASS
job1125925, reproduces its five numerical/plan comparisons, validates both
communication gates and the archive proof, and rechecks all original input,
artifact, installation and frozen-bundle hashes before proceeding.

Five full runs retain the same1024³ double-complex, in-place normal-layout,
FFTW_ESTIMATE benchmark, two warmups, seven measured forwards and three numerical
checks. The fixed order and interpretation are:

1. `mpi`: unchanged original MPI executable from job1125395, primary baseline.
2. `lean_control`: unchanged lean rendezvous executable from job1125925.
3. `mpi_profile`: newly built MPI diagnostic with the current helper/header.
4. `hpx_profile`: newly built lean rendezvous diagnostic with that same ABI.
5. `mpi_thread_multiple`: the unchanged primary MPI executable with only a
   process-specific `env OMPI_MPI_THREAD_LEVEL=3` override; this is auxiliary.

The fifth run never replaces the primary MPI baseline or its headline ratio.
Before timing, a small C probe requests MPI_THREAD_FUNNELED under the inherited
normal environment, then under the explicit3 override. Every rank prints the
requested, provided and MPI_Query_thread levels plus environment. Normal ranks
must agree and match the captured inherited environment; the forced probe must
provide MULTIPLE on all four ranks. The inherited value is never silently
unset. A normal probe already providing MULTIPLE is reported as such. The probe
does not establish the actual provided level in historical runs. OpenMPI's
[documented environment override](https://docs.open-mpi.org/en/v5.0.x/man-openmpi/man3/MPI_Init_thread.3.html)
is used without editing the benchmark source.

Both HPX cases keep cap1000ms, sendimm0, MPI/global background limits1 and MPI
multithreading1. The idle-loop threshold remains the default200000. All FFT
payload transport uses MPI/UCX `rc,sm,self`; HPX TCP is forcibly disabled.
Placement is one rank/node without binding, using `numactl --interleave=all`.
APEX and GPU discovery are disabled in the environment for all cases. Normal
MPI and its diagnostic retain the same inherited thread-level environment.

All compilation occurs sequentially inside the allocation. The instrumenter
operates on a disposable staged-source copy with its bridge replaced by the
frozen clean rendezvous source
`cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`.
The primary driver and original FFTW archives stay unchanged. Both diagnostics
are rebuilt because the metric schema adds ten fields to the prior28; no old
diagnostic executable/object is reused. Only bridge+pairwise members in a copied
HPX archive, pairwise in copied MPI, and the exact pthread worker member in copied
threads are replaced. Ordered names, every other member hash and the loose
replacement-object hashes are verified. The serial/core archive is shared
unchanged. Transformation before/after hashes are checked before and after runs.

Lean flags come from job1125925 and are scoped with an isolated loader path.
All lean executables must resolve HPX from lean and MPI from the original prefix,
without APEX; both MPI binaries must resolve the original MPI prefix with no
HPX or APEX. Clean and newly linked assertion-enabled diagnostic communication
checkers each pass four ranks × two workers before timing. The thread probe is
also compiled and run only in the allocation.

Diagnostic reporting is outside the timer and goes to fresh case-specific
per-rank files via `FFTW_REMAINING_PROFILE_DIR`, preventing launcher stderr
fragmentation. Raw benchmark logs and all eight rank files are preserved; whole
files are concatenated into separate analysis logs. The analyzer checks38metrics
per rank/sample, pending/late scopes, exact integer-nanosecond exchange phase
coverage, message-load identities, full numerics/plans and actual critical-rank
decompositions. Readiness time is elapsed token wait/validation, not pure network
latency. Nested copy/pool/task counters must not be added to the disjoint phases.
See [profile/README.md](profile/README.md) for instrumentation limits and local
validation; those local runs are correctness evidence, not cluster performance.

Outputs include all commands, raw/rank/analysis logs, source/transformation
manifests, before/after input/binary hashes, archive proofs, loader/thread-probe
records, metadata, `profile_analysis.json`, compact `lean_profile_comparison.json`
and `FINAL_STATUS`/`LEAN_PROFILE_FINAL_STATUS`. The compact comparison separates
clean, diagnostic and auxiliary roles and reports perturbation versus each clean
control. Accounting is left for root's single later query. No Slurm polling loop
is used. Pipeline failures propagate and PASS requires final preservation checks.
One fixed-order cohort cannot separate all temporal variation from instrumentation
overhead, and preparation makes no claim about the source of remaining cost.
