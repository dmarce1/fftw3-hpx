# Lean HPX build evidence: job 1125886

Copyright (c) 2026 Dominic C. Marcello

This program and its accompanying notes are free software; you can redistribute
them and/or modify them under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the License, or
(at your option) any later version. They are distributed in the hope that they
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
License for more details. You should have received a copy of the GNU General
Public License along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

Job 1125886 completed successfully on 2026-10-23, 07:52:34–07:58:09 UTC. This is
build and configuration evidence only. It does not establish a speedup or a
successful FFT benchmark using this installation.

The executed [job](1125886/build.sbatch) and [cache helper](1125886/prepare.py)
used one allocated workq node and at most 32 build jobs. No dependencies were
downloaded. The exact original HPX source commit was
`c9b81b401fbe6ba4a0306feff71d18ef01c71b34`; Asio came from the original build's
existing dependency checkout. The new build and installation are isolated under
`/work/dmarce1/fftw3_hpx_remaining_20261023/lean_hpx/`.

The actual allocation used GCC13.2.0, CMake3.26.5 and Python3.6.8. MPI5.0.11,
Boost1.83 and jemalloc configuration paths remained unchanged. Configuration
uses the original hwloc2.9.1 headers/library path; the loader resolves
`libhwloc.so.15` from the MPI prefix in both the original and lean environments,
as recorded by [original dependencies](original_config/runtime_libraries.txt)
and [lean dependencies](1125886/dynamic_dependencies.log).

## Configuration changes

| Feature | Original | Lean |
| --- | --- | --- |
| APEX | ON | OFF |
| Parcel profiling | ON | OFF |
| Logging | ON | OFF |
| IO counters | ON | OFF |
| Cumulative thread counters | ON | OFF |

APEX fetching was also disabled. Seven installed macros disappeared: the five
feature macros above plus APEX-forced thread descriptions and parent references.
No new HPX macros appeared. The complete cache changes are recorded in
[configuration.json](1125886/configuration.json).

Lock verification, lock-registration backtraces, suspension backtraces,
spinlock deadlock detection, thread debug information, stack-overflow detection,
sanitizers, Valgrind, ITTNotify, debugger attachment and test debug logging were
already OFF and remained OFF. HPX_DEBUG was absent. All 377 actual compile
commands contained `-O3 -DNDEBUG -march=native` and no HPX_DEBUG or sanitizer
definition. Exception stacktraces/demangling remain enabled; they are distinct
from suspension backtraces. Guard pages remain enabled.

MPI parcelport, MPI multithreading, async MPI, distributed runtime, networking,
jemalloc, IO/timer pools, idle-backoff support, coalescing and the 8192-byte
zero-copy serialization threshold were preserved. TCP remains disabled. This
groups five instrumentation changes; a later performance comparison can measure
their combined effect, not attribute a difference to one particular option.

## Validation and preservation

The [configuration audit](1125886/audit_configuration.log) and
[installation audit](1125886/audit_install.log) passed for all 170 explicit
options and 377 compile commands. Installed definitions match the requested
features. Dependency inspection found no missing libraries and no APEX runtime
dependency. [FINAL_STATUS](1125886/FINAL_STATUS) records PASS and exit status 0.

The original CMake cache was checked byte-for-byte before configuration. The
original source HEAD and clean tracked state were checked before and after;
both saved source-status files are empty and identical. SHA-256 preservation
checks passed for the original cache, installed definitions, exported cache
metadata, `libhpx.so` and `libhpx_core.so`. These checks and exact paths are in
[original-inputs.sha256](1125886/original-inputs.sha256) and
[verify_original.log](1125886/verify_original.log). The original installation
was not rebuilt or overwritten.

This was not a warning-free build. Configuration reported missing libxml pkg-config
metadata while resolving explicit hwloc paths. Compilation emitted 927 warning
lines comprising six distinct warnings, about unused coroutine parameters and a
disabled-logging expression. No compiler error lines were found. The configure
log is retained whole; [build excerpts](1125886/build_excerpt.txt) preserve each
distinct warning and completion lines.

## Retained evidence

`1125886/` retains the exact executed scripts, original and lean caches,
configuration record, command files, audit/status/dependency logs, installed
artifact digests and compact build/install excerpts. The 7.4 MB compilation
database is preserved byte-for-byte as deterministic
[compile_commands.json.gz](1125886/compile_commands.json.gz); decompress it to
recover every exact command. Its expanded SHA-256 and all original log digests
are in [original_evidence.json](1125886/original_evidence.json).

Full build/job/install logs, binaries and build objects are omitted. Original
installed HPX metadata is in `original_config/`. The independently recomputed
[validation summary](1125886/validation_summary.json) records the checks and
limitations. [copied_files.json](copied_files.json) maps every byte-identical
copy to its local source; [SHA256SUMS](SHA256SUMS) covers this directory and the
sibling compile audit. From this directory, `sha256sum -c SHA256SUMS` verifies
the published package.
