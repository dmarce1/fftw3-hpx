#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_comm_check
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=2
#SBATCH --ntasks=2
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=2
#SBATCH --time=00:10:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_optimize_20261022/comm-check-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_optimize_20261022/comm-check-%j.err
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

# Submit with --dependency=afterok:1125395. The parent owns submission.
# Build only the assertion-enabled check in this allocated compute job.
set -Eeuo pipefail
: "${SLURM_JOB_ID:?This script requires its two-node Slurm allocation}"
qb_root=${QB_ROOT:-/work/dmarce1/fftw3_hpx_optimize_20261022}
qb_base_root=${QB_BASE_ROOT:-/work/dmarce1/fftw3_hpx_benchmark_20261022}
qb_source=${QB_CANDIDATE_SOURCE:-$qb_root/source}
qb_build=${QB_CANDIDATE_BUILD:-$qb_root/build/candidate}
qb_base_build=${QB_BASE_BUILD:-$qb_base_root/build}
qb_main_job=${QB_MAIN_JOB_ID:-1125395}
qb_flags=${QB_HPX_FLAGS:-$qb_root/results/$qb_main_job/hpx_metadata/hpx-flags.sh}
qb_hpx=${QB_HPX_PREFIX:-/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install}
qb_mpi=${QB_MPI_PREFIX:-/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install}
qb_results=$qb_root/comm_check_results/$SLURM_JOB_ID
mkdir -p "$qb_results"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
exec 3> "$qb_results/commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
qb_stage=setup

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
        printf 'main_job_id\t%s\nfinished_utc\t%s\n' "$qb_main_job" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
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

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 2 ]
[ "${SLURM_NTASKS:-0}" -eq 2 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 2 ]
test -f "$qb_build/config.h"
test -f "$qb_flags"
cp "$0" "$qb_results/comm_check.sbatch"
cp "$qb_flags" "$qb_results/hpx-flags.sh"
cp "$qb_root/CANDIDATE_PROVENANCE" "$qb_results/CANDIDATE_PROVENANCE"
module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$qb_hpx/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hpx/lib64:$qb_hpx/lib:${LD_LIBRARY_PATH:-}"
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
export OMPI_MCA_accelerator=null
export OMPI_MCA_pml=ucx
export OMPI_MCA_btl=self,sm
export UCX_TLS=rc,sm,self
unset HPXRUN_NODES HPXRUN_ARGS
. "$qb_flags"
read -r -a qb_hpx_cflags <<< "$HPX_APP_CFLAGS"
read -r -a qb_hpx_libs <<< "$HPX_APP_LIBS"
cd "$qb_results"
{
    date -u
    hostname
    printf 'main_job_id=%s\nsource=%s\nbuild=%s\nhpx=%s\nmpi=%s\n' \
        "$qb_main_job" "$qb_source" "$qb_build" "$qb_hpx" "$qb_mpi"
    module -t list 2>&1
    g++ --version
    "$qb_mpi/bin/mpiexec" --version
    for name in APEX_DISABLE HWLOC_COMPONENTS OMPI_MCA_accelerator \
        OMPI_MCA_pml OMPI_MCA_btl UCX_TLS SLURM_JOB_NODELIST SLURM_CPUS_PER_TASK; do
        printf '%s=%s\n' "$name" "${!name-}"
    done
} > metadata.txt
scontrol show hostnames "$SLURM_JOB_NODELIST" > nodes.txt
sha256sum "$qb_source/hpx/hpx-comm-check.cpp" "$qb_source/hpx/hpx-comm.cpp" \
    "$qb_build/config.h" "$qb_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
    "$qb_flags" "$qb_results/comm_check.sbatch" > input.sha256

# -UNDEBUG appears after all inherited compiler flags, so HPX's release
# flags cannot compile away assertions or assert-wrapped collective calls.
cat > assert_enabled.h <<'HEADER'
#ifdef NDEBUG
#error The communication check requires assertions enabled
#endif
HEADER
run_log compile_check g++ -O3 -march=native -std=c++20 \
    -I"$qb_build" -I"$qb_source/api" -I"$qb_source/hpx" \
    "${qb_hpx_cflags[@]}" -UNDEBUG -include "$qb_results/assert_enabled.h" \
    "$qb_source/hpx/hpx-comm-check.cpp" \
    "$qb_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
    "${qb_hpx_libs[@]}" -lm -pthread -o "$qb_results/hpx-comm-check"
sha256sum hpx-comm-check > binary.sha256
# The initial dump preserves selected zero-copy and MPI progress settings.
# HPX 1.11 supports this option; no additional runtime or Slurm query is used.
run_log communication_check "$qb_mpi/bin/mpiexec" -n 2 \
    --map-by ppr:1:node --bind-to none /usr/bin/numactl --interleave=all \
    "$qb_results/hpx-comm-check" --hpx:ignore-batch-env --hpx:localities=2 \
    --hpx:threads=2 --hpx:bind=none --hpx:dump-config-initial \
    --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000 \
    --hpx:ini=hpx.parcel.mpi.background_threads=1 \
    --hpx:ini=hpx.parcel.tcp.enable=0 --hpx:ini=hpx.parcel.bootstrap=mpi
qb_stage=validate_output
[ "$(grep -c '^communication check PASS$' communication_check.log)" -eq 2 ]
[ "$(grep -c '^communication check, cycle [01]: message ownership and overlapping buffers$' communication_check.log)" -eq 2 ]
run_log inputs_unchanged sha256sum -c input.sha256
qb_stage=complete
printf 'COMMUNICATION_CHECK_PASS localities=2 workers_per_locality=2 background_threads=1\n'
