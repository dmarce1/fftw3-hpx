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

# QueenBee: one matched 1024³ transform

On October 22, 2026, FFTW-HPX took **4.0351 times as long** as stock FFTW-MPI
for this configuration: a 1024 × 1024 × 1024 double-complex transform on
four QueenBee nodes, one rank/locality per node and 64 workers per process.
Both implementations passed all correctness checks. This is one problem
size and resource configuration with `FFTW_ESTIMATE`, not a scaling study.

| Backend | Minimum (s) | Median (s) | Mean (s) | Maximum (s) |
| --- | ---: | ---: | ---: | ---: |
| FFTW-MPI | 3.265632567 | 3.325044719 | 3.320600687 | 3.361820403 |
| FFTW-HPX | 13.218385993 | 13.416974209 | 13.435681823 | 13.672225612 |

The ratio is `13.416974209 / 3.325044719 = 4.0351259435`, or 303.51% more
time for HPX. All times measure forward execution only. The printed forward
and inverse plans match exactly after replacing `hpx-` with `mpi-`. Both
select **pairwise transposes**. The run was not profiled, so these measurements
do not establish the cause of the performance difference.

## Measurement and correctness

Both executables were compiled from the same [driver](../matched_3d.cpp)
and linked to the same serial and threaded FFTW static archives. The MPI
backend uses the unmodified FFTW 3.3.11 MPI implementation; the HPX backend
uses the port in `hpx/`. The transform is in-place, with normal slab layout
and `FFTW_ESTIMATE` planning. The logical array contains 16 GiB of complex
data, distributed as 4 GiB per process, plus workspace and runtime storage.

The driver initializes a dense sum of three analytic Fourier modes, checks
the complete forward spectrum, and checks a normalized inverse. It performs
two forward/inverse warmups followed by seven timed forward transforms.
Each sample starts after a collective barrier and reports the maximum
`steady_clock` duration over all four ranks/localities. The barrier,
statistics reduction, printing, planning, and inverse/normalization are
outside the timer. A final normalized round trip is checked after sampling.
There is no full-field gather. MPI ran first and HPX second within the same
exclusive allocation.

| Sample, in execution order | MPI (s) | HPX (s) |
| --- | ---: | ---: |
| 0 | 3.361820403 | 13.493471864 |
| 1 | 3.265632567 | 13.329390501 |
| 2 | 3.350244935 | 13.218385993 |
| 3 | 3.310533624 | 13.555867246 |
| 4 | 3.325044719 | 13.363457339 |
| 5 | 3.295766080 | 13.672225612 |
| 6 | 3.335162478 | 13.416974209 |

| Relative maximum error | MPI | HPX |
| --- | ---: | ---: |
| Analytic forward spectrum | 7.32490e-16 | 7.61607e-16 |
| Initial normalized round trip | 1.39870e-15 | 1.44342e-15 |
| Final normalized round trip | 5.19613e-15 | 5.92579e-15 |

Every error is finite and below the `1e-10` acceptance tolerance. Both logs
report `status=PASS`. The [result checker](../summarize.py) and an independent
review recomputed all statistics, checked sample indices 0–6 and all three
correctness stages, and compared both printed plans.

## Allocation, dependencies, and transport

Slurm job **1125135**, account `loni_graphshpx`, partition `workq`, completed
with exit `0:0`. The allocation ran from 21:44:14 to 21:54:38 CDT on October
22, 2026 (02:44:14–02:54:38 UTC on October 23), including the build and both
runs. Four exclusive nodes, `qbd105` through `qbd108`, supplied 256 CPU cores.
Each node has two Intel Xeon Platinum 8358 CPUs at a nominal 2.60 GHz,
32 cores per socket, one hardware thread per core, and four NUMA domains.

Both programs used `mpiexec -n 4 --map-by ppr:1:node --bind-to none` and
`numactl --interleave=all`. HPX also used `--hpx:threads=64 --hpx:bind=none`.
These settings leave CPU placement to the operating system while spreading
memory across NUMA domains. The [exact MPI command](1125135/benchmark_mpi.command)
and [exact HPX command](1125135/benchmark_hpx.command) are preserved.

