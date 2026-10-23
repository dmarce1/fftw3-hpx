<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Prepared candidate confirmation

This bundle and its documentation are GPL version 2 or later; see the
repository `COPYING`. This is a prepared-only experiment, with no performance
assumption or production integration. No build, remote connection or submission
was performed while preparing it. Static and synthetic parser checks are
recorded in `PREPARATION_CHECKS.txt`; they do not establish cluster success.

Stage the complete directory as
`/work/dmarce1/fftw3_hpx_remaining_20261023/confirmation`. Verify its manifest
from the parent directory using `sha256sum -c confirmation/SHA256SUMS`.
Root alone owns candidate selection, staging, submission and the existing QB
login budget. After inspecting completed job1125899, explicitly select exactly
one of `parallel_copy`, `hybrid` or `rendezvous`, for example:

```sh
sbatch --export=ALL,FFTW_CANDIDATE=rendezvous confirmation/job.sbatch
```

The root selected rendezvous for confirmation after inspecting primary results;
submission remains gated on all of job1125899 passing. This does not assume
that either lean HPX or `sendimm=1` improves its performance. No default, arbitrary
source path, automatic winner selection or shell evaluation is accepted.
`selection.txt` records the chosen name, fixed source path and expected SHA256.
The frozen source is `candidates/prototypes/<selected>/hpx-comm.cpp`; both its
allowlisted hash and its identity to job1125899's compiled source are checked.

The allocation is four exclusive workq nodes, one rank and 64 workers per node,
account `loni_graphshpx`, 30 minutes, no mail. It requires job1125899's complete
PASS status and validates all its artifacts, unchanged inputs, seven
communication gates, numerical logs, timing summaries, plans and both diagnostic
counter audits before compiling or timing anything. The parsers recompute these
checks in a temporary directory without rewriting the completed job. Original
and lean metadata come from that job; no metadata query or dependency rebuild
is required. No Slurm polling or remote access is performed by this bundle.

Exactly five full primary runs execute, in this order:

1. `mpi`: unchanged job1125395 MPI executable, already protected by job1125899.
2. `pool_release`: unchanged job1125899 release-pool executable with original HPX.
3. `selected_original`: unchanged job1125899 executable for the selected source.
4. `selected_lean`: that same source compiled against the existing lean HPX.
5. `selected_lean_sendimm`: exactly the preceding binary/runtime with only
   `--hpx:ini=hpx.parcel.mpi.sendimm=1` added.

Every case uses the unchanged production `matched_3d.cpp`: 1024³, double,
in-place normal layout, FFTW_ESTIMATE, 64 FFT workers, two warmups and seven
samples, full-spectrum validation and initial/final roundtrips. All use the
original MPI5.0.11, UCX `rc,sm,self`, no CPU binding and
`numactl --interleave=all`. HPX uses only the MPI parcelport with TCP forcibly
disabled, MPI/global background-worker limits of one, multithreaded MPI enabled,
and maximum idle backoff of 1000 ms. APEX and GPU hardware discovery are disabled
in the environment for all cases. Cross-server TCP is never used.

Only the selected lean bridge, unchanged driver and assertion-enabled
communication checker are compiled inside the allocation, sequentially. The
bridge uses `-O3 -march=native -DNDEBUG`; the checker ends with `-UNDEBUG`.
The existing release-pool archive is copied before replacing `hpx-comm.o`.
The archive proof requires exactly that member to change and the other 31
members and their order to remain identical. The original serial, thread and
MPI archives and all reused binaries remain untouched.

Lean flags are loaded only inside a subshell from
`results/1125899/lean_metadata/hpx-flags.sh`. Its loader path removes the original
HPX library directories and prepends the lean installation. Both newly linked
executables must resolve every HPX library from lean, every MPI library from the
original MPI installation, and no APEX or missing libraries. The new lean
candidate must pass separate four-rank/two-worker MPI communication tests
with the default runtime and with `sendimm=1`, both before the first timing. Rendezvous selects its expanded frozen communication test; other
candidates use the production test. Each reused original executable has already
passed its communication gate in job1125899.

Outputs under `results/$SLURM_JOB_ID` include full commands/logs, selected source
and driver/checker copies, original/lean flags, input and artifact manifests,
pre/post executable hashes, archive-member proof, dependency audits, node/CPU/
NUMA metadata, all numerical and plan comparisons, `confirmation_comparison.json`
with all medians and ratios, and `FINAL_STATUS`/`CONFIRMATION_FINAL_STATUS`.
Accounting is a placeholder for the sole login owner to fill with one later
query. Pipeline failures propagate; PASS requires all final protection checks.

This is a single fixed-order cohort, so node and temporal effects remain a
limitation. Lean HPX changes five instrumentation options together; its measured
effect cannot be assigned to one option. The preparation makes no claim that any
selected candidate or lean build is faster.
