<!--
Copyright (c) 2026 Dominic C. Marcello

This document is free software; you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option)
any later version.

This document is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this document; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
-->

# Lean rendezvous phase measurements: QueenBee 1125966

The unchanged clean lean-HPX executable had a median forward time of
**3.580327051 s**, versus **3.280052551 s** for unchanged MPI: **9.15% longer**
in this allocation. All five cases passed their seven measured samples,
three numerical checks and matching normalized forward/backward plans.
The HPX diagnostic median was **10.91% above its clean control**; the MPI
diagnostic was **0.34% above its control**. Instrumentation and variation with
run order therefore materially limit attribution of the clean-run gap from
diagnostic phase timings.

| Execution order / role | Median (s) | Mean (s) | Minimum (s) | Maximum (s) |
| --- | ---: | ---: | ---: | ---: |
| 1. MPI — primary control | 3.280053 | 3.279977 | 3.233160 | 3.305555 |
| 2. Lean HPX — primary control | 3.580327 | 3.605588 | 3.439282 | 3.990412 |
| 3. MPI — diagnostic | 3.291248 | 3.294719 | 3.260385 | 3.349372 |
| 4. Lean HPX — diagnostic | 3.971094 | 3.875017 | 3.509610 | 4.226856 |
| 5. Unchanged MPI binary, forced MULTIPLE — auxiliary | 3.338921 | 3.329095 | 3.292821 | 3.350823 |

All samples, checks and reductions are in [SUMMARY.json](SUMMARY.json); the
original [compact comparison](raw/1125966/lean_profile_comparison.json) and five
complete benchmark logs are retained unchanged. The auxiliary fifth run does
not replace the primary MPI baseline. A single fixed-order allocation with
seven successive samples is not a randomized comparison and supplies no
confidence interval. Variation between allocations remains relevant.

## What the phase measurements establish

![Critical-rank mean forward decomposition and the HPX exchange phases.](critical_rank_phases.png)

The figure uses the actual slowest rank in each sample, then averages its
components. These arithmetic means add to the mean total; independently chosen
component medians would not. Both diagnostic runs contain 28 rank/sample
records and 38 metrics per record. All 28 HPX exchange partitions have exactly
zero integer-nanosecond coverage error, and the maximum rank time matches the
benchmark's reported time for each sample.

| Mean component on each sample's critical rank | MPI (s) | HPX (s) | HPX − MPI (s) |
| --- | ---: | ---: | ---: |
| Local threaded FFT envelope | 0.794834 | 0.807198 | +0.012365 |
| Pairwise local copies | 0.984774 | 0.985280 | +0.000505 |
| Pairwise allocation and release | 0.000884 | 0.000975 | +0.000091 |
| Inclusive exchange | 0.309919 | 0.892839 | +0.582920 |
| Remaining forward work | 1.204308 | 1.188725 | −0.015583 |
| Total | 3.294719 | 3.875017 | +0.580298 |

Thus the diagnostic mean difference is accounted for by the larger inclusive
exchange, with a small offset from other work. This is an elapsed-scope
comparison, not a measurement of pure network transfer time. The residual
includes serial work, uninstrumented transpose work and instrumentation costs;
it must not be called exclusively serial transpose time.

Within the HPX exchange mean of 0.892839 s, peer readiness accounts for
0.431114 s, incoming completion for 0.388283 s, outgoing completion for
0.066587 s, and the other five phases together for 0.006855 s. Readiness
contains waiting and validation: it cannot distinguish a late peer FFT from
transport or runtime progress delay. The maximum readiness duration across
ranks varied from 0.085212 s to 0.847801 s across samples. That observation
supports examining the readiness/progress path; it does not identify idle
backoff as the cause.

All **168 of 168** message loads required and obtained posted receive targets,
covering 168 GiB across all ranks and samples. There were zero owned receive
fallbacks, pool allocations and final receive memcpy calls in these measured
forwards. The source-backed conditions for MPI receiving into the posted
destination are documented in [parcelport_path.md](../parcelport_path.md).
This removes those measured application copies; it does not establish that
MPI/UCX internally performed no staging or copying.

Task CPU sums on the critical ranks were similar (48.986 s MPI and 49.015 s HPX).
Whole-process CPU time was higher in HPX (122.856 s versus 51.482 s), which
includes runtime/progress work. These overlapping CPU observations are not added
to the disjoint wall-time components and do not by themselves identify the
cause of the elapsed gap. Task/queue/pool/local-child durations are likewise
nested observations. The complete original
[profile analysis](raw/1125966/profile_analysis.json) retains every rank row,
actual critical-rank choices, readiness maxima and same-index component deltas.

