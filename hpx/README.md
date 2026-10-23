# fftw3-hpx

The 2026-10-22 HPX port retains FFTW 3.3.11's distributed algorithms,
block distributions, flags, planner hooks and verification code. Each HPX
locality takes the place of one distributed process. The public header is
`fftw3-hpx.h`; the libraries are `libfftw3_hpx`, `libfftw3f_hpx`, and
`libfftw3l_hpx`. They use FFTW's unchanged serial and threaded libraries.

The source is the [official FFTW 3.3.11 release tarball](https://fftw.org/fftw-3.3.11.tar.gz),
with SHA256 `5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1`.
Its generated codelets are included unchanged.

## Building

Use the release's generated codelets and autotools. No OCaml, code generation,
maintainer mode or CMake is needed. Use an HPX installation whose headers,
Boost headers, and linked dependencies match. For a coherent HPX 1.11.0
installation at the specified prefix:

```sh
export PKG_CONFIG_PATH=/home/dmarce1/local/hpx/Release/lib/pkgconfig
export PATH=/home/dmarce1/local/hpx/Release/bin:$PATH
mkdir -p build/double
cd build/double
../../configure --enable-hpx --enable-threads
make -j8
make -C hpx check CXXFLAGS='-O3 -UNDEBUG'
make -C hpx bigcheck CXXFLAGS='-O3 -UNDEBUG'
```

For the other precisions, configure separate build directories with
`--enable-float` or `--enable-long-double`. HPX mode requires `--enable-threads`
and rejects quad precision. The usual `--enable-shared` and
`--with-combined-threads` options remain available. A default configure without
HPX builds stock FFTW. Link C++ applications with the appropriate HPX library,
FFTW thread and serial libraries, and the flags from `hpx_application`.

These commands build the assertion-enabled checks as well as the library.
The measured Release bridge uses `-O3 -march=native -DNDEBUG`; its archived
cluster scripts build that library separately from check executables compiled
with `-UNDEBUG`. Do not pass a final `-DNDEBUG` to an `all` target that also
builds the checks, because they deliberately reject disabled assertions.

`make -C hpx check` runs the upstream random verification matrix at 1, 2, 3
and 4 localities with one HPX worker each, then 3 localities with two workers
each. Tests run sequentially. `bigcheck` increases the random geometry count
from 10 to 100 and maximum transform size from 10000 to 60000. A wisdom
round trip is available with `CHECK_PL_OPTS=--validate-wisdom`. The launcher
wrapper keeps every locality on the local machine, forces TCP, disables the
MPI parcelport, and checks for exit status zero.

## This workstation's dependency environment

The installed HPX prefix survived an operating-system upgrade with stale
pkg-config metadata and mismatched dependency defaults. The successful local
validation uses a build-directory compatibility environment:

```sh
cd /home/dmarce1/workspace/fftw3-hpx
. build/hpx_env.sh
```

This selects copied HPX pkg-config files under `build/hpx_compat/pkgconfig`,
matching Boost 1.83 headers under `build/hpx_compat/boost_headers`, and the
original packaged Open MPI 4 shared libraries through local symlinks under
`build/hpx_compat/lib`. It also removes the unavailable, unneeded `-lcuos`
entry from those copied pkg-config files. Installed HPX and system files
remain unchanged. These machine-specific build files are ignored by Git;
they are not supplied by a fresh clone. [VALIDATION.md](VALIDATION.md) records
the exact environment, dependency versions, recovery recipe, and test results.
Configure rejects mismatched HPX/Boost headers instead of accepting an
optimized link that accidentally eliminates the version check.

## Local and cluster transports

TCP is permitted only between localities on the **same server**. Never use
TCP between servers. The test wrapper uses `hpxrun.py -r none`, clears node
settings, and launches all processes on that server using TCP. It disables
the MPI parcelport. The local check targets therefore remain local even on a
cluster login or compute host.

A separate, explicitly authorized multi-server cluster run must use HPX's
MPI parcelport with TCP disabled. It needs an MPI-enabled HPX installation
and an allocated compute job; the local TCP test results do not establish
multi-server correctness. Cluster validation is reported separately.

For the measured QueenBee 1024³ case with four localities and 64 workers each,
use this startup profile with the allocated MPI launcher:

```sh
--hpx:localities=4 --hpx:threads=64 \
--hpx:ini=hpx.parcel.mpi.enable=1 \
--hpx:ini=hpx.parcel.mpi.priority=1000 \
'--hpx:ini=hpx.parcel.tcp.enable!=0' \
--hpx:ini=hpx.parcel.bootstrap=mpi \
--hpx:ini=hpx.parcel.mpi.background_threads=1 \
--hpx:ini=hpx.max_background_threads=1 \
--hpx:ini=hpx.parcel.mpi.multithreaded=1 \
--hpx:ini=hpx.parcel.mpi.sendimm=0 \
--hpx:ini=hpx.max_idle_backoff_time=10
```

These options must be applied when starting HPX, before `fftw_hpx_init()`.
The library does not override the application's background-worker settings.
The forced `!=0` TCP entry also works when that parcelport is compiled out.
Keep MPI multithreading enabled. The tested Open MPI transport environment was
`OMPI_MCA_pml=ucx`, `OMPI_MCA_btl=self,sm`, and `UCX_TLS=rc,sm,self`, with
one unbound process per node and `numactl --interleave=all`. Use the
[executed jobs and evidence](../benchmarks/queenbee/remaining_overhead/README.md)
for the complete machine-specific launch. This profile was measured for that
workload; other workloads may prefer different progress settings. The 10 ms
cap improved the final cohort's wall-time medians but used more process CPU
in its diagnostic run; the report retains that tradeoff and both 1000 ms
controls. The
[compile-time audit](../benchmarks/queenbee/remaining_overhead/compile_audit.md)
records the Release build, MPI parcelport options, and disabled debug facilities,
including lock verification. Local workstation dependencies differ from that
QueenBee installation.

## Application contract

Include `fftw3-hpx.h`. Run `hpx_main` on every locality, with the HPX setting
`hpx.run_hpx_main!=1`. Dispatch planning and execution through
`hpx::execution::parallel_executor(hpx::threads::thread_stacksize::large)`.
See `hpx-bench-main.cpp` for an executable example of startup and finalization.
FFTW needs a large stack for its stack-allocated scratch arrays and codelets.

On each locality, call `fftw_hpx_init()` before any other FFTW call. Obtain
`fftw_hpx_comm_world()` and pass it to the corresponding `fftw_hpx_*` planning
and distribution functions. Choose the FFTW worker count with
`fftw_plan_with_nthreads()`. The world handle is library-owned, belongs to its
precision library, and is valid until `fftw_hpx_cleanup()`. Destroy all plans
and release FFTW allocations before cleanup. Every locality calls cleanup
before `hpx::finalize()`. The same rules apply to the `fftwf_` and `fftwl_`
variants. There are no public constructors for other communicators.

All members issue collective operations in the same order, from HPX threads.
Planning is collective, including the cost and wisdom hooks. Calls using a
group must be sequential; planning and execution must not concurrently issue
communication on a shared group. Different precision libraries have separate
world names and counters. The Fortran distributed interface is not ported.

## Communication and threading

Communicator duplication creates a new handle sharing the existing group;
it does not create an HPX communicator. Splits gather colors and keys, order
members by key then parent rank, and cache the resulting groups until cleanup.
Each collective uses the group's next explicit generation. Point-to-point
messages combine the original tag with a per-peer send/receive sequence. A
precision-specific message serializes its match key and byte count before an
HPX `make_array` payload. Remote sends borrow caller storage until the send
future completes; self-sends own a copy so callers can reuse their source.
Collectives retain their owned byte-vector payloads. See
[MPI_MAPPING.md](MPI_MAPPING.md) for the replaced MPI calls and their HPX
counterparts.

For a remote `sendrecv` with disjoint source and destination ranges, the bridge
registers the exact FFTW destination and announces its readiness to the receive
source. It waits for readiness from the send destination before sending the
large payload. The deserializer then supplies the registered address directly
to HPX's receive path. Its lookup never waits, checks the byte count, and claims
the destination only once. Registration remains live until receipt completes.
FFTW still allocates and frees its own arrays: the bridge neither replaces its
allocator nor takes ownership of the borrowed memory. When both peers use this
direct path, it removes the final payload copy without changing FFTW's
transpose algorithm or its staging copies.
Direct MPI reception requires HPX's array/chunk and zero-copy optimizations to
remain enabled. The 1 GiB benchmark messages exceed the 8192-byte threshold.
Other settings remain correct but may copy inside deserialization; see the
[parcelport source audit](../benchmarks/queenbee/remaining_overhead/parcelport_path.md).

Every receive announces readiness, including standalone receives, self-messages,
empty messages and overlapping exchanges. Eager fallback sends consume their
matching readiness notification without waiting for it. This supports the
matched mixed-mode exchanges exercised by the communication checks. As with
portable MPI, arbitrary schedules must not rely on eager buffering to resolve
circular dependencies. A peer that promises a posted destination must supply
it; a missing or mismatched target is
an error rather than a silent fallback. Group calls retain the sequential-use
contract described above.

Early standalone arrivals and self/overlapping exchanges use owned receive
storage. A fallback exchange waits for outgoing send completion before copying
the received bytes into the destination, preserving overlapping source data.
Its allocator caches at most one idle block per precision, reuses only an exact
byte-count match, and retains the larger block when multiple sizes return.
Only the last message owner can return a block; allocation never waits for a
live owner. Cleanup frees idle storage and disables that pool epoch, so old
owners cannot refill a new initialization's pool. The pool's retained memory
is bounded by the largest returned message, in addition to live messages.
HPX's per-tag channel metadata, for both data and readiness, is retained until
group cleanup and grows with the number of messages.

The communication check covers source reuse, empty messages, self-sends,
exact/partial overlap, mixed standalone/direct exchanges, distinct send and
receive peers, splits and repeated initialization. `make -C hpx check` also
runs the standalone `hpx-message-check` first. Its eleven groups use real HPX
serialization archives to check destination matching and lifetime, owned
fallbacks, last-owner recycling, exact-size reuse, largest-block retention and
cleanup with live or delayed owners. Checks force assertions on and reject a
later `-DNDEBUG`; when setting `CXXFLAGS`, put `-UNDEBUG` last for these targets.

The threaded-loop callback starts all but the final job with `hpx::async` on a
large-stack executor, runs the final job inline, and waits with `hpx::wait_all`.
The pthread worker pool is bypassed. If the callback is entered from an
external thread, `run_as_hpx_thread` provides a trampoline and an additional
large-stack dispatch executes FFTW work.

## Installed-HPX adaptations

* Collective, data and readiness communicators use `/collective`, `/channel`
  and `/readiness` suffixes. HPX 1.11 registers them in the same AGAS basename
  namespace, so
  using an identical name would collide. Each initialization also has a
  monotonic `/eN` lifetime suffix. Without it a faster locality can look up the
  preceding world before the root finishes unregistering that old name during
  cleanup. Every newly created group still starts its generations at one.
* `run_as_hpx_thread` creates a default-stack thread. The additional dispatch
  above ensures that even the inline final FFTW job has a large stack.
* The component pkg-config file includes `-shared`. Configure removes that
  linker-mode switch so libtool can honor FFTW's static/shared options; it
  preserves the dependency libraries. Programs use `hpx_application` flags.
* The unchanged kernel reserves four distributed planner slots. The HPX
  internal header gives those same numeric slots HPX names and checks their
  endpoint at compile time.
* The original distributed benchmark obtains its main function from
  `libbench2`. The HPX C entry forwards its unchanged `bench_main` body.
* The launcher inserts the `--` delimiter required by `hpxrun.py` before the
  program. It explicitly selects TCP even for one locality, where hpxrun does
  not apply its parcelport selection itself.

## License and citation

The new HPX implementation and this README are Copyright (c) 2026 Dominic C.
Marcello and licensed under the **GNU General Public License, version 2 or
(at your option) any later version**. See [COPYING](../COPYING). They are
provided without warranty. FFTW's original copyrights and license notices
remain in force, including its public header's original notice. Copied files
identify the 2026 modification; new implementation files carry the full GPL
v2-or-later notice.

When citing FFTW, use Matteo Frigo and Steven G. Johnson, “The Design and
Implementation of FFTW3,” *Proceedings of the IEEE*, 93(2), 216–231, February
2005. [DOI: 10.1109/JPROC.2004.840301](https://doi.org/10.1109/JPROC.2004.840301);
[official paper PDF](https://www.fftw.org/fftw-paper-ieee.pdf). The paper
covers upstream FFTW; this repository documents its HPX transport port.
