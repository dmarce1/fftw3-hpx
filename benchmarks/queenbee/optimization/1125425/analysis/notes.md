<!--
Copyright (c) 2026 Dominic C. Marcello

This report is free software/documentation; you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This report is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this report; if not, write to the Free Software Foundation, Inc., 51 Franklin
Street, Fifth Floor, Boston, MA 02110-1301 USA.
-->

# HPX forward-transform diagnostic analysis: job 1125425

The candidate's measured gain is concentrated in `sendrecv`. Removing outgoing
buffer construction and the vector-return path reduces that phase sharply,
while threaded FFT callback time and the uninstrumented remainder change
little at the default progress settings. Limiting MPI progress to one worker
reduces the remainder and final-copy time, but increases the other time spent
inside `sendrecv`. The result supports further progress and receive-storage
experiments; it does not identify UCX registration or page faults as the cause.

## Provenance and validation

Inputs are the four complete `benchmark_*profile*.log` files under
`../diagnostic_evidence/results/1125425/`. The parent task downloaded and verified
the evidence bundle. This analysis read local files only and ran no benchmark,
build, or remote command. The job's `FINAL_STATUS` is PASS, with completion at
2026-10-23 05:10:18 UTC and baseline commit
`cb205948f773e8e057b14ebbf6fa4df1c7cb994a`.

Each run has four ranks, 64 workers per rank, a double-precision in-place normal
layout 1024 cubed transform, FFTW_ESTIMATE planning, two warmups, and seven
samples. The analyzer verified all 196 PROFILE rows, 28 PROFILE_TOTAL rows, and
seven SAMPLE rows in each run: 784, 112, and 28 records respectively across the
four runs. The maximum of each sample's four per-rank totals equals its SAMPLE
time exactly at the printed precision. All three numerical checks and RESULT
statistics pass. Both normalized forward and backward plans are identical
across runs and match the MPI control according to the accompanying comparison
records.

Each rank/sample has three `run_jobs` calls and six `sendrecv` calls, with no
standalone send or recv calls. Baseline samples have six `copy_bytes` calls;
candidate samples instead have six `message_bytes` calls. All samples have six
`receive_bytes` calls. All 23 runtime configuration keys are present on every
rank, and their values agree across ranks within each run.

The MPI control in **this diagnostic job** has median 3.314520655 seconds.
`profiles.json` retains every validated rank/sample record and source-log hash;
`profiles.txt` contains the complete per-rank and critical-rank tables;
`summary.json` supplies derived comparisons, plan hashes, call counts, runtime
configuration, ranges, and source provenance.

## Exact decomposition of each run's median sample

These are components from the actual rank and sample that supplies the median
maximum-rank time. Each row therefore adds to its displayed total, subject to
rounding; the table does not add independent component medians.

| Variant | Rank/sample | Total (s) | run_jobs (s) | sendrecv (s) | Residual (s) | HPX/MPI median |
|---|---:|---:|---:|---:|---:|---:|
| Baseline, default progress | 2/5 | 13.546164 | 0.909060 | 9.112491 | 3.524613 | 4.0869 |
| Candidate, default progress | 3/1 | 8.770220 | 0.831907 | 4.093580 | 3.844733 | 2.6460 |
| Baseline, MPI background workers = 1 | 0/3 | 11.825169 | 0.968581 | 8.627253 | 2.229335 | 3.5677 |
| Candidate, MPI background workers = 1 | 3/5 | 8.379853 | 0.790401 | 5.367725 | 2.221727 | 2.5282 |

Residual means `PROFILE_TOTAL - run_jobs - sendrecv`. The audited forward plan
has nonnested thread callbacks, so these top-level phases do not overlap.
Residual contains serial transposes and other uninstrumented FFT work,
wrappers, instrumentation, and timing overhead. It is **not** a dedicated
serial-transpose timer, nor does it identify CPU versus memory stalls.

`copy_bytes`, `message_bytes`, and `receive_bytes` are nested inside
`sendrecv`; adding them to the table above would double-count time. The first
includes buffer allocation/initialization and copying, not merely a memcpy.
The remaining `sendrecv` time can include serialization, internal copies,
allocation/deallocation, action handling, source/destination progress waits,
and transport work. These measurements do not separate those causes.

## Candidate improvement at fixed progress settings

At default progress, the median drops from 13.546164 to 8.770220 seconds, a
4.775943-second or 35.26% reduction. Looking at means of the actual critical
rank's components across the seven samples gives an additive interpretation:

