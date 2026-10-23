#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_tuning
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_optimize_20261022/tuning-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_optimize_20261022/tuning-%j.err
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

# Prepared for review only; submission is a separate parent-owned action.
# Reuse job 1125395's exact uninstrumented MPI/candidate HPX executables.
# Relative to candidate + MPI progress worker 1, vary global background work
# and serialized MPI independently, then combine the two settings.
# All five runs retain 1024^3 / 64 workers / 2 warmups / 7 samples.

set -Eeuo pipefail
: "${SLURM_JOB_ID:?This script must run in its four-node Slurm allocation}"
qb_base_root=${QB_BASE_ROOT:-/work/dmarce1/fftw3_hpx_benchmark_20261022}
qb_root=${QB_ROOT:-/work/dmarce1/fftw3_hpx_optimize_20261022}
qb_hpx=${QB_HPX_PREFIX:-/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install}
qb_mpi=${QB_MPI_PREFIX:-/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install}
qb_base_source=${QB_BASE_SOURCE:-$qb_base_root/source}
qb_base_build=${QB_BASE_BUILD:-$qb_base_root/build}
qb_source=${QB_CANDIDATE_SOURCE:-$qb_root/source}
qb_main_job=${QB_MAIN_JOB_ID:-1125395}
qb_primary=${QB_PRIMARY_RESULTS:-$qb_root/results/$qb_main_job}
qb_mpi_exe=$qb_primary/bin/mpi
qb_candidate_exe=$qb_primary/bin/hpx_candidate
qb_provenance=$qb_primary/CANDIDATE_PROVENANCE
qb_summary=${QB_SUMMARIZER:-$qb_source/benchmarks/summarize.py}
qb_results=$qb_root/results/$SLURM_JOB_ID
mkdir -p "$qb_results"
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
        printf 'baseline_commit\t%s\nmain_job_id\t%s\nfinished_utc\t%s\n' \
            "$qb_base_commit" "$qb_main_job" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_root/TUNING_FINAL_STATUS.tmp"
    mv "$qb_root/TUNING_FINAL_STATUS.tmp" "$qb_root/TUNING_FINAL_STATUS"
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

