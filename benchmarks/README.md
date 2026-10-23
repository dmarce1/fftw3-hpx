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

# Matched distributed 3D benchmark

`matched_3d.cpp` compiles into either an HPX or stock MPI application. Both
use double precision, an in-place complex transform, FFTW's normal slab
distribution, `FFTW_ESTIMATE`, and the requested FFTW thread count. They use
the same serial FFTW implementation when linked from one build configured
with `--enable-hpx --enable-mpi --enable-threads`.

For `--size=1024`, the logical array is 16 GiB in total, or 4 GiB per rank
with four ranks. FFTW workspace and communication buffers require additional
memory. No full global field is allocated on each rank and no full-field
gather is used.

Before timing, the program fills a sum of three analytic complex Fourier
modes, checks the entire forward spectrum, and checks the normalized inverse
round trip. Per-axis phasor tables avoid trigonometric evaluations inside the
grid loops. Global maximum relative errors must be finite and at most
`1e-10`. The final accumulated round trip is checked again after sampling.

Two forward/inverse warmups precede seven timed forward transforms by
default. Each sample starts after a collective barrier. Its reported time
is the maximum of the rank/locality elapsed times measured with
`std::chrono::steady_clock`. The barrier, reduction, output, inverse
transform, and normalization are outside the timer. The inverse restores
bounded input values between samples. `SAMPLE` lines preserve all measured
values; `RESULT` reports their minimum, correctly sorted median, arithmetic
mean, and maximum. Planning is reported separately, and rank zero prints
both plans. `FFTW_ESTIMATE` makes planner policy identical and bounded;
printed plans provide evidence of the algorithms actually selected.

The HPX application forces the MPI parcelport and disables TCP. Its FFTW
work runs on a large-stack HPX thread and its independent statistics
communicator does not consume FFTW communicator generations. `--threads`
must equal the HPX worker count.

`summarize.py MPI_LOG HPX_LOG` checks complete successful outputs, matching
problem parameters, and the reported statistics before emitting a JSON
comparison. It also compares the printed plans after replacing the transport
prefix. The reported ratio is HPX median time divided by MPI median time;
values above one mean HPX took longer.

For an installed HPX with pkg-config metadata disabled,
`hpx_cmake_flags.py HPX_PREFIX OUTPUT_DIR` evaluates its exported CMake
dependency targets and writes `OUTPUT_DIR/hpx-flags.sh`. Source that file to
set the four HPX compiler/linker variables before running FFTW's autotools
configure. Additional CMake `-D` arguments can select the matching compiler
and MPI installation. CMake is used only to inspect dependency metadata;
FFTW is still built with autotools. The application target uses explicit
`hpx::init` and does not wrap `main`.

`queenbee/job.sbatch` records the four-node QueenBee job configuration. Its
paths identify the installation and source bundle used for that experiment;
they must be adjusted before using the script on another installation.

## Build from one configured FFTW tree

Set `PKG_CONFIG_PATH` to the chosen HPX installation before configuring and
compiling. From the source directory, with a combined double-precision build
in `build/combined`, the following commands use that build's uninstalled
libraries. Use identical optimization and architecture flags for both
executables and the underlying FFTW libraries.

```sh
src_dir=$PWD
build_dir=$PWD/build/combined

"$build_dir/libtool" --tag=CXX --mode=link c++ -O3 -march=native -std=c++20 \
  -DFFTW_BENCH_HPX -I"$src_dir/api" -I"$src_dir/hpx" \
  $(pkg-config --cflags hpx_application) \
  "$src_dir/benchmarks/matched_3d.cpp" \
  "$build_dir/hpx/libfftw3_hpx.la" \
  "$build_dir/threads/libfftw3_threads.la" "$build_dir/libfftw3.la" \
  $(pkg-config --libs hpx_application) -lm -pthread \
  -o "$build_dir/matched_3d_hpx"

"$build_dir/libtool" --tag=CXX --mode=link mpicxx -O3 -march=native -std=c++20 \
  -I"$src_dir/api" -I"$src_dir/mpi" \
  "$src_dir/benchmarks/matched_3d.cpp" \
  "$build_dir/mpi/libfftw3_mpi.la" \
  "$build_dir/threads/libfftw3_threads.la" "$build_dir/libfftw3.la" \
  -lm -pthread -o "$build_dir/matched_3d_mpi"
```

## Run inside an allocation

Use the scheduler's supported launcher with exactly one process per node,
the same node list, and the same CPU allocation and binding for both runs.
Four nodes with 64 allocated CPU workers per process use:

```text
<allocated MPI launcher: 4 processes, 1 per node, 64 CPUs each> \
  build/combined/matched_3d_mpi \
  --size=1024 --threads=64 --warmups=2 --samples=7

<same allocated MPI launcher and CPU placement> \
  build/combined/matched_3d_hpx \
  --hpx:localities=4 --hpx:threads=64 \
  --size=1024 --threads=64 --warmups=2 --samples=7
```

The launcher placeholders must be replaced with the allocation's actual
launcher and affinity flags. In particular, do not use a local-only HPX
test wrapper, TCP transport, or SSH per process. Capture the allocation,
node list, CPU placement, compiler versions, configure flags, source commit,
HPX installation, MPI implementation, exact launcher commands, and complete
outputs. Run the two executables sequentially. Report the actual plan texts
alongside timings; a single matched run measures these configurations and
does not establish a general scaling result.

For a local smoke test, reduce the size and thread count, for example
`--size=16 --threads=1 --warmups=2 --samples=7`, and match the HPX worker
count to one. Both variants still require their MPI runtime to be launched
in the supported way.

This benchmark and this README are licensed under the GNU GPL, version 2
or, at your option, any later version. See the repository's `COPYING`.
