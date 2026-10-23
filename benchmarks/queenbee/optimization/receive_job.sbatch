#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_receive
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:40:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_optimize_20261022/receive-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_optimize_20261022/receive-%j.err
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

# Follow-up to the successfully completed bg1_global1 case in job 1125437.
# Compile only the isolated receive bridge prototypes, replacing hpx-comm.o
# in copied candidate archives. All original sources/libraries stay untouched.
# Preserve normal multithreaded MPI; the serialized-MPI case failed at shutdown.
# Communication checks precede six unchanged-driver 1024^3 timing runs.
# A separate candidate backoff control isolates the additional scheduler flag
# used for both receive prototypes from the unchanged tuning selection.

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
qb_tuning_job=${QB_TUNING_JOB_ID:-1125437}
qb_tuning=${QB_TUNING_RESULTS:-$qb_root/results/$qb_tuning_job}
qb_build=${QB_CANDIDATE_BUILD:-$qb_root/build/candidate}
qb_prototypes=${QB_PROTOTYPES:-$qb_root/prototypes}
qb_candidate_archive=$qb_build/hpx/.libs/libfftw3_hpx.a
qb_mpi_exe=$qb_primary/bin/mpi
qb_baseline_exe=$qb_primary/bin/hpx_baseline
qb_candidate_exe=$qb_primary/bin/hpx_candidate
qb_provenance=$qb_primary/CANDIDATE_PROVENANCE
qb_summary=${QB_SUMMARIZER:-$qb_source/benchmarks/summarize.py}
qb_results=$qb_root/results/$SLURM_JOB_ID
mkdir -p "$qb_results/bin" "$qb_results/prototypes"
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
        printf 'baseline_commit\t%s\nmain_job_id\t%s\ntuning_job_id\t%s\nfinished_utc\t%s\n' \
            "$qb_base_commit" "$qb_main_job" "$qb_tuning_job" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_root/RECEIVE_FINAL_STATUS.tmp"
    mv "$qb_root/RECEIVE_FINAL_STATUS.tmp" "$qb_root/RECEIVE_FINAL_STATUS"
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

build_prototype()
{
    local name=$1
    local source=$qb_prototypes/$name/hpx-comm.cpp
    local build=$qb_results/prototypes/$name
    local archive=$build/libfftw3_hpx.a
    mkdir -p "$build"
    cp "$source" "$build/source-hpx-comm.cpp"
    for provenance in "$qb_prototypes/$name/provenance.json" "$qb_prototypes/$name/PROVENANCE.json"; do
        if [ -f "$provenance" ]; then
            cp "$provenance" "$build/$(basename "$provenance")"
        fi
    done
    run_log "compile_bridge_$name" g++ -O3 -march=native -DHAVE_CONFIG_H \
        "${qb_hpx_cflags[@]}" -I"$qb_build" -I"$qb_source" -I"$qb_source/api" -I"$qb_source/hpx" \
        -c "$source" -o "$build/hpx-comm.o"
    cp "$qb_candidate_archive" "$archive"
    run_log "replace_bridge_$name" ar r "$archive" "$build/hpx-comm.o"
    python3 -I - "$qb_candidate_archive" "$archive" <<'ARCHIVE_PY' | tee "$build/archive_members.json"
import hashlib
import json
import subprocess
import sys

def read_members(path):
    names = subprocess.check_output(["ar", "t", path], universal_newlines=True).splitlines()
    assert len(names) == len(set(names)) == 32
    values = {name: hashlib.sha256(subprocess.check_output(["ar", "p", path, name])).hexdigest()
              for name in names}
    return names, values

before_names, before = read_members(sys.argv[1])
after_names, after = read_members(sys.argv[2])
assert before_names == after_names
changed = [name for name in before_names if before[name] != after[name]]
assert changed == ["hpx-comm.o"], changed
print(json.dumps({"changed_members": changed, "unchanged_members": 31,
                  "before": before, "after": after}, indent=2))
ARCHIVE_PY
    run_log "compile_matched_$name" g++ -O3 -march=native -std=c++20 -DFFTW_BENCH_HPX \
        "${qb_app_cflags[@]}" -I"$qb_base_source/api" -I"$qb_source/hpx" \
        "$qb_base_source/benchmarks/matched_3d.cpp" "$archive" \
        "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
        "${qb_app_libs[@]}" -lm -pthread -o "$qb_results/bin/$name"
    run_log "compile_comm_check_$name" g++ -O3 -march=native -std=c++20 \
        "${qb_app_cflags[@]}" -I"$qb_build" -I"$qb_source/api" -I"$qb_source/hpx" \
        -UNDEBUG -include "$qb_results/assert_enabled.h" "$qb_source/hpx/hpx-comm-check.cpp" "$archive" \
        "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
        "${qb_app_libs[@]}" -lm -pthread -UNDEBUG -o "$qb_results/bin/${name}_comm_check"
    sha256sum "$source" "$archive" "$qb_results/bin/$name" "$qb_results/bin/${name}_comm_check" \
        > "$build/artifacts.sha256"
}

