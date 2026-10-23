# fftw3-hpx local validation, 2026-10-22

This historical report covers the initial port. The later pooled-receive
implementation has [updated local validation](../benchmarks/queenbee/optimization/integration_validation/README.md)
and [matched QueenBee results](../benchmarks/queenbee/optimization/README.md).

This report covers the local HPX port of FFTW 3.3.11. The implementation
under test is commit `6c4be8476dea600bab1fdaa8c5aa64f3fa32575f`; subsequent
README/report changes do not alter the tested implementation. Local builds
and numerical tests use the requested HPX 1.11.0 installation at
`/home/dmarce1/local/hpx/Release` with matching dependencies selected below.

TCP is permitted only between localities on the **same server**. All results
here use local processes and the TCP parcelport. Multi-server execution must
use HPX's MPI parcelport with TCP disabled and is a separate validation task.
No cluster result is claimed by this report. Public repository publication
and the subsequently authorized QB4 work are separate from these results.

## Source and commits

The source is the [official release tarball](https://fftw.org/fftw-3.3.11.tar.gz),
verified before extraction:

```text
5630c24cdeb33b131612f7eb4b1a9934234754f9f388ff8617458d0be6f239a1
```

The tarball was extracted into a fresh empty temporary directory, then copied
into `/home/dmarce1/workspace/fftw3-hpx`, the directory the user selected after
clarifying the underscore/hyphen discrepancy. No upstream Git checkout,
OCaml, codelet generation, maintainer mode, or FFTW CMake build was used.

| Commit | Change |
| --- | --- |
| `c9fbc88d783536635e1718c2053e96ad84b66a9f` | Import FFTW 3.3.11 release tarball |
| `e44290a08763428a9d1d1fa7c5f0c9650539e2d6` | Copy mpi/ to hpx/ as the starting point for the HPX port |
| `e67b230` | Record HPX port implementation instructions |
| `1e88e08` | Port distributed FFTW communication and worker callbacks to HPX |
| `3e40c01` | Add optional HPX libraries and verification targets to autotools |
| `d2eb8cf` | Port distributed benchmark and test HPX communicator lifecycle |
| `6c4be84` | Reject mismatched HPX and Boost headers during configure |

The source audit reports an exact match of all **4,885 release files and
modes** in the baseline commit. The second commit contains the unmodified
copy. The release contains pre-existing trailing whitespace; it was retained
in these two commits to preserve the exact source.

The following protected-source audit has an empty diff:

```sh
git diff c9fbc88 -- mpi kernel dft rdft reodft simd-support threads api genfft \
    COPYING COPYRIGHT AUTHORS
```

Every retained copied file has the required modification notice. The only
remaining legacy identifier matches under `hpx/` are two explanatory comment
lines in `ifftw-hpx.h` documenting the unchanged kernel's distributed planner
enum slots. New bridge code includes public FFTW declarations but no FFTW
internal C headers. A normalized token comparison confirms public prototype
parity after the intended prefix/communicator replacements and the new
`comm_world` declaration. Algorithm source changes are limited to those
replacements, communication calls, initialization/cleanup, and notices.

GNU `diff` does not provide `--stat`; the corresponding summary command is:

```sh
git diff --no-index --stat -- mpi hpx
```

Its exit status 1 means the directories differ. The final summary in
`build/logs/mpi_hpx_stat_final.log`, including the documentation, reports
`55 files changed, 2719 insertions(+), 2628 deletions(-)`.
This includes omission of the distributed Fortran interface and the added
implementation, verification programs, build glue, and documentation.

## Workstation dependencies and recovery

The local compiler is GCC/G++ 15.2.0; regeneration used Autoconf 2.72 and
Automake 1.18.1. Build concurrency was reduced below the 12-core ceiling:
stock FFTW used seven make jobs; the final matching-dependency precision
builds ran concurrently with two jobs each, for six build jobs in total.
Tests were serialized with `make -j1`; the largest HPX test allocation is three localities with two workers
per locality. No GPU computation is required by the port.

The original installed HPX metadata did not work unchanged after the local
operating-system upgrade:

1. Initial linking failed with `cannot find -lcuos` and `cannot find -lmpi_cxx`.
   The missing CUDA library was named in HPX's pkg-config metadata, but neither
   HPX nor the retained CUDA libraries required it in their dynamic dependency
   lists. Its entry was removed only from build-local copies of the metadata.
2. Default MPI resolution mixed Open MPI 5's `libmpi.so.40.40.7` with the old
   Open MPI 4 C++ library. Relocation inspection reported unresolved
   `ompi_mpi_errors_throw_exceptions` and `ompi_op_set_cxx_callback`. The genuine
   packaged Open MPI 4 libraries still installed on disk were selected using
   build-local symlinks; no replacement library or MPI shim was written.
3. An unoptimized combined-precision link exposed mismatched Boost headers:
   installed HPX exports its Boost 1.83 version symbol, while the system headers
   are Boost 1.90. Earlier optimized links had discarded that diagnostic check.
   The official Boost 1.83 headers were installed only under the build directory
   and all precision builds' C++ objects were rebuilt. Configure now requires
   live link references to the HPX and Boost version symbols so optimization
   cannot hide this mismatch.

The Boost archive is
[`boost_1_83_0.tar.bz2`](https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2).
Its [official metadata](https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.bz2.json)
and the downloaded archive agree on SHA256:

```text
6478edfe2f3305127cffe8caf73ea0176c53769f4bf1585be237eb30798c3b8e
```

The local library targets are:

| Link names in `build/hpx_compat/lib` | Original installed target |
| --- | --- |
| `libmpi.so`, `libmpi.so.40` | `/usr/lib/x86_64-linux-gnu/libmpi.so.40.30.6` |
| `libmpi_cxx.so`, `libmpi_cxx.so.40` | `/usr/lib/x86_64-linux-gnu/libmpi_cxx.so.40.30.1` |
| `libopen-pal.so.40` | `/usr/lib/x86_64-linux-gnu/libopen-pal.so.40.30.3` |
| `libopen-rte.so.40` | `/usr/lib/x86_64-linux-gnu/libopen-rte.so.40.30.3` |

`build/logs/hpx_dependency_compat.log` contains the target hashes and clean
relocation output. Four HPX pkg-config files were copied into
`build/hpx_compat/pkgconfig`: the component/application files and their
release variants. Their changes are removal of `-lcuos`, replacement of the
obsolete MPI library search directory by the compatibility directory, and
prepending `-I/home/dmarce1/workspace/fftw3-hpx/build/hpx_compat/boost_headers`
to `Cflags`. The Boost extraction retains its upstream license. No system
file or installed HPX file was modified.

The exact successful environment, saved in the ignored local file
`build/hpx_env.sh`, is:

```sh
export PKG_CONFIG_PATH=/home/dmarce1/workspace/fftw3-hpx/build/hpx_compat/pkgconfig
export LD_LIBRARY_PATH=/home/dmarce1/workspace/fftw3-hpx/build/hpx_compat/lib:/home/dmarce1/local/hpx/Release/lib
export PATH=/home/dmarce1/local/hpx/Release/bin:$PATH
```

On this existing checkout, source that file before building or testing. A
fresh checkout does not contain `build/`. On another machine, use coherent
HPX/Boost/MPI installations instead of copying these machine-specific paths.
To reconstruct this workstation's environment, create the compatibility
subdirectories, make the links listed above, verify and extract the Boost
archive's `boost/` tree and `LICENSE_1_0.txt` into `boost_headers`, and apply the
three metadata changes to copies of the four installed `.pc` files. Preserve
all remaining include/link flags and use the environment above. The port's
configure check is the gate for a matching HPX/Boost header/library set.

## Configure and build commands

Autotools was regenerated with:

```sh
autoreconf -fi
```

Only top-level build glue and the new `hpx/` generated Makefile were retained;
unrelated regenerated release files were restored to the pristine contents.
Autoreconf completed with existing upstream portability/deprecation warnings.
Maintainer mode was not enabled.

The successful final precision builds used these configure options and make
job counts, with the matching dependency environment sourced first:

```sh
cd /home/dmarce1/workspace/fftw3-hpx
. build/hpx_env.sh
(cd build/double && ../../configure --enable-hpx --enable-threads && make -j2)
(cd build/single && ../../configure --enable-hpx --enable-threads --enable-float && make -j2)
(cd build/long_double && ../../configure --enable-hpx --enable-threads --enable-long-double && make -j2)
```

All three configure and build steps passed. Their logs are
`build/logs/configure_{double,single,long_double}_matched.log` and
`build/logs/build_{double,single,long_double}_matched.log`. Earlier C++ objects
compiled with the mismatched headers were explicitly removed before these
rebuilds.

The independent stock build used:

```sh
(cd build/stock && ../../configure && make -j7 && make -j1 check)
```

It passed with `FFTW transforms passed basic tests!`; see the `configure_stock`,
`build_stock`, and `check_stock` logs. This configure omitted HPX and threading.

Negative configure checks passed by rejecting each invalid request with exit
status 1 and the corresponding diagnostic:

| Request | Required diagnostic |
| --- | --- |
| `../../configure --enable-hpx` | `--enable-hpx requires --enable-threads` |
| `../../configure --enable-hpx --enable-threads --enable-quad-precision` | `quad precision is not supported in HPX` |
| HPX enabled with system Boost 1.90 headers against this HPX build | `HPX/Boost header and library link check failed` |

The last case overrides `HPX_CFLAGS` with the uncorrected installed
`hpx_component` Cflags while retaining the corrected library search path.
Exact commands are in `build/check_configure_rejections.sh`; output is in
`build/logs/configure_rejections.log`.

## Final acceptance commands and results

The local runner is `build/run_final_acceptance.sh`. From the repository root,
it sources `build/hpx_env.sh`, runs each command below sequentially, saves its
exact shell-escaped command in `build/logs/<label>.command`, saves output in
`build/logs/<label>.log`, and appends exit status and elapsed seconds to
`build/logs/final_results.tsv`. It stops immediately on any nonzero exit.

```sh
timeout --signal=TERM --kill-after=10s 120s sh hpx/hpx-run.sh /home/dmarce1/local/hpx/Release/bin/hpxrun.py 3 2 /home/dmarce1/workspace/fftw3-hpx/build/combined_precision_smoke

timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/double/hpx check NUMCHECK=2 CHECKSIZE=10000 CHECK_PL_OPTS=--validate-wisdom
timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/double check

timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/single/hpx check NUMCHECK=2 CHECKSIZE=10000 CHECK_PL_OPTS=--validate-wisdom
timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/single check

timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/long_double/hpx check NUMCHECK=2 CHECKSIZE=10000 CHECK_PL_OPTS=--validate-wisdom
timeout --signal=TERM --kill-after=10s 1800s make -j1 -C build/long_double check

timeout --signal=TERM --kill-after=10s 3600s make -j1 -C build/double/hpx bigcheck
```

<!-- FINAL_RESULTS_BEGIN -->
| Label | Exit status | Elapsed seconds | Result |
| --- | --- | --- | --- |
| `combined_precision_matched` | 0 | 0 | PASS |
| `wisdom_double_matched` | 0 | 15 | PASS |
| `check_all_double_matched` | 0 | 90 | PASS |
| `wisdom_single_matched` | 0 | 21 | PASS |
| `check_all_single_matched` | 0 | 91 | PASS |
| `wisdom_long_double_matched` | 0 | 20 | PASS |
| `check_all_long_double_matched` | 0 | 196 | PASS |
| `bigcheck_double_matched` | 0 | 491 | PASS |
<!-- FINAL_RESULTS_END -->

All eight final acceptance commands completed with exit status zero. Double
precision `bigcheck` completed the full five-configuration matrix at
`NUMCHECK=100`, `CHECKSIZE=60000` in 491 seconds, including three localities
with two workers. The final runner printed `FINAL ACCEPTANCE PASS`.

Each full top-level precision check includes the upstream serial and threaded
checks and the entire HPX matrix: 1, 2, 3, and 4 localities with one worker,
then 3 localities with two workers. The regular matrix uses `NUMCHECK=10` and
`CHECKSIZE=10000`. The integer printed by upstream check.pl is its random
geometry count; each geometry can exercise multiple transform variants.
Representative successful output is:

```text
FFTW transforms passed basic tests!
FFTW threaded transforms passed basic tests!
communication check PASS
HPX FFTW transforms passed 10 tests, 1 locality, 1 thread
HPX FFTW transforms passed 10 tests, 2 localities, 1 thread each
HPX FFTW transforms passed 10 tests, 3 localities, 1 thread each
HPX FFTW transforms passed 10 tests, 4 localities, 1 thread each
HPX FFTW threaded transforms passed 10 tests, 3 localities, 2 threads each
```

The wisdom matrix runs the same locality/worker combinations with two random
geometries per configuration. It removes old wisdom, verifies the transforms,
gathers and writes wisdom, then reruns the same transforms with imported,
broadcast wisdom and wisdom-only planning. The default verification plans
use measure mode. Every recorded pass completed within its timeout.

The communication check additionally exercises shared duplicated handles,
interleaved generations, repeated cached splits with reversed keys, repeated
channel tags, zero-length messages, variable all-to-all offsets/counts, nested
worker callbacks, large-stack assertions, and two init/cleanup lifetimes.
The combined-precision smoke executable links all three precision libraries
into one process per locality and reports:

```text
combined double/single/long-double precision smoke PASS
```

Its build command and source are retained locally in
`build/compile_combined_precision_smoke.sh` and
`build/combined_precision_smoke.cpp`; it is supplementary to the repository's
regular acceptance targets. These tests establish numerical verification
against FFTW's inherited checks; they are not performance comparisons with
the original MPI implementation. Shared-library installation and cross-server
MPI parcelport execution are outside these local results.

## Installed-HPX adaptations and resolved failures

- Collective and channel communicators use separate `/collective` and
  `/channel` suffixes because HPX 1.11 registers both in the same AGAS namespace.
- A lifecycle stress test initially reported a generational sequencing error
  on the second initialization. A fast locality could resolve the old world
  before another locality unregistered it. The monotonically increasing
  `/world/eN` lifetime suffix fixes this; generation counters still begin at
  one for each new group. The final two-lifetime checks pass in every precision.
- HPX's `run_as_hpx_thread` creates a default-stack thread. The non-HPX callback
  path therefore uses it only as a trampoline to a large-stack executor, so
  the final inline FFTW job also gets a large stack.
- The component pkg-config `-shared` switch is stripped by configure so
  libtool controls static/shared output. Dependency flags remain; application
  targets use the separate `hpx_application` flags.
- The unchanged FFTW kernel's four distributed planner indices are reused
  under HPX names, with a compile-time endpoint check. No kernel edit is needed.
- The original benchmark's C `main` comes from `libbench2/main.c`; the new C
  entry forwards unchanged `bench_main` and the C++ launcher supplies `main`.
- `hpxrun.py` needs `--` before application arguments and applies its TCP
  selection only for more than one locality. The wrapper explicitly selects
  TCP for every local run, disables the MPI parcelport, clears inherited node
  and extra-argument settings, requires zero exits, and disables conflicting
  per-process CPU binding. Worker counts and benchmark arguments are preserved.

The default path retains the original FFTW algorithm, data distribution,
scheduling decisions, flags, and planner hook logic. The copied Fortran wrapper/generator
files are omitted as requested. README documentation and the Git ignore file
are the additional repository documentation/build-workflow changes beyond
`hpx/` and autotools glue.

## Experimental all-to-all transpose, 2026-10-23

The opt-in `FFTW_HPX_TRANSPOSE_EXCHANGE=all_to_all` path passed local
double, single, and long-double validation. Each precision passed the full
ten-geometry verification matrix at 1, 2, 3, and 4 localities with one worker,
and 3 localities with two workers. Explicit `pairwise` mode passed the
two-geometry matrix in each precision. Both modes also passed forward,
backward, and out-of-place checks for 2×2×2 on four localities and 5×7×3 on
three localities, using two workers each.

The assertion-enabled communication check now exercises the wide-count
transpose helper with overlapping buffers, differing displacements,
untouched gap sentinels, empty blocks, zero active peers, inactive ranks, and
repeated generations across two initialization/cleanup cycles. Existing
message ownership, rendezvous, communicator, and nested-thread checks pass.
These tests used same-server TCP only, with no more than eight workers per
run and builds limited to two concurrent compiler processes.

The local serial/threaded FFTW archive hashes are unchanged. The upstream
`mpi`, `kernel`, `dft`, `rdft`, `reodft`, `simd-support`, `threads`, `api`, and
`genfft` trees match the pristine release. HPX itself is unchanged. Logs and
commands are retained under `build/qb_alltoall/local`; the frozen source and
QueenBee job inputs are under `build/qb_alltoall/bundle`.

QueenBee job 1126247 completed with exit `0:0` for the unchanged 1024³
benchmark on four exclusive nodes, one process per node, 64 workers, the
MPI parcelport, and no TCP. All 42 timed samples, 18 primary numerical checks,
12 preliminary numerical checks, eight rank-level communication passes,
normalized local plans, and source/binary preservation checks passed.
The all-to-all medians were 12.786 and 12.805 seconds, compared with 3.498
and 3.499 seconds for pairwise and 3.353 and 3.371 seconds for FFTW-MPI.
The default remains pairwise. The
[completed comparison](../benchmarks/queenbee/remaining_overhead/all_to_all/README.md)
preserves the exact frozen inputs, raw logs, commands, accounting, local
validation snapshot, and reproducible timing summary.

## License

This validation report is Copyright (c) 2026 Dominic C. Marcello and is
licensed under the GNU General Public License, version 2 or (at your option)
any later version. It is provided without warranty. See [COPYING](../COPYING).
All upstream source and dependency license notices are preserved.
