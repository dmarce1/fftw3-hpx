# HPX all-to-all transpose experiment

Copyright 2026 Dominic C. Marcello. GPL-2.0-or-later, like fftw3-hpx.

This frozen bundle compares the unchanged 1024^3 double-complex in-place
FFTW_ESTIMATE benchmark on four exclusive QueenBee nodes, one process per node,
64 FFT workers per process, two warmups and seven samples. The same candidate
HPX executable runs with `FFTW_HPX_TRANSPOSE_EXCHANGE=pairwise` and `all_to_all`.
Only the global redistribution changes; local subplans, the benchmark driver,
FFTW core and FFTW thread archive are preserved. The MPI executable is the exact
previous control. HPX itself is unchanged.

The six-case order is MPI, HPX pairwise, HPX all_to_all, HPX all_to_all repeated,
HPX pairwise repeated, MPI repeated. All HPX cases retain the 10 ms idle-backoff
cap. Eight rank-level communication passes and four small correctness runs are
required before the primary cases. The validator requires all 42 timed samples,
18 primary numerical checks, 12 preliminary numerical checks, matching local
plans after removing only the exchange suffix/backend prefix, four 64-worker
ranks, and actual per-rank collective call counters.

The allocation builds only the bridge and transpose replacement objects and
links the unchanged driver. Archive-member hashes prove all other objects are
preserved. All input, reused binary, dependency, HPX installation, source-overlay
and output hashes are verified before and after execution. The HPX installation
has TCP compiled out; runtime disables TCP, selects MPI bootstrap/transport, and
uses Open MPI 5.0.11/UCX `rc,sm,self` for both implementations.

HPX's current all_to_all implementation centralizes the packed matrix on the
communicator root. The full exclusive-node memory request accommodates this;
node inventory records physical memory and the owner must collect step MaxRSS
once with final scheduler accounting. No Slurm polling loops are included.
Each primary/small FFT invocation has a 900-second timeout; communication gates
have 180 seconds, with TERM followed by KILL after 30 seconds. Failures retain
logs and FINAL_STATUS. The job's CURRENT_STAGE can be read through the already
authorized persistent SSH connection without another login.

Run the sibling `prepare.py` only after local source/tests are ready. It freezes
the four relevant HPX sources plus the unchanged driver/parser, writes source
hashes and a diff, and makes `alltoall_bundle.tar.gz`. The owner stages it as
`/work/dmarce1/fftw3_hpx_remaining_20261023/alltoall`, verifies SHA256SUMS, and
submits `job.sbatch` once. This harness never opens an SSH connection, sends
email, changes HPX, polls Slurm, or alters prior benchmark artifacts.
