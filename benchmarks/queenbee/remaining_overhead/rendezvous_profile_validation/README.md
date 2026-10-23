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

# Local validation of the rendezvous phase profiler

This package validates the temporary instrumentation prepared for a new cluster diagnostic run. It contains **no new cluster timing result** and makes no claim that the remaining HPX overhead has been eliminated. The production bridge and primary benchmark driver were unchanged.

The diagnostic recorder partitions each HPX `sendrecv` into setup/destruction, receive registration/readiness initiation, peer readiness, payload initiation, incoming completion, outgoing completion, final receive handling and readiness-announcement completion. Shared clock boundaries make the phase nanoseconds add exactly to the inclusive exchange time. The recorder is destroyed last, so final future/message/registration destruction is included. Actual receive memcpy remains a nested counter; it is not added twice. Readiness elapsed time does not distinguish a peer that arrives late from transport/progress delay. See the frozen [instrumentation design](provenance/README.md) and [generated diagnostic bridge](transformation/hpx-comm.cpp).

| Validation | Result |
| --- | --- |
| Eight diagnostic C/C++ object compilations | Passed with `-O3 -DNDEBUG` |
| Recorder unit with active assertions | Inactive operation, exact coverage, destruction order and exception unwinding passed |
| Synthetic analyzer checks | Two full-schema cases passed; 30 malformed fixtures rejected; old MPI accepted only with its explicit legacy option |
| Local MPI and HPX, N64, 4 ranks × 1 worker | Seven samples and three numerical checks per backend passed; normalized plans match |
| Local MPI and HPX, N64, 3 ranks × 2 workers | Same checks passed; callback counts match for every rank/sample |
| Exact exchange coverage | Zero nanosecond error in all 49 measured HPX rank/sample records |
| Receive route | 168/168 and 84/84 respective message loads required and used posted targets; no owned fallback or final receive memcpy |

The threaded case exercised 184 or 188 thread-loop calls and 368 or 376 callback bodies per rank/sample, equally for MPI and HPX, with no nesting or CPU-migration flags. These are bounded local instrumentation checks. Local HPX used TCP on one machine; this does not establish MPI zero-copy performance or any QueenBee speedup.

[SUMMARY.json](SUMMARY.json) is recomputed from the preserved benchmark and per-rank logs. [Original validation receipts](provenance/VALIDATION.json) also record compile, synthetic, reversible-patch and independent read-only review results. [Archive-member records](raw/local_runtime/archives.json) show that only the intended members changed in copied archives, with original archive hashes preserved. Binaries and archives are excluded from this publication.

## Frozen sources and provenance

The primary bridge is SHA256 `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`. The generated diagnostic bridge is `2ea7e60fb8fec7383f8a86b898e4364d82fa1190038be9cba633321484383e13`. The primary driver remains `9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41`.

[tools/](tools/) preserves the exact frozen transformer, helper sources, analyzer, unit and original local check scripts. [source_inputs/](source_inputs/) preserves the five original source inputs. The [reversible patch](transformation/remaining_profile.patch) and [transformation manifest](transformation/remaining_profile_manifest.json) record all diagnostic edits. The transformed pthread and both pairwise C files are byte-identical to the preceding profiler, and original metric IDs are preserved with ten new IDs appended. The frozen original README/scripts retain their original workspace-relative paths; compilation or regeneration requires the corresponding full source/build environment, not this compact evidence directory alone.

The new optional `FFTW_REMAINING_PROFILE_DIR` writes one file per backend/rank after the forward timer, with checked open/write/flush/close errors and no added barrier. Initial merged local stderr was rejected because launcher fragments interleaved. Both rejected merged logs and the initial sandbox socket-denial receipt are retained under [raw/local_runtime/](raw/local_runtime/). Subsequent authorized local runs used separate files. Reporting outside the forward timer can still perturb later samples, so unchanged controls remain necessary for cluster conclusions.

[Source and exclusion mapping](SOURCE_MAP.json) records every exact copy and omitted file. The [original frozen inventory](provenance/FROZEN_SHA256SUMS) includes omitted binaries and duplicate intermediate snapshots; it is a historical receipt, not a manifest that can be checked wholly in this reduced package. [SHA256SUMS](SHA256SUMS) covers every published file except itself. No additional FFT run, build or QueenBee access was performed to make this publication.

## Reproduce the compact evidence

From this directory, with Python 3.6 or newer:

```sh
sha256sum -c SHA256SUMS
(cd tools && sha256sum -c TOOLS_SHA256SUMS)
(cd source_inputs && sha256sum -c ../provenance/PROJECT_INPUTS.sha256)
python3 -I recompute.py > /tmp/rendezvous_profile_summary.json
cmp SUMMARY.json /tmp/rendezvous_profile_summary.json
```

The recomputation reads the original benchmark/rank files and writes only temporary concatenated inputs. It runs no FFTs and changes no raw evidence. Full duplicated analysis JSON and concatenated inputs are omitted with their hashes because these can be regenerated.

Synthetic rejection fixtures are retained losslessly: two base logs are byte-identical, small mutations are unified patches, and mutations whose patch would be larger remain full logs. Their [manifest](fixtures/FIXTURES.json) records original hashes and expected outcomes. Restore all fixtures to a new empty directory with GNU `patch` available:

```sh
python3 -I reconstruct_fixtures.py /tmp/rendezvous_profile_fixtures
```

Restoration verifies every original fixture hash and does not execute tests. The frozen [analyzer check log](provenance/analyzer_check.log) records the executed rejection results. Synthetic fixtures are explicitly marked and must not be presented as measured timing data.