The stack was GCC/G++ 13.2.0, Open MPI 5.0.11, HPX 1.11.0, and Boost 1.83.0.
The [installed HPX configuration](1125135/installed_hpx_config.txt) has its
MPI parcelport enabled, TCP parcelport compiled out, and thread-stack mmap
disabled. The launch explicitly enables MPI,
disables TCP, and selects MPI bootstrap. Open MPI uses UCX with
`UCX_TLS=rc,sm,self`; its enabled data transports exclude TCP. CPU-only
hardware discovery and APEX disabling were set for both runs:

```sh
APEX_DISABLE=1
HWLOC_COMPONENTS=-cuda,-nvml,-opencl
OMPI_MCA_accelerator=null
OMPI_MCA_pml=ucx
OMPI_MCA_btl=self,sm
UCX_TLS=rc,sm,self
```

The HPX runtime links jemalloc and APEX, with APEX disabled at execution.
The MPI baseline uses its ordinary runtime. This comparison therefore
includes the complete runtime configurations as recorded, rather than
isolating a single communication operation.

Both FFTW libraries and executables used `-O3 -march=native`. FFTW was built
inside the compute allocation with `make -j32`, using:

```sh
./configure --enable-hpx --enable-mpi --enable-threads \
  --enable-sse2 --enable-avx --enable-avx2
```

The installed HPX did not provide pkg-config files. The
[dependency helper](../hpx_cmake_flags.py) queried its exported CMake targets
with CMake 3.26.5 and supplied the four HPX flags variables to FFTW's
Autotools build. The resolved [flags](1125135/hpx-flags.json),
[environment](1125135/metadata.txt), and compile commands are recorded.

## Reproduction and evidence

The tested source commit is
[`cb205948f773e8e057b14ebbf6fa4df1c7cb994a`](https://github.com/dmarce1/fftw3-hpx/commit/cb205948f773e8e057b14ebbf6fa4df1c7cb994a).
The [batch script](job.sbatch) is the exact submitted script. It and the
dependency/result helpers were published in commit `45bccfb` after source
staging; no transform or benchmark-driver code changed between those commits.
Installation and working-directory paths in the script describe this run
and must be adjusted for a new environment. [Input hashes](1125135/input_sha256.txt)
and [binary hashes](1125135/binary_sha256.txt) identify the executed files.

Raw [MPI output](1125135/benchmark_mpi.log) and
[HPX output](1125135/benchmark_hpx.log) include complete plans, checks,
samples, and summaries. [Slurm accounting](1125135/accounting.txt) records
completion; [node inventory](1125135/node_inventory.log) records hardware.
The [machine-readable comparison](1125135/comparison.json) is reproduced,
from the repository root, with:

```sh
python3 benchmarks/summarize.py \
  benchmarks/queenbee/1125135/benchmark_mpi.log \
  benchmarks/queenbee/1125135/benchmark_hpx.log > /tmp/fftw3_hpx_comparison.json
cmp /tmp/fftw3_hpx_comparison.json benchmarks/queenbee/1125135/comparison.json
(cd benchmarks/queenbee/1125135 && sha256sum -c SHA256SUMS)
```

The full build/configure evidence archive is retained locally at
`build/qb_results_1125135.tar.gz` and remotely at
`/work/dmarce1/fftw3_hpx_benchmark_20261022/results-1125135.tar.gz`.
Its SHA-256, verified after transfer, is
`85f7d24e4d005ea9f060bece58f9708083013b689ffa1be9faec686979d631fd`.
The source archive SHA-256 is
`e02baa2938d1a6e412cbe4c84db9b6eeab9143d36d49ad8a14926a55eb9a3576`.

No benchmark or compiler warnings were reported. The submission wrapper
warned that `--mem` is unsupported; the recorded script requested `--mem=0`,
and the exclusive-node job completed successfully. An inventory-shell
trace-descriptor warning did not prevent hardware capture. Neither affects
the passing numerical checks or recorded timings.

This task used **3 of the authorized 12 login attempts**, conservatively
including the user's manual MFA login. Subsequent commands, job submission,
and transfers reused one persistent connection.

This report and the added benchmark code are Copyright (c) 2026 Dominic C.
Marcello, licensed under the GNU GPL version 2 or, at your option, any later
version. See [COPYING](../../COPYING). The root [README](../../README)
contains the upstream FFTW paper citation and official source-tarball link.