## Workload, thread-level control and provenance

All cases used the unchanged 1024³, double-complex, in-place, normal-layout
`FFTW_ESTIMATE` driver, two warmups, seven measured forwards, and full-spectrum
plus initial/final roundtrip checks. The maximum relative error was
`5.9257913899479424e-15` against tolerance `1e-10`. The four nodes were `qbd002`,
`qbd007`, `qbd008`, and `qbd009`; each ran one rank with 64 workers and
`numactl --interleave=all` without MPI or HPX CPU binding. Both HPX runs retained
`sendimm=0`, 1000 ms idle cap, one MPI background worker, one global background
worker, MPI multithreading, and TCP disabled. Exact commands and the
[runtime configuration](raw/1125966/runtime.txt) are preserved.

The normal probe requested and received `MPI_THREAD_FUNNELED` on all four ranks,
with `OMPI_MPI_THREAD_LEVEL` unset. The forced probe requested FUNNELED but
received `MPI_THREAD_MULTIPLE` with the process-local environment override `3`.
The fifth benchmark used the exact original MPI binary and command plus that
same override. Its median was 1.79% above the normal MPI median in this fixed
order; this alone does not explain the 9.15% primary gap. The fresh probe does
not establish the provided thread level of historical jobs.

Both diagnostic executables rebuilt the same new recorder/header ABI. In copied
archives, HPX changed exactly bridge and pairwise members (30 of 32 unchanged),
MPI changed only pairwise (31 of 32 unchanged), and the thread archive changed
only its worker member (8 of 9 unchanged). All loose object hashes agree with
the replaced archive members. The core archive and clean executables remained
unchanged. Two assertion-enabled communication gates passed at four ranks ×
two workers before timing. Loader checks selected the isolated lean HPX and
original OpenMPI 5.0.11 prefixes, without APEX.

All 45 recorded stages passed. Final status is PASS/exit zero and scheduler
stderr is empty. The job verified 25 fixed inputs, three reused binaries,
13 generated artifacts and 166 prior receipts before/after execution.
[SOURCE_VERIFICATION.json](SOURCE_VERIFICATION.json) checks the frozen input
copies, transformation hashes and seven reused receipts against the published
[1125925 evidence](../confirmation/README.md). The clean bridge remains
`cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`, the diagnostic
bridge is `2ea7e60fb8fec7383f8a86b898e4364d82fa1190038be9cba633321484383e13`, and
the clean driver is `9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41`.
Accounting was pending at packaging; its original note is retained.

## Reproduce the published evidence

The exact 25-file [input bundle](inputs/lean_profile/README.md), five benchmark
logs, eight rank logs, individual build/launch commands, probe/loader records,
archive proofs, transformation patch and all preservation checks are included.
[SOURCE_MAP.json](SOURCE_MAP.json) records 152 byte-identical copies and six
omitted duplicate/xtrace logs with hashes. Combined analysis logs reconstruct
exactly from each benchmark log followed by rank files 0–3. Binaries, objects,
archives and full source trees are omitted; their hashes are cluster receipts,
not local rehashes of absent artifacts. The downloaded archive SHA-256 is
`d40f45c489043c2c1aca5e50751882ed639a996aa412ee877dd71fe9d8e6ad0b`.

From this directory:

```sh
sha256sum -c SHA256SUMS
(cd inputs && sha256sum -c lean_profile/SHA256SUMS)
(cd inputs/lean_profile/profile && sha256sum -c TOOLS_SHA256SUMS)
python3 -I recompute.py > /tmp/fftw_lean_profile_summary.json
cmp SUMMARY.json /tmp/fftw_lean_profile_summary.json
```

Recomputation independently parses the five raw cases and commands, checks
provenance receipts and reconstructs both diagnostic inputs in a temporary
directory. It runs the frozen analyzer and compares its output with the
original, allowing only `5e-15` absolute floating-point roundoff. Local Python
3.14 versus cluster Python 3.6 differed in 59 derived values by at most
`4.440892098500626e-16` seconds; raw integer counters and nanosecond identities
match exactly. No FFT, build or remote operation is run.

Regenerate PNG/SVG with `python3 plot_phases.py` (Matplotlib required). Local
profiler correctness evidence is separately published in
[rendezvous_profile_validation](../rendezvous_profile_validation/README.md).
All new package code, notes, summaries and figures are GPL-2.0-or-later.
