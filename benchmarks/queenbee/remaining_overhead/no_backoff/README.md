<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# QueenBee no-backoff comparison, job 1126034

The unchanged 1024³ benchmark compared the same lean HPX executable with
its idle backoff enabled at a 10 ms cap and disabled entirely. HPX with
backoff disabled measured **3.487117545 s**, -0.052% relative to the first
10 ms control and -13.48% relative to its repeat. Its overhead against
the MPI bookends was **3.80–4.89%**. These are observed medians within
one fixed-order allocation; the repeated controls show temporal variation.
The repeated 10 ms control is 15.515% slower than the first.
This run therefore does not demonstrate a reproducible benefit from disabling
backoff. The documented runtime setting remains the 10 ms cap, and the
remaining HPX/MPI overhead is unresolved.

| Case | Median (s) | Range (s) |
|---|---:|---:|
| MPI opening control | 3.324601818 | 3.283852–3.329731 |
| HPX, 10 ms cap | 3.488932252 | 3.451844–3.576400 |
| HPX, backoff disabled | 3.487117545 | 3.442325–3.754647 |
| HPX, 10 ms cap repeated | 4.030231765 | 3.919144–4.508316 |
| MPI closing control | 3.359598584 | 3.275848–3.387463 |

Every case used four exclusive physical nodes, one rank/locality per node,
64 FFT workers per process, Open MPI 5.0.11 and MPI/UCX `rc,sm,self`.
The HPX TCP parcelport was compiled out and forcibly disabled. The workload
was the same 1024³ double-complex, in-place, normal slab FFTW_ESTIMATE
transform with two warmups and seven timed forward FFTs. Planning,
verification, inverse, barrier and reduction remain outside the timer.
All 35 timed samples, 15
numerical checks, normalized forward/backward plans, and both four-rank
communication gates passed. The original MPI and lean HPX binaries were
reused without rebuilding.

Slurm job 1126034 completed with exit `0:0`. This extension used six of the
original twelve authorized QueenBee login attempts in total.

The exact HPX source's default scheduler mode is 3303. Setting
`hpx.default_scheduler_mode=1255` clears only `enable_idle_backoff`
(bit 2048). The 10 ms cap was passed to all three HPX cases but is
inactive when that bit is clear. All other HPX launch flags are identical,
including `sendimm=0` and one global/MPI background worker. This runtime
comparison does not measure process CPU or prove that backoff caused earlier
timing variation.

The [input bundle](inputs/no_backoff/README.md) records exact settings and
source hashes. [Raw results](raw/1126034/FINAL_STATUS) retain full commands,
per-case samples, validation and pre/post checks. [Scheduler accounting](accounting.txt)
records the completed job. Run `python3 -I recompute.py` from any directory
to regenerate and compare the summary from raw logs. `SHA256SUMS` covers the
full evidence tree; `SOURCE_MAP.json` records each copied source and the
verified transfer archive. The [parent report](../README.md) relates these
results to earlier cohorts and retains the original controls.

The raw `READINESS_PROGRESS_FINAL_STATUS` is a byte-identical copy of
`FINAL_STATUS` with a legacy filename from the reused job harness. It does
not represent another run.

This code and evidence are licensed under GNU GPL version 2 or later; see
[COPYING](../../../../COPYING). Upstream FFTW notices remain unchanged.
