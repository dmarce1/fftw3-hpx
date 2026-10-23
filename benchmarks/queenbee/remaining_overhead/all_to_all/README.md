<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# QueenBee all-to-all transpose comparison, job 1126247

Replacing the scheduled pairwise exchange with HPX `collectives::all_to_all`
made the unchanged 1024³ FFT substantially slower. The all-to-all medians were
**12.786193686 s** and **12.804769315 s**, compared with **3.498045230 s** and
**3.499442670 s** for HPX pairwise and **3.352854357 s** and **3.371002973 s**
for FFTW-MPI. Across both repetitions and controls, all-to-all took
**3.65–3.66×** the pairwise time and **3.79–3.82×** the FFTW-MPI time.
The default remains pairwise; the collective path remains an opt-in experiment.

| Case, in execution order | Median FFT time (s) | Range (s) |
|---|---:|---:|
| FFTW-MPI opening control | 3.352854357 | 3.254188–3.381917 |
| HPX pairwise | 3.498045230 | 3.476965–3.652772 |
| HPX all-to-all | 12.786193686 | 12.684345–12.839264 |
| HPX all-to-all repeated | 12.804769315 | 12.667090–13.695748 |
| HPX pairwise repeated | 3.499442670 | 3.354461–3.532025 |
| FFTW-MPI closing control | 3.371002973 | 3.293651–3.393404 |

The repeated all-to-all median increased by 0.145%, the repeated pairwise
median by 0.040%, and the closing MPI median by 0.541%. The repeated cases
therefore reproduce the large difference in this allocation. This is one
fixed-order workload comparison, not a general scaling result or a complete
isolation of system variation. HPX pairwise remained roughly 4% slower than
FFTW-MPI.

## Workload and controlled changes

Every case used four exclusive physical nodes, one process/locality per node,
64 FFT workers per process, and the unchanged 1024³ double-complex in-place
normal-slab `FFTW_ESTIMATE` benchmark. Each case ran two warmups and seven
timed forward FFTs. Planning, verification, inverse transforms, barriers, and
timing reductions remained outside the timer. Both backends used Open MPI
5.0.11, with MPI/UCX `rc,sm,self`. The HPX TCP parcelport was compiled out
and disabled; HPX itself was unchanged.

Both HPX modes used the same executable and the same 10 ms idle-backoff cap.
The only mode switch was `FFTW_HPX_TRANSPOSE_EXCHANGE=pairwise` or
`FFTW_HPX_TRANSPOSE_EXCHANGE=all_to_all`. The collective mode replaces the
global exchange within the existing pairwise transpose plan, retaining its
local transpose and FFT subplans, block distribution, in-place API, and FFTW
flags. It does not select FFTW's separate out-of-place all-to-all solver.
The `/all_to_all` plan suffix records this intentional exchange change.

The allocated build replaced only `hpx-comm.o` and `transpose-pairwise.o` in
the existing HPX archive. FFTW's core and threaded archives and the original
MPI executable were reused unchanged. The source overlay and archive-member
checks preserve the rest of the source and binaries. The implementation was
published at commit `5d7995a29ed3c3c5610f243b3b343dae56559953`; its exact
frozen source inputs are retained with this report.

## Why the collective is a different communication path

The [bridge](inputs/alltoall/source/hpx/hpx-comm.cpp) packs an owned block for
every destination before writing any receive buffer. It then calls HPX
`all_to_all` and copies the returned blocks into the FFTW destination. This
preserves overlapping and in-place arrays and supports inactive ranks, but
adds packing and unpacking work compared with the current direct-receive
pairwise path.

The audited HPX source is commit
`c9b81b401fbe6ba4a0306feff71d18ef01c71b34`.
Its [communicator creation](https://github.com/STEllAR-GROUP/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/collectives/src/create_communicator.cpp#L145)
creates one communicator component at the root locality. Its
[all-to-all implementation](https://github.com/STEllAR-GROUP/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/collectives/include/hpx/collectives/all_to_all.hpp#L245)
collects each participant's vector there, then returns the corresponding
matrix columns to participants. This centralizes communication and temporary
storage. For this workload, each locality packs 4 GiB and the collective
matrix contains 16 GiB overall, in addition to FFT and transport storage.
Those are structural data sizes, not measured resident-memory peaks.

The timings establish that this implementation is slower for the tested
workload. They do not separately measure how much of the added time comes
from packing, unpacking, allocation, root-locality communication, or
synchronization. This experiment also does not imply that all HPX collective
algorithms, parcelports, or problem sizes have the same performance.

## Validation and provenance

The job's final status reports `PASS`, with all 42 timed samples, 18 primary
numerical checks, 12 preliminary numerical checks, and eight rank-level
communication passes accepted. The normalized forward and backward local
plans match, removing only the exchange suffix and HPX/MPI naming prefix.
Every rank in both all-to-all cases reported 40 actual collective exchange
calls; both pairwise cases reported zero. Exact commands, samples, mode counters,
dependency checks, and source/binary hashes are retained in the
[raw results](raw/1126247/FINAL_STATUS).

[Scheduler accounting](accounting.txt), captured explicitly with `TZ=UTC`,
confirms job 1126247 and all its steps completed with exit `0:0`. The
allocation ran from 2026-10-23 15:14:29 UTC to 15:33:20 UTC on
`qbd[099-100,439-440]`.

Slurm records `52391144K` (about 49.964 GiB) as the batch step's `MaxRSS`.
That is a job-accounting observation, not an isolated memory peak for one
benchmark case or one FFT rank. It cannot establish the all-to-all versus
pairwise memory difference. The raw step records are retained without
converting them into a per-case memory comparison.

The downloaded evidence archive was independently verified with SHA256
`a30e25f6bf66b344572437a9d5d7caba0a2f4c7a0eedf25bf5a652d67f9606ee`.
The packaging check verifies the frozen source overlay, the two replaced
archive members, all other preserved members, raw file bytes against that
archive, and byte-identical regeneration of the timing summary.

Run `python3 -I recompute.py` from any directory to reproduce the summary
from raw logs. `SHA256SUMS` covers the complete evidence package;
`SOURCE_MAP.json` records every copied source and the verified transfer
archive. The [parent report](../README.md) preserves prior comparisons.
The task has used seven of the original twelve authorized QueenBee login
attempts; this results check reused the existing connection.

This code and evidence are licensed under GNU GPL version 2 or later; see
[COPYING](../../../../COPYING). Upstream FFTW notices remain unchanged.
