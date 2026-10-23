#!/bin/bash -l
#SBATCH --job-name=fftw_hpx_final
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:25:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_optimize_20261022/final-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_optimize_20261022/final-%j.err
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

# Prepared for review; submission is a separate parent-owned action.
# No builds: reuse the exact candidate and prototype executables exercised by
# successful receive job 1125605, and the original MPI executable from 1125395.
# All HPX cases use the same bg1/global1/multithreaded runtime with the original
# 1000 ms maximum idle backoff. TCP is explicitly disabled on every locality.

set -Eeuo pipefail
: "${SLURM_JOB_ID:?This script must run in its four-node Slurm allocation}"
qb_base_root=/work/dmarce1/fftw3_hpx_benchmark_20261022
qb_root=/work/dmarce1/fftw3_hpx_optimize_20261022
qb_hpx=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_base_source=$qb_base_root/source
qb_base_build=$qb_base_root/build
qb_source=$qb_root/source
qb_primary=$qb_root/results/1125395
qb_receive=$qb_root/results/1125605
qb_mpi_exe=$qb_primary/bin/mpi
qb_candidate_exe=$qb_primary/bin/hpx_candidate
qb_pool_exe=$qb_receive/bin/pooled_receive
qb_direct_exe=$qb_receive/bin/direct_receive
qb_summary=$qb_source/benchmarks/summarize.py
qb_results=$qb_root/results/$SLURM_JOB_ID
qb_stage=setup
qb_started=$(date -u +%FT%TZ)
qb_base_commit=unknown
mkdir -p "$qb_results/reused_artifacts"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
exec 3> "$qb_results/commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '

finish()
{
    local result=$1
    trap - EXIT
    set +e
    set +x
    local outcome=FAIL
    if [ "$result" -eq 0 ] && [ "$qb_stage" = complete ]; then
        outcome=PASS
    elif [ "$result" -eq 0 ]; then
        result=1
    fi
    {
        printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\n' \
            "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage"
        printf 'baseline_commit\t%s\nprimary_job_id\t1125395\nreceive_job_id\t1125605\n' "$qb_base_commit"
        printf 'started_utc\t%s\nfinished_utc\t%s\n' "$qb_started" "$(date -u +%FT%TZ)"
    } > "$qb_results/FINAL_STATUS.tmp"
    mv "$qb_results/FINAL_STATUS.tmp" "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_root/FINAL_RUNTIME_STATUS.tmp"
    mv "$qb_root/FINAL_RUNTIME_STATUS.tmp" "$qb_root/FINAL_RUNTIME_STATUS"
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
    local started=$SECONDS
    printf 'START %s %s\n' "$label" "$(date -u +%FT%TZ)"
    {
        printf 'cd %q\n' "$PWD"
        printf '%q ' "$@"
        printf '\n'
    } > "$qb_results/$label.command"
    if "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"; then
        printf '%s\tPASS\t%s\n' "$label" "$((SECONDS-started))" >> "$qb_results/results.tsv"
        printf 'PASS %s %s\n' "$label" "$(date -u +%FT%TZ)"
    else
        local result=$?
        printf '%s\tFAIL\t%s\t%s\n' "$label" "$((SECONDS-started))" "$result" >> "$qb_results/results.tsv"
        printf 'FAIL %s exit=%s %s\n' "$label" "$result" "$(date -u +%FT%TZ)"
        return "$result"
    fi
}

verify_candidate_source()
{
    (cd "$qb_source" && sha256sum -c "$qb_results/reused_artifacts/candidate_source.sha256")
}

run_hpx()
{
    local label=$1 executable=$2
    run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
        "$executable" "${qb_hpx_options[@]}" "${qb_options[@]}" || return "$?"
    run_log "comparison_$label" python3 -I "$qb_summary" \
        "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log" || return "$?"
}

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
grep -q $'^status\tPASS$' "$qb_receive/FINAL_STATUS"
grep -q $'^status\tPASS$' "$qb_primary/FINAL_STATUS"
for executable in "$qb_mpi_exe" "$qb_candidate_exe" "$qb_pool_exe" "$qb_direct_exe"; do
    test -x "$executable"
done
test -f "$qb_summary"
read -r qb_base_commit < "$qb_base_root/SOURCE_COMMIT"
[ "$qb_base_commit" = cb205948f773e8e057b14ebbf6fa4df1c7cb994a ]
cp "$0" "$qb_results/job.sbatch"
cp "$qb_receive/FINAL_STATUS" "$qb_results/reused_artifacts/receive_FINAL_STATUS"
cp "$qb_primary/FINAL_STATUS" "$qb_results/reused_artifacts/primary_FINAL_STATUS"
cp "$qb_base_root/SOURCE_COMMIT" "$qb_results/BASELINE_COMMIT"
cp "$qb_receive/CANDIDATE_PROVENANCE" "$qb_results/CANDIDATE_PROVENANCE"
cp "$qb_receive/job.sbatch" "$qb_results/reused_artifacts/receive_job.sbatch"
cp "$qb_receive/primary_hpx-flags.sh" "$qb_results/reused_artifacts/hpx-flags.sh"
for manifest in baseline_inputs.sha256 prototype_inputs.sha256 binaries.sha256 candidate_source.sha256; do
    cp "$qb_receive/$manifest" "$qb_results/reused_artifacts/$manifest"
