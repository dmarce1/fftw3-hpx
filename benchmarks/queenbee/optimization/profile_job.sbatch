#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_profile
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_optimize_20261022/profile-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_optimize_20261022/profile-%j.err
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

# Diagnostic-only comparison: one MPI control, then baseline and candidate
# instrumented HPX executables with default MPI progress and one progress
# worker. Source snapshots must already contain instrument.py modifications.
# All variants retain the 1024^3 / 64 workers / 2 warmups / 7 samples case.

set -Eeuo pipefail
: "${SLURM_JOB_ID:?This script must run in its four-node Slurm allocation}"
qb_base_root=${QB_BASE_ROOT:-/work/dmarce1/fftw3_hpx_benchmark_20261022}
qb_root=${QB_ROOT:-/work/dmarce1/fftw3_hpx_optimize_20261022}
qb_hpx=${QB_HPX_PREFIX:-/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install}
qb_mpi=${QB_MPI_PREFIX:-/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install}
qb_base_source=${QB_BASE_SOURCE:-$qb_base_root/source}
qb_base_build=${QB_BASE_BUILD:-$qb_base_root/build}
qb_source=${QB_CANDIDATE_SOURCE:-$qb_root/source}
qb_provenance=${QB_CANDIDATE_PROVENANCE:-$qb_root/CANDIDATE_PROVENANCE}
qb_helper=${QB_HPX_HELPER:-$qb_base_root/helpers/hpx_cmake_flags.py}
qb_summary=${QB_SUMMARIZER:-$qb_source/benchmarks/summarize.py}
qb_jobs=${QB_MAKE_JOBS:-32}
qb_profile_base=${QB_PROFILE_BASELINE_SOURCE:-$qb_root/profile_baseline_source}
qb_profile_candidate=${QB_PROFILE_CANDIDATE_SOURCE:-$qb_root/profile_candidate_source}
qb_results=$qb_root/results/$SLURM_JOB_ID
mkdir -p "$qb_results/bin"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
exec 3> "$qb_results/commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
qb_stage=setup
qb_base_commit=unknown

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
        printf 'baseline_commit\t%s\nfinished_utc\t%s\n' \
            "$qb_base_commit" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_root/PROFILE_FINAL_STATUS.tmp"
    mv "$qb_root/PROFILE_FINAL_STATUS.tmp" "$qb_root/PROFILE_FINAL_STATUS"
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

# Expose immutable original link inputs without copying or rebuilding them.
# No make command runs in the original build, or above a candidate hpx dir.
link_original()
{
    local source=$1 destination=$2
    test -e "$source"
    if [ -e "$destination" ] || [ -L "$destination" ]; then
        [ "$(readlink -f "$destination")" = "$(readlink -f "$source")" ]
    else
        ln -s "$source" "$destination"
    fi
}

build_hpx()
{
    local label=$1 source=$2 build=$3
    [ "$(readlink -f "$source")" != "$(readlink -f "$qb_base_source")" ]
    mkdir -p "$build/threads"
    [ "$(readlink -f "$build")" != "$(readlink -f "$qb_base_build")" ]
    link_original "$qb_base_build/libfftw3.la" "$build/libfftw3.la"
    link_original "$qb_base_build/.libs" "$build/.libs"
    link_original "$qb_base_build/threads/libfftw3_threads.la" "$build/threads/libfftw3_threads.la"
    link_original "$qb_base_build/threads/.libs" "$build/threads/.libs"
    cd "$build"
    run_log "configure_$label" "$source/configure" --enable-hpx --enable-mpi \
        --enable-threads --enable-sse2 --enable-avx --enable-avx2
    cp config.log "$qb_results/configure_$label.config.log"
    cp config.status "$qb_results/configure_$label.config.status"
    run_log "build_$label" make -C hpx -j"$qb_jobs" libfftw3_hpx.la
    sha256sum "$source/hpx/hpx-comm.cpp" "$build/hpx/.libs/libfftw3_hpx.a" \
        > "$qb_results/$label.sha256"
}