check_prototype()
{
    local name=$1
    run_log "comm_check_$name" timeout --kill-after=15s 180s "${qb_launcher[@]}" \
        /usr/bin/numactl --interleave=all "$qb_results/bin/${name}_comm_check" \
        "${qb_hpx_options[@]}" --hpx:threads=2 "${qb_selected_flags[@]}" \
        --hpx:ini=hpx.max_idle_backoff_time=1
    [ "$(grep -c '^communication check PASS$' "$qb_results/comm_check_$name.log")" -eq 4 ]
}

run_hpx()
{
    local label=$1 executable=$2
    shift 2
    run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
        "$executable" "${qb_hpx_options[@]}" --hpx:threads=64 "$@" "${qb_options[@]}"
    run_log "comparison_$label" python3 -I "$qb_summary" \
        "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log"
}

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
test -f "$qb_provenance"
test -f "$qb_summary"
test -x "$qb_mpi_exe"
test -x "$qb_baseline_exe"
test -x "$qb_candidate_exe"
grep -q $'^status\tPASS$' "$qb_primary/FINAL_STATUS"
grep -q '^PASS comparison_candidate_bg1_global1 ' "$qb_tuning/job.log"
test -f "$qb_tuning/comparison_candidate_bg1_global1.log"
test -f "$qb_build/config.h"
test -f "$qb_prototypes/direct_receive/hpx-comm.cpp"
test -f "$qb_prototypes/pooled_receive/hpx-comm.cpp"
read -r qb_base_commit < "$qb_base_root/SOURCE_COMMIT"
[[ "$qb_base_commit" =~ ^[0-9a-f]{40}$ ]]
cp "$qb_base_root/SOURCE_COMMIT" "$qb_results/BASELINE_COMMIT"
cp "$qb_provenance" "$qb_results/CANDIDATE_PROVENANCE"
cp "$0" "$qb_results/job.sbatch"
cp "$qb_primary/hpx_baseline.binary.sha256" "$qb_results/primary_baseline.binary.sha256"
cp "$qb_primary/mpi.binary.sha256" "$qb_results/primary_mpi.binary.sha256"
cp "$qb_primary/hpx_candidate.binary.sha256" "$qb_results/primary_candidate.binary.sha256"
cp "$qb_primary/candidate.sha256" "$qb_results/primary_candidate_archive.sha256"
cp "$qb_primary/hpx_metadata/hpx-flags.sh" "$qb_results/primary_hpx-flags.sh"
run_log verify_primary_baseline sha256sum -c "$qb_results/primary_baseline.binary.sha256"
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
    printf 'tuning_job=%s\nprototypes=%s\n' "$qb_tuning_job" "$qb_prototypes"
    printf 'compilation=only prototype bridge objects and benchmark/check executables; original libraries preserved\n'
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
sha256sum "$qb_mpi_exe" "$qb_baseline_exe" "$qb_candidate_exe" > "$qb_results/binaries.sha256"
sha256sum "$qb_prototypes/direct_receive/hpx-comm.cpp" \
    "$qb_prototypes/pooled_receive/hpx-comm.cpp" "$qb_source/hpx/hpx-comm-check.cpp" \
    "$qb_build/config.h" "$qb_candidate_archive" > "$qb_results/prototype_inputs.sha256"
