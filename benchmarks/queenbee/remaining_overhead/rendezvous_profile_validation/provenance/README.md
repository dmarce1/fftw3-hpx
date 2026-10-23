<!--
Copyright (c) 2026 Dominic C. Marcello

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

-->

# Isolated rendezvous phase profiler

This is a diagnostic-only fork of the executed prior profiler. No tracked bridge, FFTW algorithm, primary benchmark driver or original archive is changed. The production rendezvous bridge remains SHA256 `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`; the generated diagnostic bridge is `2ea7e60fb8fec7383f8a86b898e4364d82fa1190038be9cba633321484383e13`. The unchanged primary driver hash is `9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41`.

## Generate and compile

Copy the source files into a disposable, unlinked directory, then run:

```sh
python3 -I instrument.py SOURCE_DIR --threads --pairwise
```

The script refuses a Git working tree, symlinks/hard links, an unexpected bridge hash, and duplicate instrumentation. It validates all anchors before writes. It emits `remaining_profile_manifest.json` with before/after hashes and `remaining_profile.patch`, a reversible unified patch for the five modified source files. It copies the three helper sources into the snapshot's `benchmarks/` directory.

Use the existing HPX/application metadata flags and release flags `-O3 -DNDEBUG` (and the established cluster `-march=native`) for diagnostic bridge/driver compilation. `remaining_profile.cpp` is standard-library-only and needs C++20 and pthread, without HPX flags. Link it into both diagnostic executables; link `remaining_mpi_profile.cpp` only into MPI. The latter intercepts `MPI_Sendrecv` and calls `PMPI_Sendrecv`. Replace only the exact bridge and pairwise archive members in copies of the HPX archive, the pairwise member in a copy of the MPI archive, and the dynamically identified pthread member in a copy of the threaded archive. Keep the shared serial archive unchanged. The original 28 metric IDs and all three transformed C sources remain unchanged from the old profiler; ten new IDs are appended. Rebuilding MPI with the new helper is supported and used in local validation.

## Disjoint exchange phases

`FrpPhases` is declared before all function-local exchange objects and destroyed last. It records one monotonic-clock boundary at each transition. The final timestamp is shared by the last phase and the inclusive total, so all phase nanoseconds add exactly to total exchange nanoseconds, including `Message`, future and registration destruction. Diagnostic clock/counter overhead is included, largely in the next phase; an exact partition is not a claim of zero measurement overhead.

| Metric | Boundary and interpretation |
| --- | --- |
| `exchange_rest_wall` | Initial group, count, sequence and overlap setup; plus final object/registration destruction. Two intervals per successful call. |
| `post_announce_initiation_wall` | Target registration, readiness announcement initiation and outgoing-peer readiness-get initiation. |
| `readiness_phase_wall` | Conditional peer readiness `get`, byte validation and direct flag selection. Includes the small false-branch work for eager/self calls. |
| `send_initiation_wall` | Construct the outgoing message and initiate channel `set`. |
| `receive_wait_wall` | Initiate incoming channel `get` and wait for its message. |
| `send_completion_wait_wall` | Wait for any outgoing completion still outstanding after incoming completion. |
| `receive_finish_wall` | Entire `receiveBytes` call, including size/null checks and either final memcpy or direct-buffer no-op. |
| `announce_completion_wait_wall` | Wait for readiness-announcement completion. |

`receive_memcpy_wall` remains the nested actual memcpy scope and records only bytes actually copied. It is not added again to the disjoint phase sum. Pool allocation and direct/owned message-load counters are also nested observations. `message_load` is partitioned into direct, owned and empty events, with counts and bytes conserved. `required_posted_message_load` proves which payloads required an already-posted target. A direct load proves destination selection; with a transport/archive that does not support direct receive it can still involve a serialization copy. Local TCP validation does not establish MPI zero-copy performance.

Readiness elapsed time cannot distinguish a peer that finishes FFT/staging late from token transport or progress delay. Incoming-get elapsed time is similarly not an isolated network bandwidth measurement. Outgoing completion is the remaining wait at that program point, not total send duration. No profiler output alone should assign one of these causes.

## Reporting without mixed output

Set `FFTW_REMAINING_PROFILE_DIR` separately for each diagnostic case to an existing, fresh, case-specific directory. The helper writes `<backend>-<rank>.log` there after the forward timer and reduction. It aborts on open, flush, write or close failure. It never adds a barrier. Without this environment variable it retains the old stderr behavior, but launchers can interleave fragments and the strict parser will reject them.

Keep the original benchmark stdout/stderr and all per-rank logs byte-identical. Concatenate whole files into a separate analysis input, without rewriting any original. Report-file I/O and other diagnostics occur outside the forward timer but may perturb subsequent samples; unchanged primary MPI/HPX controls remain necessary.

```sh
python3 -I analyze.py analysis_mpi_profile.log analysis_hpx_profile.log --json analysis.json
```

Defaults are four ranks, 64 workers, extent 1024, two warmups and seven samples. Override `--ranks`, `--threads`, `--extent`, `--warmups` and `--samples` for bounded local validation. `--legacy-mpi-baseline` explicitly accepts only a complete old MPI metric schema; its appended HPX-only metrics are marked unmeasured/not applicable zeros, never silently treated as observed measurements.

The analyzer validates all raw numerical checks, printed plan equality, timing statistics, rank/sample completeness, nonnegative counters, no late/pending scopes and no nested job envelope. For HPX it additionally requires exact integer-nanosecond exchange coverage, exact phase-call counts, memcpy contained in receive-finish time, and direct/owned/empty load conservation. It retains every rank/sample phase, each sample's actual slowest rank, and each sample's largest rank sum of readiness phases. Cross-run equal sample indices are only bookkeeping pairs. Component arithmetic-mean deltas add to the mean total difference; independent component medians must never be summed.

Unchanged thread and staging metrics retain their original scope: callback thread CPU is valid for audited nonyielding callback bodies only, with no detected migration/nesting. Full-process CPU includes runtime work and is valid across waits. The residual includes serial FFT/transpose work and instrumentation not covered by disjoint exchange, threaded envelope and pairwise-copy/allocation/free scopes. Inclusive task/queue/child/pool scopes cannot be added to those disjoint totals.

## Validation and limits

`VALIDATION.json`, `TOOLS_SHA256SUMS`, `PROJECT_INPUTS.sha256`, compile commands/logs, `phase_check.log`, `analyzer_check.log`, and the two local runtime directories retain the evidence. All eight diagnostic objects compile with release assertions disabled. The ordinary-main recorder unit uses active assertions and covers inactive operation, exact coverage, destruction order and exception unwinding. Synthetic fixtures include explicit legacy-MPI acceptance and 30 rejected malformed inputs, including a one-nanosecond partition error, missing exact counters and inconsistent message-load routes.

Local double-precision N64 cases passed at four ranks × one worker and three ranks × two workers. Both backends used two warmups and seven samples, with all numerical checks and normalized plans passing. Every HPX rank/sample had exact phase coverage, only required direct message loads and zero final-copy bytes. The threaded case exercised the original callback instrumentation with equal MPI/HPX callback counts and no nesting/migration flags. These are correctness/instrumentation checks, not cluster performance results.

The original merged local logs are retained as rejected interleaving examples, as is the first sandbox socket-denial log. Subsequent authorized local tests used local socket access only. No QueenBee access or login was performed by this validation task.
