<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# QueenBee idle-backoff disable comparison

This frozen bundle reuses the existing MPI and lean direct-receive HPX executables.
It runs the unchanged 1024^3 double-complex, in-place, normal-slab FFTW_ESTIMATE
benchmark with two warmups and seven timed forwards. Four exclusive nodes each
run one process with 64 FFT workers. The ordered primary cases are MPI, HPX with
a 10 ms backoff cap, HPX with backoff disabled, repeated HPX 10 ms, and repeated
MPI. The two MPI runs and repeated HPX setting bracket temporal drift.

For the exact HPX source commit c9b81b401fbe6ba4a0306feff71d18ef01c71b34,
`scheduler_mode::default_` is 3303 and `enable_idle_backoff` is 2048. Runtime
`hpx.default_scheduler_mode=1255` clears only that bit. All three HPX cases use
the same binary and set the 10 ms cap; it is inactive when backoff is disabled.
The same `sendimm=0`, MPI/UCX `rc,sm,self`, one background worker and unbound
NUMA-interleaved placement are retained. TCP is compiled out and forcibly
disabled. No build or source change occurs on QueenBee.

Both scheduler settings first pass the four-locality communication checker.
Prior executable/source/archive checks run before timing, with post-run hash
checks. The result checker validates all 35 samples, 15 numerical checks,
normalized forward/backward plans, commands and communication gates.
Accounting is captured once after the job; Slurm is not polled in a loop.

This package is licensed under GNU GPL version 2 or later; see repository
`COPYING`. It contains no email submission or notification.
