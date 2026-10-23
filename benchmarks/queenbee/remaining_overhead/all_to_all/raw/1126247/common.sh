#!/bin/bash
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
set -Eeuo pipefail
: "${SLURM_JOB_ID:?Run only in an allocated compute job}"
[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
qb_root=/work/dmarce1/fftw3_hpx_remaining_20261023
qb_old=/work/dmarce1/fftw3_hpx_optimize_20261022
qb_original=/work/dmarce1/fftw3_hpx_benchmark_20261022
qb_source=$qb_root/source
qb_bundle=$qb_root/alltoall
qb_prior=$qb_root/results/1125925
qb_candidate_run=$qb_root/results/1125899
qb_base_build=$qb_original/build
qb_build=$qb_old/build/candidate
qb_archive=$qb_prior/objects/selected_lean/libfftw3_hpx.a
qb_threads=$qb_base_build/threads/.libs/libfftw3_threads.a
qb_core=$qb_base_build/.libs/libfftw3.a
qb_hpx=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_lean=$qb_root/lean_hpx/install
qb_mpi_exe=$qb_old/results/1125395/bin/mpi
qb_old_hpx_exe=$qb_prior/bin/selected_lean
qb_results=$qb_root/results/$SLURM_JOB_ID
qb_stage=setup
qb_started=$(date -u +%FT%TZ)
mkdir "$qb_results"
mkdir -p "$qb_results/bin" "$qb_results/objects" "$qb_results/reused_artifacts"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
exec 3> "$qb_results/commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
finish()
{
    local result=$1 outcome=FAIL
    trap - EXIT
    set +e
    set +x
    if [ "$result" -eq 0 ] && [ "$qb_stage" = complete ]; then
        outcome=PASS
    else
        [ "$result" -ne 0 ] || result=1
        if [ -s "$qb_results/CURRENT_STAGE" ]; then qb_stage=$(cat "$qb_results/CURRENT_STAGE"); fi
    fi
    printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\nstarted_utc\t%s\nfinished_utc\t%s\n' \
        "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage" "$qb_started" "$(date -u +%FT%TZ)" > "$qb_results/FINAL_STATUS"
    printf 'FINAL_STATUS %s exit=%s stage=%s\n' "$outcome" "$result" "$qb_stage"
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
    printf '%s\n' "$label" > "$qb_results/CURRENT_STAGE"
    { printf 'cd %q\n' "$PWD"; printf '%q ' "$@"; printf '\n'; } > "$qb_results/$label.command"
    if "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"; then
        printf '%s\tPASS\t%s\n' "$label" "$((SECONDS-started))" >> "$qb_results/results.tsv"
    else
        local status=$?
        printf '%s\tFAIL\t%s\t%s\n' "$label" "$((SECONDS-started))" "$status" >> "$qb_results/results.tsv"
        return "$status"
    fi
}
qb_inherited_mpi_thread_level_set=${OMPI_MPI_THREAD_LEVEL+x}
qb_inherited_mpi_thread_level=${OMPI_MPI_THREAD_LEVEL-}
module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$qb_hpx/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hpx/lib64:$qb_hpx/lib:${LD_LIBRARY_PATH:-}"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
export OMPI_MCA_accelerator=null OMPI_MCA_pml=ucx OMPI_MCA_btl=self,sm UCX_TLS=rc,sm,self
unset HPXRUN_NODES HPXRUN_ARGS HPXRUN_EXPECTED FFTW_HPX_TRANSPOSE_EXCHANGE
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:bind=none
    '--hpx:ini=hpx.parcel.mpi.enable!=1' --hpx:ini=hpx.parcel.mpi.priority=1000
    '--hpx:ini=hpx.parcel.tcp.enable!=0' '--hpx:ini=hpx.parcel.bootstrap!=mpi'
    --hpx:ini=hpx.parcel.mpi.background_threads=1 --hpx:ini=hpx.max_background_threads=1
    --hpx:ini=hpx.parcel.mpi.multithreaded=1 --hpx:ini=hpx.max_idle_backoff_time=10
    --hpx:ini=hpx.parcel.mpi.sendimm=0 --hpx:threads=64)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
cd "$qb_root"
cp "$0" "$qb_results/job.sbatch"
cp "$qb_bundle/common.sh" "$qb_results/common.sh"
cp "$qb_bundle/PROVENANCE.json" "$qb_results/PROVENANCE.json"
printf 'is_set=%s\nvalue=%s\n' "$qb_inherited_mpi_thread_level_set" "$qb_inherited_mpi_thread_level" > "$qb_results/inherited_mpi_thread_level.txt"
printf 'Accounting must be captured once after completion by the login-session owner, including MaxRSS for steps. This job never polls Slurm.\n' > "$qb_results/accounting_pending.txt"
{ printf 'launcher='; printf '%q ' "${qb_launcher[@]}"; printf '\nhpx_options='; printf '%q ' "${qb_hpx_options[@]}"; printf '\nbenchmark_options='; printf '%q ' "${qb_options[@]}"; printf '\nplacement=numactl --interleave=all, one rank/node, no binding\nper_case_timeout=900s\n'; } > "$qb_results/runtime.txt"
qb_original_ld=$LD_LIBRARY_PATH
qb_lean_ld=$qb_lean/lib64:$qb_lean/lib
IFS=: read -r -a qb_ld_entries <<< "$qb_original_ld"
for entry in "${qb_ld_entries[@]}"; do
    case "$entry" in "$qb_hpx/lib"|"$qb_hpx/lib64"|"$qb_lean/lib"|"$qb_lean/lib64"|'') ;;
        *) qb_lean_ld=$qb_lean_ld:$entry ;;
    esac
done
printf 'original_LD_LIBRARY_PATH=%s\nlean_LD_LIBRARY_PATH=%s\n' "$qb_original_ld" "$qb_lean_ld" > "$qb_results/library_environments.txt"
run_hpx()
{
    local label=$1 mode=$2
    shift 2
    run_log "$label" timeout --signal=TERM --kill-after=30s 900s "${qb_launcher[@]}" \
        /usr/bin/numactl --interleave=all env "FFTW_HPX_TRANSPOSE_EXCHANGE=$mode" \
        "$qb_results/bin/hpx_candidate" "${qb_hpx_options[@]}" "$@"
}
verify_prior_artifacts()
{
    (cd "$qb_prior" && sha256sum -c artifacts.sha256) || return "$?"
    sha256sum -c "$qb_prior/fixed_inputs.sha256" || return "$?"
    sha256sum -c "$qb_prior/reused_binaries.sha256" || return "$?"
    sha256sum -c "$qb_candidate_run/reused_artifacts/lean_installed-artifacts.sha256" || return "$?"
    (cd "$qb_bundle" && sha256sum -c SHA256SUMS) || return "$?"
}
