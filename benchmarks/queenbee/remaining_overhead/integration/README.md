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

# Integrated rendezvous validation

The tracked rendezvous bridge and both tracked check sources passed the existing autotools targets in all three precision builds. Source digests are recorded in `source_inputs.sha256` and `summary.json`; the bridge is the frozen `cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c` candidate. No tracked source was modified during validation.

For each of `double`, `single`, and `long_double`, `run_validation.sh build PRECISION` built the library target with `CXXFLAGS='-O3 -DNDEBUG'`, then the existing `hpx-message-check` and `hpx-comm-check` targets with `CXXFLAGS='-O3 -UNDEBUG'`. These use the configured HPX compiler/linker flags and current production source. No prototype archive was substituted. Three `make -j1` builds ran concurrently, with at most three compiler processes.

`run_validation.sh focused PRECISION` then ran the ordinary-main message test (all 11 groups passed) and communication checks at 1 locality x 2 workers and 3 localities x 2 workers. Each communication launch completed two initialization/cleanup cycles, including shared duplicate generations, cached reversed-key splits, repeated message tags, ownership/overlap cases, readiness matching with standalone operations and directional empty messages, variable all-to-all byte counts, and nested large-stack callbacks. All six launches passed.

`validate_combined.sh build` linked the existing combined-precision smoke source against all three newly built HPX archives and their unchanged serial/threaded archives. Its single 3-locality x 2-worker run passed, including interleaved precision use, cleanup and reinitialization. All runtimes ran sequentially on this workstation; no remote connection was made and at most six HPX workers ran at once. The local launcher forces same-server TCP and disables MPI; this is local integration evidence, separate from QueenBee MPI-parcelport measurements.

`hpx_archives_before.json` and `hpx_archives_after.json` record every member digest. Each HPX archive has 32 members and changed only `hpx-comm.o`. All 45 protected C archives across the three precision builds remained byte-identical, verified before and after the work. The C++ style audit found no issue in include grouping, trailing const, unqualified `size_t`, braced loop bodies or GPL notices. No warning/error/assertion-failure patterns were found in the build and runtime logs.

Exact commands, logs, statuses, compiler environment and binary hashes are below each precision directory and `combined/`. This check did not repeat the full random numerical matrix: that matrix had already passed for the byte-identical frozen candidate. The combined numerical smoke is the fresh numerical check here.

## Published package and source provenance

This directory is a text-only copy of the local integration evidence from `build/qb_remaining/integration_validation`. It contains no executables, objects or libraries. [PACKAGING_PROVENANCE.json](PACKAGING_PROVENANCE.json) maps every copied evidence file and all ten validated source inputs to their byte hashes. Exact source snapshots are under [validated_inputs](validated_inputs/), including the combined-precision smoke source and the Makefile inputs used by these checks. [validation_README.md](validation_README.md) preserves the original local summary before this packaging appendix.

The current implementation is [hpx-comm.cpp](../../../../hpx/hpx-comm.cpp); the assertion-enabled checks are [hpx-comm-check.cpp](../../../../hpx/hpx-comm-check.cpp) and [hpx-message-check.cpp](../../../../hpx/hpx-message-check.cpp). The [frozen rendezvous experiment](../experiments/prototypes/rendezvous/README.md) supplies the earlier full numerical matrix evidence. Current build documentation may receive subsequent documentation-only distribution updates; the recorded Makefile snapshots identify exactly what this integration run used.

[SHA256SUMS](SHA256SUMS) covers every published text file except itself. The executable/archive hashes in the original logs identify validation artifacts that are intentionally not shipped. Absolute workstation paths in the raw command and hash logs are retained verbatim. The scripts are recorded as executed from their original ignored directory; their path assumptions are not rewritten for this published location.
