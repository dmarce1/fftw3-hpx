#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_1024
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --time=01:00:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_benchmark_20261022/slurm-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_benchmark_20261022/slurm-%j.err
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

set -Eeuo pipefail
: "${SLURM_JOB_ID:?This script must run in its four-node Slurm allocation}"
qb_root=/work/dmarce1/fftw3_hpx_benchmark_20261022
qb_hpx=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_source=$qb_root/source
qb_build=$qb_root/build
qb_results=$qb_root/results/$SLURM_JOB_ID
mkdir -p "$qb_results" "$qb_build"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
exec 3> "$qb_results/commands.log"
export BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
qb_stage=setup
qb_source_commit=unknown

finish()
{
    local result=$1
    trap - EXIT
    set +e
    set +x
    local outcome=FAIL
    if [ "$result" -eq 0 ]; then
        outcome=PASS
    fi
    {
        printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\n' \
            "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage"
        printf 'source_commit\t%s\nfinished_utc\t%s\n' \
            "$qb_source_commit" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_root/FINAL_STATUS.tmp"
    mv "$qb_root/FINAL_STATUS.tmp" "$qb_root/FINAL_STATUS"
    printf 'FINAL_STATUS %s exit=%s stage=%s results=%s\n' \
        "$outcome" "$result" "$qb_stage" "$qb_results"
    exit "$result"
}
trap 'finish "$?"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
set -x

run_log()
{
    local label=$1
    shift
    qb_stage=$label
    printf 'START %s %s\n' "$label" "$(date -u +%FT%TZ)"
    {
        printf 'cd %q\n' "$PWD"
        printf '%q ' "$@"
        printf '\n'
    } > "$qb_results/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"
    printf 'PASS %s %s\n' "$label" "$(date -u +%FT%TZ)"
}

# One allocation, one rank per node, identical placement and environment.
[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$qb_hpx/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hpx/lib64:$qb_hpx/lib:${LD_LIBRARY_PATH:-}"
export CC=gcc CXX=g++ MPICC="$qb_mpi/bin/mpicc"
export CFLAGS='-O3 -march=native'
export CXXFLAGS='-O3 -march=native'
export HPXRUN
HPXRUN=$(readlink -f "$qb_hpx/bin/hpxrun.py")
test -f "$HPXRUN"
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
export OMPI_MCA_accelerator=null
export OMPI_MCA_pml=ucx
export OMPI_MCA_btl=self,sm
export UCX_TLS=rc,sm,self
# These runs use the MPI parcelport across servers; TCP data transport is off.
unset HPXRUN_NODES HPXRUN_ARGS
read -r qb_source_commit < "$qb_root/SOURCE_COMMIT"
[[ "$qb_source_commit" =~ ^[0-9a-f]{40}$ ]]
cp "$qb_root/SOURCE_COMMIT" "$qb_results/SOURCE_COMMIT"
cp "$0" "$qb_results/job.sbatch"
cd "$qb_root"
{
    date -u
    hostname
    printf 'source_commit=%s\n' "$qb_source_commit"
    printf 'source=%s\nbuild=%s\nhpx=%s\nmpi=%s\n' \
        "$qb_source" "$qb_build" "$qb_hpx" "$qb_mpi"
    printf 'placement=one rank per node, 64 workers, no CPU binding, NUMA interleave all\n'
    module -t list 2>&1
    gcc --version
    g++ --version
    "$qb_mpi/bin/mpiexec" --version
    "$qb_mpi/bin/mpicxx" --showme
    cmake --version
    for name in PATH LD_LIBRARY_PATH CC CXX MPICC CFLAGS CXXFLAGS HPXRUN \
        APEX_DISABLE HWLOC_COMPONENTS OMPI_MCA_accelerator OMPI_MCA_pml \
        OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST SLURM_CPUS_PER_TASK; do
        printf '%s=%s\n' "$name" "${!name-}"
    done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 \
    --ntasks-per-node=1 --cpus-per-task=1 --label \
    sh -c 'hostname; uname -a; lscpu; numactl --show'
sha256sum "$qb_root/SOURCE_COMMIT" "$qb_results/job.sbatch" \
    "$qb_root/helpers/hpx_cmake_flags.py" \
    "$qb_source/benchmarks/matched_3d.cpp" > "$qb_results/input_sha256.txt"
(cd "$qb_source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/source_sha256.txt"

# CMake queries the installed HPX metadata only; FFTW itself uses autotools.
run_log hpx_metadata python3 "$qb_root/helpers/hpx_cmake_flags.py" \
    "$qb_hpx" "$qb_results/hpx_metadata" \
    "-DCMAKE_CXX_COMPILER=$(command -v g++)" \
    "-DMPI_CXX_COMPILER=$qb_mpi/bin/mpicxx" "-DMPI_HOME=$qb_mpi"
. "$qb_results/hpx_metadata/hpx-flags.sh"
cd "$qb_build"
run_log configure "$qb_source/configure" --enable-hpx --enable-mpi \
    --enable-threads --enable-sse2 --enable-avx --enable-avx2
cp config.log config.status "$qb_results/"
run_log build make -j32

# Both executables link exactly the same serial FFTW and pthread libraries.
read -r -a qb_hpx_cflags <<< "$HPX_APP_CFLAGS"
read -r -a qb_hpx_libs <<< "$HPX_APP_LIBS"
run_log compile_mpi "$qb_mpi/bin/mpicxx" -O3 -march=native -std=c++20 \
    -I"$qb_source/api" -I"$qb_source/mpi" \
    "$qb_source/benchmarks/matched_3d.cpp" \
    "$qb_build/mpi/.libs/libfftw3_mpi.a" \
    "$qb_build/threads/.libs/libfftw3_threads.a" "$qb_build/.libs/libfftw3.a" \
    -lm -pthread -o "$qb_build/matched_3d_mpi"
run_log compile_hpx g++ -O3 -march=native -std=c++20 -DFFTW_BENCH_HPX \
    -I"$qb_source/api" -I"$qb_source/hpx" "${qb_hpx_cflags[@]}" \
    "$qb_source/benchmarks/matched_3d.cpp" \
    "$qb_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_build/threads/.libs/libfftw3_threads.a" "$qb_build/.libs/libfftw3.a" \
    "${qb_hpx_libs[@]}" -lm -pthread -o "$qb_build/matched_3d_hpx"
sha256sum "$qb_build/matched_3d_mpi" "$qb_build/matched_3d_hpx" \
    "$qb_build/mpi/.libs/libfftw3_mpi.a" "$qb_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_build/threads/.libs/libfftw3_threads.a" "$qb_build/.libs/libfftw3.a" \
    > "$qb_results/binary_sha256.txt"
run_log mpi_dependencies ldd "$qb_build/matched_3d_mpi"
run_log hpx_dependencies ldd "$qb_build/matched_3d_hpx"

# Analytic spectrum and inverse checks run before sampling in both drivers.
# There is one MPI run followed by one HPX run; no retry or polling loop.
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_build/matched_3d_mpi" "${qb_options[@]}"
run_log benchmark_hpx "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_build/matched_3d_hpx" --hpx:ignore-batch-env --hpx:localities=4 \
    --hpx:threads=64 --hpx:bind=none --hpx:ini=hpx.parcel.mpi.enable=1 \
    --hpx:ini=hpx.parcel.mpi.priority=1000 --hpx:ini=hpx.parcel.tcp.enable=0 \
    --hpx:ini=hpx.parcel.bootstrap=mpi "${qb_options[@]}"
qb_stage=validate_output
for backend in mpi hpx; do
    log="$qb_results/benchmark_$backend.log"
    [ "$(grep -c "^SAMPLE backend=$backend " "$log")" -eq 7 ]
    [ "$(grep -c "^CHECK backend=$backend " "$log")" -eq 3 ]
    grep -E "^RESULT backend=$backend extent=1024 ranks=4 threads=64 samples=7 .*status=PASS$" \
        "$log" >> "$qb_results/RESULTS.txt"
done
qb_stage=complete
printf 'MATCHED_BENCHMARK_PASS source=%s results=%s\n' "$qb_source_commit" "$qb_results"
