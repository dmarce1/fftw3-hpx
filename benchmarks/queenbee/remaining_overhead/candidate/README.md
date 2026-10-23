<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Candidate comparison: QueenBee job 1125899

This code, documentation and evidence package are GPL version 2 or later; see
[the repository license](../../../../COPYING). Job1125899 completed PASS on
2026-10-23, 08:05:02–08:37:03 UTC, on qbd007, qbd008, qbd043 and qbd044.
The raw numerical logs, sample statistics, plans and all 616 diagnostic rows
were independently recomputed locally after download. All nine runs passed
three numerical checks each; all plans match after changing the HPX prefix to
MPI, and all HPX plans are byte-identical. This package records that completed
job; the later selected-candidate confirmation is a separate experiment.

The seven primary cases, in execution order, were:

| Case | Change | Median forward seconds | Time / MPI |
|---|---|---:|---:|
| MPI | Original FFTW MPI executable | 3.266202833 | 1.000000 |
| pooled_current | Previously validated pooled bridge executable | 4.718505469 | 1.444646 |
| pool_release | Same pool source, explicit release bridge build | 4.138595902 | 1.267097 |
| lean_pool | Release pool with lean HPX | 4.031524612 | 1.234315 |
| parallel_copy | Parallel final receive copy, original HPX | 3.623516321 | 1.109397 |
| hybrid | Posted direct targets with pooled fallback, original HPX | 4.039347635 | 1.236711 |
| rendezvous | Receiver readiness before transfer, original HPX | 3.583454221 | 1.097132 |

The release pool and all new candidates use `-O3 -march=native -DNDEBUG` for
the bridge and primary driver. Rendezvous's median was 13.41% below the release
pool and 9.71% above MPI in this cohort. Its 1.11% lower median than parallel
copy is a small difference in one fixed-order allocation, not evidence of a
stable ranking across machines or runs. Lean pool was 2.59% below release pool;
lean HPX changes five instrumentation options together, so this does not
identify the cost of one option. Individual sample times and ranges are in
[SUMMARY.json](SUMMARY.json).

Two separate diagnostic runs followed the clean timings. Their medians were
4.771412811 s for hybrid and 3.522780545 s for rendezvous. These include atomic
counters and an extra reporting barrier outside the forward timer and must not
replace clean-case measurements. They establish the receive behavior in those
diagnostic runs:

| Diagnostic | Direct receives | Direct bytes / remote bytes | Final receive copies | Pool hits / misses |
|---|---:|---:|---:|---:|
| Hybrid | 94 / 168 (55.95%) | 94 / 168 GiB | 74 (74 GiB) | 59 / 15 |
| Rendezvous | 168 / 168 (100%) | 168 / 168 GiB | 0 (0 bytes) | 0 / 0 |

Every rendezvous rank/sample pair had exactly six remote loads, six direct hits
and zero final-copy calls/bytes. This is checked for all four ranks and seven
samples, not inferred from aggregate totals. Each diagnostic has exactly
308 unique rows: four ranks × seven samples × eleven metrics. Independent
checks cover both call counts and bytes: remote loads equal direct plus
fallback, owned allocations equal fallback plus self-copy, elided copies equal
direct hits, and final copies equal fallback plus self-copy. Neither run had
unpooled allocation or self-copy in this measured case. Direct hits eliminate
the bridge's final receive copy; they do not establish that the entire MPI/HPX
transport performs no internal copying.

All cases retain the unchanged primary benchmark driver: 1024³ double complex,
in-place normal layout, FFTW_ESTIMATE, four ranks with 64 FFT workers each,
two warmups and seven samples. The timed quantity is the maximum rank time for
each forward transform. Full-spectrum validation and the initial/final
roundtrip checks are outside those timings. Original FFTW serial/thread/MPI
archives remain unchanged; only the HPX bridge object differs among candidates.
Each new archive keeps the other 31 members byte-identical, with original order.
Seven assertion-enabled four-rank/two-worker communication gates passed before
timing, including the expanded rendezvous tests.

Runtime uses the MPI parcelport, forcibly disables TCP, and uses UCX
`rc,sm,self`, original OpenMPI5.0.11, one rank per node, no CPU binding and
`numactl --interleave=all`. MPI and global background-worker limits are one,
multithreaded MPI is enabled, and the idle-backoff cap is 1000 ms. APEX and GPU
hardware discovery are disabled in the environment for every case. All inter-node FFT payloads use MPI/UCX;
HPX TCP is forcibly disabled. Lean binaries resolve all HPX libraries from the
lean installation and MPI from the original MPI installation, with no APEX.
The package was produced without a new login, build or benchmark run.

The baseline source commit was
`4cd4e9b9961bf50295df9eb0b905e0bf45a13659`. Exact frozen source identities are
recorded in [SOURCE_VERIFICATION.json](SOURCE_VERIFICATION.json):

| Source | SHA256 |
|---|---|
| Pool / lean pool | `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c` |
| Parallel copy | `55b88660b9ca905049b197c7d9437864985877cc497152413c40c3204f1e12a9` |
| Hybrid clean | `5a2446f92d48d69d25f16f2b19202e7e03159aab57397c415c3e31f8592ae0cd` |
| Rendezvous clean | `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c` |
| Unchanged primary driver | `9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41` |

The clean and diagnostic sources, patches, driver reference and diagnostic-only
changes are preserved in [the frozen experiment bundle](../experiments/README.md).
All seven downloaded bridge source copies match that bundle and their recorded
cluster artifact hashes. The submitted job/common scripts match the frozen
bundle. Raw `PROVENANCE.json` retains its original preparation-time wording;
the final status and this recomputation establish completed execution.

[raw/1125899](raw/1125899) contains byte-identical benchmark and communication
logs, command files and full command trace, compile/link logs, exported original
and lean flags, runtime/node metadata, archive-member proof, input/artifact
hashes and final statuses. [SOURCE_MAP.json](SOURCE_MAP.json) maps each copy to
the local extraction and records hashes/reasons for all excluded files.
`SHA256SUMS` verifies this published package. Cluster binary/archive hash files
are historical records with original absolute paths; the omitted binaries
cannot be independently rehashed from this text-only package. The Slurm stderr
file is retained, including when empty. Accounting remains a recorded placeholder
for the login owner to supply separately.

Repeated full-plan JSON summaries and the combined stdout copies are excluded
because the raw benchmark logs retain all plans and samples. The two combined
stdout files were byte-identical. Also excluded are duplicate frozen source/
driver copies and CMake's internal metadata-query directory. No executable,
object, archive, shared library, whole FFTW source tree or synthetic fixture is
included. The compact summary is reproducible from the repository root:

```sh
python3 -I benchmarks/queenbee/remaining_overhead/candidate/recompute.py \
  benchmarks/queenbee/remaining_overhead/candidate/raw/1125899 \
  --summarizer benchmarks/summarize.py > /tmp/candidate_summary.json
cmp /tmp/candidate_summary.json benchmarks/queenbee/remaining_overhead/candidate/SUMMARY.json
cd benchmarks/queenbee/remaining_overhead/candidate
sha256sum -c SHA256SUMS
```