done
cp "$qb_primary/mpi.binary.sha256" "$qb_results/reused_artifacts/primary_mpi.binary.sha256"
cp "$qb_primary/hpx_candidate.binary.sha256" "$qb_results/reused_artifacts/primary_candidate.binary.sha256"
cp "$qb_primary/candidate.sha256" "$qb_results/reused_artifacts/primary_candidate_archive.sha256"
for name in pooled_receive direct_receive; do
    mkdir -p "$qb_results/reused_artifacts/$name"
    cp "$qb_receive/prototypes/$name/artifacts.sha256" "$qb_results/reused_artifacts/$name/artifacts.sha256"
    cp "$qb_receive/prototypes/$name/archive_members.json" "$qb_results/reused_artifacts/$name/archive_members.json"
    cp "$qb_receive/prototypes/$name/source-hpx-comm.cpp" "$qb_results/reused_artifacts/$name/source-hpx-comm.cpp"
done
run_log verify_primary_mpi sha256sum -c "$qb_results/reused_artifacts/primary_mpi.binary.sha256"
run_log verify_primary_candidate sha256sum -c "$qb_results/reused_artifacts/primary_candidate.binary.sha256"
run_log verify_candidate_archive sha256sum -c "$qb_results/reused_artifacts/primary_candidate_archive.sha256"
run_log verify_receive_binaries sha256sum -c "$qb_results/reused_artifacts/binaries.sha256"
run_log verify_baseline_inputs sha256sum -c "$qb_results/reused_artifacts/baseline_inputs.sha256"
run_log verify_prototype_inputs sha256sum -c "$qb_results/reused_artifacts/prototype_inputs.sha256"
run_log verify_candidate_source verify_candidate_source
run_log verify_pool_artifacts sha256sum -c "$qb_results/reused_artifacts/pooled_receive/artifacts.sha256"
run_log verify_direct_artifacts sha256sum -c "$qb_results/reused_artifacts/direct_receive/artifacts.sha256"
run_log verify_fixed_paths python3 -I - "$qb_root" "$qb_results" <<'PROVENANCE_PY'
import hashlib
import json
from pathlib import Path
import sys

root, results = map(Path, sys.argv[1:])
saved = results / "reused_artifacts"
def manifest(path):
    return {filename: digest for digest, filename in
            (line.split("  ", 1) for line in path.read_text().splitlines())}
binary = manifest(saved / "binaries.sha256")
assert str(root / "results/1125395/bin/hpx_candidate") in binary
assert str(root / "results/1125395/bin/mpi") in binary
expected = {
    "direct_receive": "477f1243b68a303e370d97913279f9b312ed66c8a54811392083b9b6faec1590",
    "pooled_receive": "57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c",
}
for name, digest in expected.items():
    entries = manifest(saved / name / "artifacts.sha256")
    paths = {
        root / "prototypes" / name / "hpx-comm.cpp",
        root / "results/1125605/prototypes" / name / "libfftw3_hpx.a",
        root / "results/1125605/bin" / name,
        root / "results/1125605/bin" / (name + "_comm_check"),
    }
    assert set(entries) == {str(path) for path in paths}
    source = saved / name / "source-hpx-comm.cpp"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert entries[str(root / "prototypes" / name / "hpx-comm.cpp")] == digest
    members = json.loads((saved / name / "archive_members.json").read_text())
    assert members["changed_members"] == ["hpx-comm.o"]
    assert members["unchanged_members"] == 31
print("FIXED_ARTIFACT_PROVENANCE_PASS")
PROVENANCE_PY

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
cd "$qb_root"
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:threads=64 --hpx:bind=none
    --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000
    '--hpx:ini=hpx.parcel.tcp.enable!=0' --hpx:ini=hpx.parcel.bootstrap=mpi
    --hpx:ini=hpx.parcel.mpi.background_threads=1 --hpx:ini=hpx.max_background_threads=1
    --hpx:ini=hpx.parcel.mpi.multithreaded=1 --hpx:ini=hpx.max_idle_backoff_time=1000)