sha256sum "$qb_base_source/benchmarks/matched_3d.cpp" \
    "$qb_base_build/mpi/.libs/libfftw3_mpi.a" \
    "$qb_base_build/hpx/.libs/libfftw3_hpx.a" \
    "$qb_base_build/threads/libfftw3_threads.la" \
    "$qb_base_build/threads/.libs/libfftw3_threads.a" \
    "$qb_base_build/libfftw3.la" "$qb_base_build/.libs/libfftw3.a" \
    > "$qb_results/baseline_inputs.sha256"
(cd "$qb_source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) \
    > "$qb_results/candidate_source.sha256"
. "$qb_results/primary_hpx-flags.sh"
read -r -a qb_hpx_cflags <<< "$HPX_CFLAGS"
read -r -a qb_app_cflags <<< "$HPX_APP_CFLAGS"
read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
cat > "$qb_results/assert_enabled.h" <<'HEADER'
#ifdef NDEBUG
#error The communication check requires assertions enabled
#endif
HEADER

# This exact configuration completed successfully before a separate serialized-
# MPI experiment failed during finalization. Do not use the failed option.
cp "$qb_tuning/comparison_candidate_bg1_global1.log" "$qb_results/tuning_comparison_input.json"
cp "$qb_tuning/benchmark_candidate_bg1_global1.command" "$qb_results/tuning_completed_case.command"
cp "$qb_tuning/FINAL_STATUS" "$qb_results/tuning_job_status.txt"
qb_stage=select_runtime
python3 -I - "$qb_results/tuning_comparison_input.json" "$qb_results" "$qb_tuning_job" <<'SELECT_PY'
import json
import math
from pathlib import Path
import sys

out = Path(sys.argv[2])
report = json.loads(Path(sys.argv[1]).read_text())
assert all(report["normalized_plans_equal"].values())
for backend in ("hpx", "mpi"):
    result = report[backend]["result"]
    assert result["status"] == "PASS"
    assert all(int(result[key]) == expected for key, expected in
               (("extent", 1024), ("ranks", 4), ("threads", 64), ("samples", 7)))
    assert math.isfinite(float(result["median_seconds"])) and float(result["median_seconds"]) > 0
flags = ["--hpx:ini=hpx.parcel.mpi.background_threads=1",
         "--hpx:ini=hpx.max_background_threads=1",
         "--hpx:ini=hpx.parcel.mpi.multithreaded=1"]
selection = {"tuning_job_id": sys.argv[3], "selected_case": "candidate_bg1_global1",
             "selection_rule": "completed successful case; later serialized-MPI case excluded after shutdown failure",
             "tuning_median_seconds": float(report["hpx"]["result"]["median_seconds"]),
             "mpi_control_median_seconds": float(report["mpi"]["result"]["median_seconds"]),
             "argv": flags,
             "scope": "chosen from a completed run in a subsequently failed allocation; remeasured here"}
(out / "runtime_selection.json").write_text(json.dumps(selection, indent=2) + "\n")
(out / "runtime_selection.argv").write_text("\n".join(flags) + "\n")
print(json.dumps(selection, indent=2))
SELECT_PY
mapfile -t qb_selected_flags < "$qb_results/runtime_selection.argv"
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:bind=none
    --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000
    --hpx:ini=hpx.parcel.tcp.enable!=0 --hpx:ini=hpx.parcel.bootstrap=mpi)