run_hpx()
{
    local label=$1
    shift
    run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
        "$qb_candidate_exe" "${qb_hpx_options[@]}" "$@" "${qb_options[@]}"
    run_log "comparison_$label" python3 -I "$qb_summary" \
        "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log"
}

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
test -f "$qb_provenance"
test -f "$qb_summary"
test -x "$qb_mpi_exe"
test -x "$qb_candidate_exe"
grep -q $'^status\tPASS$' "$qb_primary/FINAL_STATUS"
read -r qb_base_commit < "$qb_base_root/SOURCE_COMMIT"
[[ "$qb_base_commit" =~ ^[0-9a-f]{40}$ ]]
cp "$qb_base_root/SOURCE_COMMIT" "$qb_results/BASELINE_COMMIT"
cp "$qb_provenance" "$qb_results/CANDIDATE_PROVENANCE"
cp "$0" "$qb_results/job.sbatch"
cp "$qb_primary/mpi.binary.sha256" "$qb_results/primary_mpi.binary.sha256"
cp "$qb_primary/hpx_candidate.binary.sha256" "$qb_results/primary_candidate.binary.sha256"
cp "$qb_primary/candidate.sha256" "$qb_results/primary_candidate_archive.sha256"
cp "$qb_primary/hpx_metadata/hpx-flags.sh" "$qb_results/primary_hpx-flags.sh"
run_log verify_primary_mpi sha256sum -c "$qb_results/primary_mpi.binary.sha256"
run_log verify_primary_candidate sha256sum -c "$qb_results/primary_candidate.binary.sha256"
run_log verify_primary_candidate_archive sha256sum -c "$qb_results/primary_candidate_archive.sha256"
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
# MPI parcelport plus InfiniBand/shared-memory UCX transports; never TCP.
unset HPXRUN_NODES HPXRUN_ARGS
cd "$qb_root"
{
    date -u
    hostname
    printf 'baseline_commit=%s\nbaseline_source=%s\nbaseline_build=%s\n' \
        "$qb_base_commit" "$qb_base_source" "$qb_base_build"
    printf 'candidate_source=%s\nmain_job_id=%s\nprimary_results=%s\nmpi_executable=%s\ncandidate_executable=%s\n' \
        "$qb_source" "$qb_main_job" "$qb_primary" "$qb_mpi_exe" "$qb_candidate_exe"
    printf 'compilation=none; executables reused byte-for-byte from primary job\n'
    printf 'placement=one rank per node, 64 workers, no CPU binding, NUMA interleave all\n'
    module -t list 2>&1
    "$qb_mpi/bin/mpiexec" --version
    "$qb_mpi/bin/mpicxx" --showme
    for name in PATH LD_LIBRARY_PATH \
        APEX_DISABLE HWLOC_COMPONENTS OMPI_MCA_accelerator OMPI_MCA_pml \
        OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST SLURM_CPUS_PER_TASK; do
        printf '%s=%s\n' "$name" "${!name-}"
    done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 \
    --ntasks-per-node=1 --cpus-per-task=1 --label \
    sh -c 'hostname; uname -a; lscpu; numactl --show'
sha256sum "$qb_results/job.sbatch" "$qb_summary" "$qb_provenance" \
    "$qb_results/primary_hpx-flags.sh" > "$qb_results/input.sha256"
sha256sum "$qb_mpi_exe" "$qb_candidate_exe" > "$qb_results/binaries.sha256"
sha256sum "$qb_base_source/benchmarks/matched_3d.cpp" \
    "$qb_base_build/mpi/.libs/libfftw3_mpi.a" \
    "$qb_base_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_base_build/threads/libfftw3_threads.la" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" \
    "$qb_base_build/libfftw3.la" "$qb_base_build/.libs/libfftw3.a" \
    > "$qb_results/baseline_inputs.sha256"
(cd "$qb_source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/candidate_source.sha256"
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:threads=64 --hpx:bind=none
    --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000
    --hpx:ini=hpx.parcel.tcp.enable=0 --hpx:ini=hpx.parcel.bootstrap=mpi
    --hpx:ini=hpx.parcel.mpi.background_threads=1)
# Four configurations form a 2x2 comparison on the same candidate binary.
# The first is an unchanged candidate-bg1 control within this allocation.
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_mpi_exe" "${qb_options[@]}"
run_hpx candidate_bg1
run_hpx candidate_bg1_global1 --hpx:ini=hpx.max_background_threads=1
run_hpx candidate_bg1_serialized --hpx:ini=hpx.parcel.mpi.multithreaded=0
run_hpx candidate_bg1_global1_serialized --hpx:ini=hpx.max_background_threads=1 \
    --hpx:ini=hpx.parcel.mpi.multithreaded=0
qb_stage=validate_tuning
python3 -I - "$qb_results" "$qb_main_job" <<'TUNING_PY' | tee "$qb_results/tuning_comparison.json"
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
labels = ("candidate_bg1", "candidate_bg1_global1", "candidate_bg1_serialized",
          "candidate_bg1_global1_serialized")
runs = {}
for label in labels:
    with (root / ("comparison_" + label + ".log")).open() as stream:
        comparison = json.load(stream)
    runs[label] = {
        "median_seconds": float(comparison["hpx"]["result"]["median_seconds"]),
        "hpx_over_mpi_median_ratio": comparison["hpx_over_mpi_median_ratio"],
        "normalized_plans_equal_to_mpi": comparison["normalized_plans_equal"],
        "hpx_plans": comparison["hpx"]["plans"],
    }
control = runs[labels[0]]["median_seconds"]
control_plans = runs[labels[0]]["hpx_plans"]
for run in runs.values():
    run["median_over_candidate_bg1_control"] = run["median_seconds"] / control
    run["plans_equal_to_candidate_bg1_control"] = run.pop("hpx_plans") == control_plans
    assert run["plans_equal_to_candidate_bg1_control"]
print(json.dumps({"instrumented": False, "mpi_background_threads": 1,
                  "reused_primary_job": sys.argv[2], "runs": runs}, indent=2))
TUNING_PY
run_log binaries_unchanged sha256sum -c "$qb_results/binaries.sha256"
run_log candidate_unchanged sha256sum -c "$qb_results/primary_candidate_archive.sha256"
run_log baseline_unchanged sha256sum -c "$qb_results/baseline_inputs.sha256"
qb_stage=complete
printf 'MATCHED_TUNING_PASS baseline=%s results=%s\n' "$qb_base_commit" "$qb_results"