printf '%s\n' "${qb_hpx_options[@]}" > "$qb_results/runtime.argv"
printf '%s\n' "${qb_options[@]}" > "$qb_results/benchmark.argv"
{
    date -u
    hostname
    printf 'baseline_commit=%s\nprimary_job_id=1125395\nreceive_job_id=1125605\n' "$qb_base_commit"
    printf 'baseline_source=%s\nbaseline_build=%s\ncandidate_source=%s\n' "$qb_base_source" "$qb_base_build" "$qb_source"
    printf 'mpi_executable=%s\ncandidate_executable=%s\npool_executable=%s\ndirect_executable=%s\n' \
        "$qb_mpi_exe" "$qb_candidate_exe" "$qb_pool_exe" "$qb_direct_exe"
    printf 'compilation=none; fixed executables reused without instrumentation\n'
    printf 'placement=one rank per node,64 workers,no CPU binding,NUMA interleave all\n'
    printf 'runtime=bg1/global1/multithreaded1/max_idle_backoff_time1000;MPI parcelport;TCP disabled\n'
    module -t list 2>&1
    "$qb_mpi/bin/mpiexec" --version
    "$qb_mpi/bin/mpicxx" --showme
    for name in PATH LD_LIBRARY_PATH APEX_DISABLE HWLOC_COMPONENTS OMPI_MCA_accelerator \
        OMPI_MCA_pml OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST SLURM_CPUS_PER_TASK; do
        printf '%s=%s\n' "$name" "${!name-}"
    done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
scontrol show job "$SLURM_JOB_ID" > "$qb_results/slurm_job_start.txt"
{
    printf 'Final scheduler accounting must be collected once after this allocation completes.\n'
    printf 'No scheduler polling is performed by this job.\n'
    printf 'sacct -j %s --parsable2 --units=K --format=JobIDRaw,JobName,State,ExitCode,Elapsed,AllocCPUS,NodeList,MaxRSS\n' "$SLURM_JOB_ID"
} > "$qb_results/accounting_pending.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 \
    --ntasks-per-node=1 --cpus-per-task=1 --label \
    sh -c 'hostname; uname -a; lscpu; numactl --show'
sha256sum "$qb_mpi_exe" "$qb_candidate_exe" "$qb_pool_exe" "$qb_direct_exe" > "$qb_results/binaries.sha256"
sha256sum "$qb_results/job.sbatch" "$qb_summary" "$qb_results/CANDIDATE_PROVENANCE" \
    "$qb_results/runtime.argv" "$qb_results/benchmark.argv" > "$qb_results/input.sha256"

run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
    "$qb_mpi_exe" "${qb_options[@]}"
run_hpx candidate "$qb_candidate_exe"
run_hpx pooled_receive "$qb_pool_exe"
run_hpx direct_receive "$qb_direct_exe"
run_log final_comparison python3 -I - "$qb_results" <<'COMPARE_PY'
import json
import math
from pathlib import Path
import sys

root = Path(sys.argv[1])
labels = ("candidate", "pooled_receive", "direct_receive")
runs = {}
mpi_control = None
candidate_plans = None
for label in labels:
    report = json.loads((root / ("comparison_" + label + ".log")).read_text())
    assert all(report["normalized_plans_equal"].values())
    for backend in ("mpi", "hpx"):
        config = report[backend]["configuration"]
        result = report[backend]["result"]
        assert result["status"] == "PASS"
        for key, expected in (("extent", 1024), ("ranks", 4), ("threads", 64), ("warmups", 2), ("samples", 7)):
            assert int(config[key]) == expected, (label, backend, key)
        assert math.isfinite(float(result["median_seconds"])) and float(result["median_seconds"]) > 0
    if mpi_control is None:
        mpi_control = report["mpi"]
        candidate_plans = report["hpx"]["plans"]
    assert report["mpi"] == mpi_control
    assert report["hpx"]["plans"] == candidate_plans
    runs[label] = {
        "median_seconds": float(report["hpx"]["result"]["median_seconds"]),
        "samples_seconds": report["hpx"]["samples_seconds"],
        "checks": report["hpx"]["checks"],
        "hpx_over_mpi_median_ratio": report["hpx_over_mpi_median_ratio"],
        "normalized_plans_equal_to_mpi": report["normalized_plans_equal"],
        "plans_equal_to_candidate": True,
    }
control = runs["candidate"]["median_seconds"]
for run in runs.values():
    run["median_over_candidate_control"] = run["median_seconds"] / control
summary = {
    "status": "PASS", "instrumented": False, "rebuilt": False,
    "primary_job_id": "1125395", "receive_job_id": "1125605",
    "runtime_argv": (root / "runtime.argv").read_text().splitlines(),
    "benchmark_argv": (root / "benchmark.argv").read_text().splitlines(),
    "prototype_comparison_control": "candidate",
    "mpi": mpi_control, "runs": runs,
    "limitations": "One allocation and fixed run order; local correctness and prior backoff1 measurements are separate evidence.",
}
(root / "final_comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
COMPARE_PY
run_log inputs_unchanged sha256sum -c "$qb_results/input.sha256"
run_log binaries_unchanged sha256sum -c "$qb_results/binaries.sha256"
run_log baseline_unchanged sha256sum -c "$qb_results/reused_artifacts/baseline_inputs.sha256"
run_log candidate_archive_unchanged sha256sum -c "$qb_results/reused_artifacts/primary_candidate_archive.sha256"
run_log prototype_inputs_unchanged sha256sum -c "$qb_results/reused_artifacts/prototype_inputs.sha256"
run_log pool_artifacts_unchanged sha256sum -c "$qb_results/reused_artifacts/pooled_receive/artifacts.sha256"
run_log direct_artifacts_unchanged sha256sum -c "$qb_results/reused_artifacts/direct_receive/artifacts.sha256"
run_log candidate_source_unchanged verify_candidate_source
qb_stage=complete
printf 'MATCHED_FINAL_PASS baseline=%s results=%s\n' "$qb_base_commit" "$qb_results"
