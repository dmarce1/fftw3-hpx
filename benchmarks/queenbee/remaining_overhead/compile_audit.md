# HPX compile-time option audit

Copyright (c) 2026 Dominic C. Marcello

These notes are free software; you can redistribute them and/or modify them
under the terms of the GNU General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version. They are distributed in the hope that they will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along
with these notes; if not, write to the Free Software Foundation, Inc., 51 Franklin
Street, Fifth Floor, Boston, MA 02110-1301 USA.

## Evidence and scope

The root agent retrieved the actual QB CMakeCache and installed configuration.
They are preserved in [the lean-build evidence](lean_hpx/README.md), including
`lean_hpx/1125886/original-CMakeCache.txt` and `lean_hpx/original_config/`.
The matching APEX implementation used for the source audit remains in the local
`build/qb_remaining/apex_source` evidence.
This audit performed no remote access. Installed HPX reports commit
`c9b81b401fbe6ba4a0306feff71d18ef01c71b34`; the local HPX source inspected at
`/home/dmarce1/work/hpx` is the same commit. Source references below are relative
to that HPX checkout unless they explicitly name the fetched APEX files.

The local installed HPX is not the QB configuration. Locally APEX and parcel
profiling are OFF, TCP is ON, and spinlock deadlock detection is ON. Those local
settings cannot be used to infer the QueenBee binary's options.

## Debug facilities

The actual QB build is Release with `-O3 -DNDEBUG`, plus `-march=native`. Cache
entries and installed defines agree that lock verification, lock-registration
backtraces, suspension backtraces, spinlock deadlock detection, thread debug
information, stack-overflow detection, sanitizers, Valgrind and ITTNotify are
disabled. `HPX_DEBUG` is absent. These are not hidden debug builds.

Exception stacktrace and symbol-demangling support remain enabled. They are not
the suspension-backtrace option, and their presence does not establish repeated
stack captures on the timed path. Guard pages are also enabled and remain in the
controlled lean build to preserve stack protection. Thread descriptions and
parent references are compiled in because APEX forces them even though
HPX_WITH_THREAD_DEBUG_INFO is OFF: see `CMakeLists.txt:1569` and
`cmake/HPX_SetupApex.cmake:46`.

The earlier FFTW bridge compilation omitted `-DNDEBUG`, leaving ordinary C++
`assert` calls enabled. They check scalar pointer, size, generation and rank
invariants; they do not scan message bytes. This does not enable HPX's lock
verification or HPX_DEBUG. `libs/core/config/include/hpx/config/debug.hpp` does
not infer HPX_DEBUG from missing NDEBUG, and
`libs/core/assertion/include/hpx/modules/assertion.hpp:79` gates HPX_ASSERT on
HPX_DEBUG explicitly. A same-source `pool_release` control isolates the addition
of `-DNDEBUG`. Correctness checks using explicit if/throw remain active, and the
communication checker separately retains `-UNDEBUG`.

## APEX and parcel profiling

APEX, parcel profiling, logging, IO counters and cumulative thread counters are
all compiled ON in the installed QB HPX. The benchmark sets APEX_DISABLE=1.
The matching fetched APEX code supports an early disabled path:

- `apex_source/src/apex/apex.cpp:1393` and `:1427`: new_task returns before
  task-wrapper allocation, task lookup and listener notification when disabled.
- `apex.cpp:819`: start checks the task and disabled setting before normal work.
- `apex.cpp:2276` and `:2303`: send/receive adapters return before event listeners.
- `apex_options.cpp:58`: option environment values are loaded when the options
  singleton is constructed, not reparsed by each callback.

HPX callback registration and wrapper calls still exist, and APEX enters its
`in_apex` guard before several disabled checks. It is therefore inaccurate both
to call the build completely free of APEX overhead and to claim APEX is actively
recording all task profiles despite APEX_DISABLE=1.

Some parcel-profiling work exists independently of the runtime APEX setting:
`libs/full/parcelset/src/parcel.cpp:42` initializes creation time;
`:115` and `:131` deserialize/serialize extra parcel ID and time fields;
`parcelhandler.cpp:1445` sets parcel start time and a unique ID under the compile
flag. Disabling APEX at runtime does not compile those operations away. This is
a concrete reason to compare a clean instrumentation-free build, but it does
not quantify their cost or establish that they explain the remaining gap.

## Transport options to preserve

The MPI parcelport, distributed runtime, MPI multithreading and async-MPI module
are ON; TCP, LCI, GASNet and libfabric parcelports are OFF. The global and MPI
runtime zero-copy options were already enabled in the prior diagnostics, and
1 GiB payloads exceed the compile-time 8192-byte serialization threshold. No
evidence supports adjusting that threshold for this case.

HPX_WITH_ASYNC_MPI selects the separate async-MPI API/module. The MPI parcelport
has its own MPI requests and progress implementation; disabling the API module
does not replace that mechanism. HPX_WITH_PARCELPORT_MPI_MULTITHREADED affects
the requested MPI thread level (`libs/core/mpi_base/src/mpi_environment.cpp:201`).
Turning it OFF would force the serialized path already rejected after a failed
runtime experiment, so it is preserved. MPI background-thread count and global
maximum background-thread count remain runtime controls, not compile switches.

Parcel-coalescing support is ON, but compiled support alone does not show that
the channel actions attach a coalescing handler. No timing claim is made for it.
The allocator is jemalloc, thread stacks do not use mmap, and the existing
NUMA/interleave/worker placement controls are retained.

Job [1125886](lean_hpx/1125886/FINAL_STATUS) successfully built and installed the
lean configuration in a fresh prefix. It checked all 170 seeded options, all
377 compile commands, the installed defines and dependencies, and preservation
of the original inputs. Its exact executed script is
[build.sbatch](lean_hpx/1125886/build.sbatch). The transport and allocation
choices remain unchanged. Seven macros disappeared: the five requested feature
macros plus APEX-forced thread descriptions and parent references.
All HPX-dependent C++ consumers must be recompiled because these changes affect
task/parcel layouts. Build success alone establishes no performance benefit;
benchmark results must be assessed separately.