compile_hpx()
{
    local label=$1 source=$2 build=$3
    local driver=${4:-$qb_base_source/benchmarks/matched_3d.cpp}
    # Profile drivers contain diagnostic hooks; the MPI control is unchanged.
    run_log "compile_$label" g++ -O3 -march=native -std=c++20 -DFFTW_BENCH_HPX \
        -I"$qb_base_source/api" -I"$source/hpx" "${qb_hpx_cflags[@]}" \
        "$driver" \
        "$build/hpx/.libs/libfftw3_hpx.a" \
        "$qb_base_build/threads/.libs/libfftw3_threads.a" \
        "$qb_base_build/.libs/libfftw3.a" \
        "${qb_hpx_libs[@]}" -lm -pthread -o "$qb_results/bin/$label"
    sha256sum "$driver" "$qb_results/bin/$label" > "$qb_results/$label.binary.sha256"
}

run_hpx()
{
    local label=$1
    local executable=${2:-$label}
    shift
    if [ "$#" -gt 0 ]; then
        shift
    fi
    run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
        "$qb_results/bin/$executable" "${qb_hpx_options[@]}" "$@" "${qb_options[@]}"
    run_log "comparison_$label" python3 -I "$qb_summary" \
        "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log"
}

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
[[ "$qb_jobs" =~ ^[1-9][0-9]*$ ]]
[ "$qb_jobs" -le 64 ]
test -f "$qb_provenance"
test -f "$qb_summary"
read -r qb_base_commit < "$qb_base_root/SOURCE_COMMIT"
[[ "$qb_base_commit" =~ ^[0-9a-f]{40}$ ]]
cp "$qb_base_root/SOURCE_COMMIT" "$qb_results/BASELINE_COMMIT"
cp "$qb_provenance" "$qb_results/CANDIDATE_PROVENANCE"
cp "$0" "$qb_results/job.sbatch"
module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$qb_hpx/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hpx/lib64:$qb_hpx/lib:${LD_LIBRARY_PATH:-}"
export CC=gcc CXX=g++ MPICC="$qb_mpi/bin/mpicc"
export CFLAGS='-O3 -march=native' CXXFLAGS='-O3 -march=native'
export HPXRUN
HPXRUN=$(readlink -f "$qb_hpx/bin/hpxrun.py")
test -f "$HPXRUN"
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
export OMPI_MCA_accelerator=null
export OMPI_MCA_pml=ucx
export OMPI_MCA_btl=self,sm
export UCX_TLS=rc,sm,self
# MPI parcelport plus InfiniBand/shared-memory UCX transports; never TCP.
unset HPXRUN_NODES HPXRUN_ARGS
cd "$qb_root"
{
    date -u
    hostname
    printf 'baseline_commit=%s\nbaseline_source=%s\nbaseline_build=%s\n' \
        "$qb_base_commit" "$qb_base_source" "$qb_base_build"
    printf 'candidate_source=%s\nprofile_baseline_source=%s\nprofile_candidate_source=%s\n' \
        "$qb_source" "$qb_profile_base" "$qb_profile_candidate"
    printf 'placement=one rank per node, 64 workers, no CPU binding, NUMA interleave all\n'
    module -t list 2>&1
    gcc --version
    g++ --version
    "$qb_mpi/bin/mpiexec" --version
    "$qb_mpi/bin/mpicxx" --showme
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
sha256sum "$qb_results/job.sbatch" "$qb_helper" "$qb_summary" "$qb_provenance" \
    > "$qb_results/input.sha256"
sha256sum "$qb_base_source/benchmarks/matched_3d.cpp" \
    "$qb_base_build/mpi/.libs/libfftw3_mpi.a" \
    "$qb_base_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_base_build/threads/libfftw3_threads.la" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" \
    "$qb_base_build/libfftw3.la" "$qb_base_build/.libs/libfftw3.a" \
    > "$qb_results/baseline_inputs.sha256"
(cd "$qb_source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/candidate_source.sha256"
(cd "$qb_profile_base" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/profile_baseline_source.sha256"
(cd "$qb_profile_candidate" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/profile_candidate_source.sha256"

run_log hpx_metadata python3 "$qb_helper" "$qb_hpx" "$qb_results/hpx_metadata" \
    "-DCMAKE_CXX_COMPILER=$(command -v g++)" \
    "-DMPI_CXX_COMPILER=$qb_mpi/bin/mpicxx" "-DMPI_HOME=$qb_mpi"
. "$qb_results/hpx_metadata/hpx-flags.sh"
read -r -a qb_hpx_cflags <<< "$HPX_APP_CFLAGS"
read -r -a qb_hpx_libs <<< "$HPX_APP_LIBS"
build_hpx profile_baseline "$qb_profile_base" "$qb_root/build/profile_baseline"
compile_hpx hpx_profile_baseline "$qb_profile_base" "$qb_root/build/profile_baseline" \
    "$qb_profile_base/benchmarks/matched_3d.cpp"
build_hpx profile_candidate "$qb_profile_candidate" "$qb_root/build/profile_candidate"
compile_hpx hpx_profile_candidate "$qb_profile_candidate" "$qb_root/build/profile_candidate" \
    "$qb_profile_candidate/benchmarks/matched_3d.cpp"
run_log compile_mpi "$qb_mpi/bin/mpicxx" -O3 -march=native -std=c++20 \
    -I"$qb_base_source/api" -I"$qb_base_source/mpi" \
    "$qb_base_source/benchmarks/matched_3d.cpp" \
    "$qb_base_build/mpi/.libs/libfftw3_mpi.a" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
    -lm -pthread -o "$qb_results/bin/mpi"
sha256sum "$qb_results/bin/mpi" > "$qb_results/mpi.binary.sha256"

qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:threads=64 --hpx:bind=none
    --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000
    --hpx:ini=hpx.parcel.tcp.enable=0 --hpx:ini=hpx.parcel.bootstrap=mpi)
# No duplicate primary HPX timings: these four runs include instrumentation.
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_results/bin/mpi" "${qb_options[@]}"
run_hpx hpx_profile_baseline
run_hpx profile_baseline_bg1 hpx_profile_baseline --hpx:ini=hpx.parcel.mpi.background_threads=1
run_hpx hpx_profile_candidate
run_hpx profile_candidate_bg1 hpx_profile_candidate --hpx:ini=hpx.parcel.mpi.background_threads=1
qb_stage=validate_profiles
python3 -I - "$qb_results" <<'PROFILE_PY' | tee "$qb_results/profile_validation.json"
import json
import math
from pathlib import Path
import sys

root = Path(sys.argv[1])
metrics = {
    "copy_bytes_inclusive", "message_bytes_inclusive", "receive_bytes_inclusive",
    "run_jobs_inclusive", "send_inclusive", "recv_inclusive", "sendrecv_inclusive",
}
expected = {(rank, sample, metric) for rank in range(4) for sample in range(7)
            for metric in metrics}
summary = {"timing_includes_instrumentation": True,
           "metrics_are_inclusive_do_not_sum": True, "runs": {}}
for label in ("hpx_profile_baseline", "profile_baseline_bg1",
              "hpx_profile_candidate", "profile_candidate_bg1"):
    rows = []
    for line in (root / ("benchmark_" + label + ".log")).read_text().splitlines():
        if line.startswith("PROFILE "):
            row = dict(token.split("=", 1) for token in line.split()[1:])
            value = float(row["seconds"])
            assert math.isfinite(value) and value >= 0
            assert int(row["calls"]) >= 0
            rows.append((int(row["rank"]), int(row["sample"]), row["metric"]))
    assert len(rows) == len(expected) and set(rows) == expected, label
    with (root / ("comparison_" + label + ".log")).open() as stream:
        comparison = json.load(stream)
    summary["runs"][label] = {"profile_rows": len(rows),
                             "median_seconds": comparison["hpx"]["result"]["median_seconds"],
                             "normalized_plans_equal": comparison["normalized_plans_equal"]}
print(json.dumps(summary, indent=2))
PROFILE_PY
run_log baseline_unchanged sha256sum -c "$qb_results/baseline_inputs.sha256"
qb_stage=complete
printf 'MATCHED_PROFILE_PASS baseline=%s results=%s\n' "$qb_base_commit" "$qb_results"