build_prototype pooled_receive
build_prototype direct_receive
# Re-run the simple candidate ownership check with TCP explicitly defined off.
# The earlier standalone job stopped at option parsing, before any tests.
run_log compile_comm_check_candidate g++ -O3 -march=native -std=c++20 \
    "${qb_app_cflags[@]}" -I"$qb_build" -I"$qb_source/api" -I"$qb_source/hpx" \
    -UNDEBUG -include "$qb_results/assert_enabled.h" "$qb_source/hpx/hpx-comm-check.cpp" \
    "$qb_candidate_archive" "$qb_base_build/threads/.libs/libfftw3_threads.a" \
    "$qb_base_build/.libs/libfftw3.a" "${qb_app_libs[@]}" -lm -pthread -UNDEBUG \
    -o "$qb_results/bin/candidate_comm_check"
sha256sum "$qb_results/bin/candidate_comm_check" > "$qb_results/candidate_comm_check.sha256"
check_prototype candidate
check_prototype pooled_receive
check_prototype direct_receive

# Old HPX stays at default progress settings. The candidate is measured first
# with the tuning selection unchanged, then with the one additional backoff
# setting. Both receive prototypes use that same latter configuration.
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_mpi_exe" "${qb_options[@]}"
run_hpx hpx_baseline "$qb_baseline_exe"
run_hpx candidate_selected "$qb_candidate_exe" "${qb_selected_flags[@]}"
run_hpx candidate_selected_backoff1 "$qb_candidate_exe" "${qb_selected_flags[@]}" \
    --hpx:ini=hpx.max_idle_backoff_time=1
run_hpx pooled_selected "$qb_results/bin/pooled_receive" "${qb_selected_flags[@]}" \
    --hpx:ini=hpx.max_idle_backoff_time=1
run_hpx direct_selected "$qb_results/bin/direct_receive" "${qb_selected_flags[@]}" \
    --hpx:ini=hpx.max_idle_backoff_time=1
qb_stage=validate_receive
python3 -I - "$qb_results" <<'RECEIVE_PY' | tee "$qb_results/receive_comparison.json"
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
with (root / "runtime_selection.json").open() as stream:
    selection = json.load(stream)
labels = ("hpx_baseline", "candidate_selected", "candidate_selected_backoff1",
          "pooled_selected", "direct_selected")
runs = {}
for label in labels:
    with (root / ("comparison_" + label + ".log")).open() as stream:
        comparison = json.load(stream)
    assert all(comparison["normalized_plans_equal"].values())
    runs[label] = {
        "median_seconds": float(comparison["hpx"]["result"]["median_seconds"]),
        "hpx_over_mpi_median_ratio": comparison["hpx_over_mpi_median_ratio"],
        "normalized_plans_equal_to_mpi": comparison["normalized_plans_equal"],
        "hpx_plans": comparison["hpx"]["plans"],
    }
control = runs["candidate_selected_backoff1"]["median_seconds"]
control_plans = runs["candidate_selected_backoff1"]["hpx_plans"]
for run in runs.values():
    run["median_over_candidate_selected_backoff1_control"] = run["median_seconds"] / control
    run["plans_equal_to_candidate_selected_backoff1_control"] = run.pop("hpx_plans") == control_plans
    assert run["plans_equal_to_candidate_selected_backoff1_control"]
print(json.dumps({
    "instrumented": False,
    "runtime_selection": selection,
    "prototype_additional_argv": ["--hpx:ini=hpx.max_idle_backoff_time=1"],
    "prototype_comparison_control": "candidate_selected_backoff1",
    "candidate_backoff1_over_selected_median_ratio": control / runs["candidate_selected"]["median_seconds"],
    "runs": runs,
}, indent=2))
RECEIVE_PY
run_log prototypes_unchanged sha256sum -c "$qb_results/prototype_inputs.sha256"
(cd "$qb_source" && sha256sum -c "$qb_results/candidate_source.sha256") > "$qb_results/candidate_source_unchanged.log"
run_log binaries_unchanged sha256sum -c "$qb_results/binaries.sha256"
run_log candidate_unchanged sha256sum -c "$qb_results/primary_candidate_archive.sha256"
run_log baseline_unchanged sha256sum -c "$qb_results/baseline_inputs.sha256"
qb_stage=complete
printf 'MATCHED_RECEIVE_PASS baseline=%s results=%s\n' "$qb_base_commit" "$qb_results"
