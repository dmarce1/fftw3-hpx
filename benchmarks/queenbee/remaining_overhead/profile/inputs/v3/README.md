# Immutable diagnostic inputs v3

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

Prepared for the root agent to stage under `/work/dmarce1/fftw3_hpx_remaining_20261023/inputs_v3`. No QB access, submission, local compilation, or benchmark was performed during preparation. v1 (`inputs`) and v2 remain unchanged.

Job 1125884 completed every compile/link stage, then failed in the archive checker because the actual QB Python is **3.6**, where `text=True` is unsupported. v3 replaces that keyword with `universal_newlines=True`. Its profile transformer and three C/C++ helpers are byte-identical to v2. The unchanged five-case cohort uses MPI, pooled control, release pool, profiled MPI, and profiled HPX, with the same 1024-cubed driver, plans, samples and runtime settings.

The v3 job performs no compilation. Before any benchmark, it verifies current fixed inputs against the failed job's manifest and verifies the immutable v2 and v3 input manifests. `reuse_artifacts.py` requires the expected failed job/stage/error, all 16 completed instrument/build/link steps, no previous benchmark logs, all eight diagnostic source hashes, matching unmodified source/helper hashes and HPX flags. It copies `bin` and `objects` into the new result directory and verifies each copy's digest. The failed job's outputs and logs remain untouched.

The corrected archive checker requires the exact original ordered member set, unique member names, the intended changed members only, and byte equality between each replacement archive member and its loose compiled object. It resolves both plain and Automake-prefixed original member names; it never treats an extra appended member as a valid replacement. The root independently checked that the remote original MPI member is `transpose-pairwise.o`.

Reuse hashes are recorded at this guarded reuse step: v2 stopped before it produced its final artifact manifest. This is an explicit provenance boundary, not a claim that v2 recorded those hashes earlier. The new job preserves the failed job's source manifest, commands/status/log, records all old input digests, and rechecks them after the cohort. New artifacts and frozen input manifests are also rechecked by the existing final gate. Any failure before the archive proof prevents every benchmark launch.

Python 3.6 grammar checks passed for all v3 Python scripts, the shared comparison parser, and the CMake flag helper; shell syntax checks passed. The checker read three real existing local archives successfully and resolved both plain and prefixed member names. This was read-only inspection, not a rebuild. The workflow audit found no other active Python3.6-incompatible call. The old frozen v1 transformer still uses `Path.is_relative_to`; v2/v3 use `Path.parents` and v3 does not rerun transformation.