- `sendrecv` decreases from 9.055913 to 4.218401 seconds, a 4.837513-second drop.
- The explicitly timed outgoing-buffer construction/copy disappears: 2.831262
  seconds in baseline versus zero `copy_bytes` calls in the candidate.
  `message_bytes` averages only 3.4 microseconds per whole forward sample.
- The final receive copy remains approximately unchanged: 0.731895 versus
  0.745487 seconds. The remainder inside `sendrecv`, after subtracting its
  disjoint measured copy/construction subscopes, decreases from 5.492756 to
  3.472910 seconds. This is consistent with eliminating additional internal
  copying and allocation, but the counters cannot attribute that decrease to
  one specific operation.
- `run_jobs` changes from 0.882813 to 0.801788 seconds; residual changes from
  3.623417 to 3.739733 seconds. Neither accounts for the large improvement.

With one MPI background worker, the candidate median drops from the matching
baseline's 11.825169 to 8.379853 seconds, or 29.14%. Residual means are nearly
identical, 2.221684 and 2.238070 seconds. The corresponding critical-rank mean
`sendrecv` drop is 9.748042 to 5.505452 seconds. Baseline timing variation is
substantial in this setting, so means and medians differ appreciably.

These compare separate runs, not paired samples; sample indices do not identify
the same machine state across variants. Instrumented results explain behavior
and do not replace the uninstrumented primary comparison.

## One MPI progress worker changes the balance

For the candidate, setting `hpx.parcel.mpi.background_threads=1` reduces the
median by only 0.390367 seconds, or 4.45%, in this diagnostic job. Across
critical-rank component means, residual falls by 1.501663 seconds and final
receive copying falls by 0.177811 seconds, but inclusive `sendrecv` rises by
1.287051 seconds. Its non-copy remainder rises by 1.464861 seconds. Threaded
callback time is almost unchanged.

The runtime records show `hpx.max_background_threads=64` in **all four runs**.
Thus this experiment limits MPI parcelport progress only; it does not limit
global HPX background work. MPI multithreading is enabled, and all four global
and MPI zero-copy send/receive configuration values are `1` in every run. A
disabled zero-copy receive path is therefore not an explanation for these
measurements.

The lower residual and copy times are consistent with reduced contention, but
these timers do not prove a particular lock, cache, placement, or allocator
mechanism. The separate global-background limit reported later is a distinct
experiment, discussed below.

## Critical ranks and variability

At default settings, candidate rank 3 is slowest in five of seven samples;
other ranks are slowest in the remaining two. Per-sample rank spread is only
0.079 to 0.202 seconds. With one MPI background worker, the candidate's slowest
rank changes to rank 0 in four samples, rank 2 in two, and rank 3 in one; rank
spread widens to 0.120–1.515 seconds. The gain is not a uniform constant removed
from each rank.

The baseline with one MPI background worker is especially variable. Its last
three sample maxima are 14.578736, 14.836336, and 15.165132 seconds. Their
critical-rank `sendrecv` times are 11.487056, 12.060161, and 12.153146 seconds,
while residual remains 2.14–2.25 seconds and final copying stays 0.54–0.57
seconds. The late slowdown is located in the rest of `sendrecv`, not in the
measured final copy or residual phase. The present evidence cannot distinguish
progress delays, transport behavior, allocation effects, or other causes.

For the candidate with one MPI background worker, the critical-rank mean final
copy is 0.567676 seconds, while the remaining `sendrecv` time is 4.937771 seconds.
Eliminating only that final memcpy cannot account for the roughly five-second
gap to this job's entire MPI transform. Direct reception may additionally
avoid temporary allocation and associated page/registration work, and pooling
may isolate allocation reuse effects, but those benefits require the pending
receive experiments. No page-fault, registration, or allocator-cost counters
were collected here.

## Subsequent tuning context, separate evidence

The parent reported a later uninstrumented comparison with candidate medians
8.38813 seconds for MPI background workers = 1 and 5.55955 seconds for both MPI
and global background workers = 1, against MPI at 3.33358 seconds. These raw
logs were not part of the local diagnostic inputs at analysis time; the values
are recorded in `summary.json` explicitly as parent-reported context. They
must not be substituted for job 1125425's MPI control or assigned the phase
decomposition measured here. Receive-storage experiments were still pending.

The next useful comparison holds both chosen background limits fixed while
comparing unchanged candidate, pooled receive storage, and guarded direct
reception. Correctness and unchanged plans must precede timing. Any remaining
residual should be measured directly before labeling it wholly as serial
transpose time.
