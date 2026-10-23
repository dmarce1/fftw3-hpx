#!/bin/bash
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
: "${SLURM_JOB_ID:?Run only inside an allocated compute job}"
[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 4 ]
[ "${SLURM_NTASKS:-0}" -eq 4 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 64 ]
qb_root=/work/dmarce1/fftw3_hpx_remaining_20261023
qb_old=/work/dmarce1/fftw3_hpx_optimize_20261022
qb_original=/work/dmarce1/fftw3_hpx_benchmark_20261022
qb_source=$qb_root/source
qb_bundle=$qb_root/confirmation
qb_candidates=$qb_root/candidates
qb_prior=$qb_root/results/1125899
qb_base_build=$qb_original/build
qb_build=$qb_old/build/candidate
qb_archive=$qb_prior/objects/pool_release/libfftw3_hpx.a
qb_hpx=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_lean=$qb_root/lean_hpx/install
qb_results=$qb_root/results/$SLURM_JOB_ID
qb_stage=setup
qb_started=$(date -u +%FT%TZ)
mkdir -p "$qb_results/bin" "$qb_results/objects/selected_lean" "$qb_results/reused_artifacts"
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
    if [ "$result" -eq 0 ] && [ "$qb_stage" = complete ]; then outcome=PASS; else [ "$result" -ne 0 ] || result=1; fi
    printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\ncandidate\t%s\nstarted_utc\t%s\nfinished_utc\t%s\n' \
      "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage" "${FFTW_CANDIDATE:-UNSET}" "$qb_started" "$(date -u +%FT%TZ)" > "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_results/CONFIRMATION_FINAL_STATUS"
    printf 'FINAL_STATUS %s exit=%s stage=%s\n' "$outcome" "$result" "$qb_stage"
    exit "$result"
}
trap 'finish "$?"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
set -x
case "${FFTW_CANDIDATE:-}" in
 parallel_copy) qb_source_sha=55b88660b9ca905049b197c7d9437864985877cc497152413c40c3204f1e12a9 ;;
 hybrid) qb_source_sha=5a2446f92d48d69d25f16f2b19202e7e03159aab57397c415c3e31f8592ae0cd ;;
 rendezvous) qb_source_sha=cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c ;;
 *) printf 'FFTW_CANDIDATE must be explicitly set to parallel_copy, hybrid or rendezvous\n' >&2; exit 2 ;;
esac
qb_bridge=$qb_candidates/prototypes/$FFTW_CANDIDATE/hpx-comm.cpp
qb_comm=$qb_source/hpx/hpx-comm-check.cpp
if [ "$FFTW_CANDIDATE" = rendezvous ]; then qb_comm=$qb_candidates/prototypes/rendezvous/hpx-comm-check.cpp; fi
qb_driver=$qb_source/benchmarks/matched_3d.cpp
qb_threads=$qb_base_build/threads/.libs/libfftw3_threads.a
qb_core=$qb_base_build/.libs/libfftw3.a
qb_mpi_exe=$qb_old/results/1125395/bin/mpi
qb_pool_exe=$qb_prior/bin/pool_release
qb_selected_exe=$qb_prior/bin/$FFTW_CANDIDATE
run_log()
{
    local label=$1
    shift
    qb_stage=$label
    local started=$SECONDS
    printf 'START %s %s\n' "$label" "$(date -u +%FT%TZ)"
    { printf 'cd %q\n' "$PWD"; printf '%q ' "$@"; printf '\n'; } > "$qb_results/$label.command"
    if "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"; then
      printf '%s\tPASS\t%s\n' "$label" "$((SECONDS-started))" >> "$qb_results/results.tsv"
      printf 'PASS %s %s\n' "$label" "$(date -u +%FT%TZ)"
    else
      local status=$?
      printf '%s\tFAIL\t%s\t%s\n' "$label" "$((SECONDS-started))" "$status" >> "$qb_results/results.tsv"
      printf 'FAIL %s exit=%s\n' "$label" "$status"
      return "$status"
    fi
}
module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$qb_hpx/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hpx/lib64:$qb_hpx/lib:${LD_LIBRARY_PATH:-}"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
export OMPI_MCA_accelerator=null OMPI_MCA_pml=ucx OMPI_MCA_btl=self,sm UCX_TLS=rc,sm,self
unset HPXRUN_NODES HPXRUN_ARGS HPXRUN_EXPECTED
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:threads=64 --hpx:bind=none
 '--hpx:ini=hpx.parcel.mpi.enable!=1' --hpx:ini=hpx.parcel.mpi.priority=1000
 '--hpx:ini=hpx.parcel.tcp.enable!=0' '--hpx:ini=hpx.parcel.bootstrap!=mpi'
 --hpx:ini=hpx.parcel.mpi.background_threads=1 --hpx:ini=hpx.max_background_threads=1
 --hpx:ini=hpx.parcel.mpi.multithreaded=1 --hpx:ini=hpx.max_idle_backoff_time=1000)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
cd "$qb_root"
cp "$0" "$qb_results/job.sbatch"
cp "$qb_bundle/common.sh" "$qb_results/common.sh"
cp "$qb_bundle/PROVENANCE.json" "$qb_results/PROVENANCE.json"
printf 'candidate=%s\nsource=%s\nsource_sha256=%s\nprior_job=1125899\n' "$FFTW_CANDIDATE" "$qb_bridge" "$qb_source_sha" > "$qb_results/selection.txt"
printf 'Accounting is to be captured once by the login-session owner after completion; no Slurm polling is performed by this job.\n' > "$qb_results/accounting_pending.txt"
{ printf 'launcher='; printf '%q ' "${qb_launcher[@]}"; printf '\nhpx_options='; printf '%q ' "${qb_hpx_options[@]}"; printf '\nbenchmark_options='; printf '%q ' "${qb_options[@]}"; printf '\nplacement=numactl --interleave=all, one rank/node, no binding\nsendimm_case_extra=--hpx:ini=hpx.parcel.mpi.sendimm=1\n'; } > "$qb_results/runtime.txt"
run_hpx()
{
 local label=$1 executable=$2
 shift 2
 run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$executable" "${qb_hpx_options[@]}" "$@" "${qb_options[@]}"
 run_log "comparison_$label" python3 -I "$qb_source/benchmarks/summarize.py" "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log"
}
verify_prior_artifacts()
{
 (cd "$qb_prior" && sha256sum -c artifacts.sha256) || return "$?"
 sha256sum -c "$qb_prior/fixed_inputs.sha256" || return "$?"
 sha256sum -c "$qb_prior/reused_artifacts/lean_installed-artifacts.sha256" || return "$?"
 (cd "$qb_root" && sha256sum -c candidates/SHA256SUMS && sha256sum -c confirmation/SHA256SUMS)
}
