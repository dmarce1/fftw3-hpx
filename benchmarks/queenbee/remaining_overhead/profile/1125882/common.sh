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
qb_base_build=$qb_original/build
qb_build=$qb_old/build/candidate
qb_archive=$qb_old/results/1125605/prototypes/pooled_receive/libfftw3_hpx.a
qb_hpx=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx/install
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_results=$qb_root/results/$SLURM_JOB_ID
qb_stage=setup
qb_started=$(date -u +%FT%TZ)
mkdir -p "$qb_results/bin" "$qb_results/objects"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1
finish()
{
    local result=$1 outcome=FAIL
    trap - EXIT
    set +e
    if [ "$result" -eq 0 ] && [ "$qb_stage" = complete ]; then outcome=PASS; else [ "$result" -ne 0 ] || result=1; fi
    printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\nstarted_utc\t%s\nfinished_utc\t%s\n' \
      "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage" "$qb_started" "$(date -u +%FT%TZ)" > "$qb_results/FINAL_STATUS"
    printf 'FINAL_STATUS %s exit=%s stage=%s\n' "$outcome" "$result" "$qb_stage"
    exit "$result"
}
trap 'finish "$?"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
run_log()
{
    local label=$1
    shift
    qb_stage=$label
    printf 'START %s %s\n' "$label" "$(date -u +%FT%TZ)"
    { printf 'cd %q\n' "$PWD"; printf '%q ' "$@"; printf '\n'; } > "$qb_results/$label.command"
    if "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"; then
      printf 'PASS %s %s\n' "$label" "$(date -u +%FT%TZ)"
    else
      local status=$?
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
unset HPXRUN_NODES HPXRUN_ARGS
. "$qb_old/results/1125605/primary_hpx-flags.sh"
read -r -a qb_component_flags <<< "$HPX_CFLAGS"
read -r -a qb_app_flags <<< "$HPX_APP_CFLAGS"
read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
qb_launcher=("$qb_mpi/bin/mpiexec" -n 4 --map-by ppr:1:node --bind-to none)
qb_hpx_options=(--hpx:ignore-batch-env --hpx:localities=4 --hpx:threads=64 --hpx:bind=none
 --hpx:ini=hpx.parcel.mpi.enable=1 --hpx:ini=hpx.parcel.mpi.priority=1000
 '--hpx:ini=hpx.parcel.tcp.enable!=0' --hpx:ini=hpx.parcel.bootstrap=mpi
 --hpx:ini=hpx.parcel.mpi.background_threads=1 --hpx:ini=hpx.max_background_threads=1
 --hpx:ini=hpx.parcel.mpi.multithreaded=1 --hpx:ini=hpx.max_idle_backoff_time=1000)
qb_options=(--size=1024 --threads=64 --warmups=2 --samples=7)
qb_mpi_exe=$qb_old/results/1125395/bin/mpi
qb_pool_exe=$qb_old/results/1125605/bin/pooled_receive
cd "$qb_root"
cp "$0" "$qb_results/job.sbatch"
cp "$qb_root/inputs/common.sh" "$qb_results/common.sh"
cp "$qb_old/results/1125605/primary_hpx-flags.sh" "$qb_results/hpx-flags.sh"
{
 date -u; hostname; module -t list 2>&1; gcc --version; "$qb_mpi/bin/mpiexec" --version
 printf 'source_commit='; cat "$qb_root/SOURCE_COMMIT"
 for name in PATH LD_LIBRARY_PATH APEX_DISABLE OMPI_MCA_accelerator OMPI_MCA_pml OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST; do printf '%s=%s\n' "$name" "${!name-}"; done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 --ntasks-per-node=1 --cpus-per-task=1 --label sh -c 'hostname; uname -a; lscpu; numactl --show'
sha256sum "$qb_mpi_exe" "$qb_pool_exe" "$qb_archive" \
 "$qb_original/source/benchmarks/matched_3d.cpp" "$qb_source/benchmarks/matched_3d.cpp" \
 "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" > "$qb_results/fixed_inputs.sha256"
(cd "$qb_root" && sha256sum -c inputs/SHA256SUMS) > "$qb_results/input_verification.log"
run_mpi()
{
 local label=$1 executable=$2
 run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$executable" "${qb_options[@]}"
}
run_hpx()
{
 local label=$1 executable=$2
 run_log "benchmark_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$executable" "${qb_hpx_options[@]}" "${qb_options[@]}"
 run_log "comparison_$label" python3 -I "$qb_source/benchmarks/summarize.py" "$qb_results/benchmark_mpi.log" "$qb_results/benchmark_$label.log"
}
compile_bridge()
{
 local label=$1 source=$2
 mkdir -p "$qb_results/objects/$label"
 run_log "compile_bridge_$label" g++ -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H "${qb_component_flags[@]}" \
  -I"$qb_build" -I"$qb_source" -I"$qb_source/api" -I"$qb_source/hpx" -I"$(dirname "$source")" \
  -c "$source" -o "$qb_results/objects/$label/hpx-comm.o"
 cp "$qb_archive" "$qb_results/objects/$label/libfftw3_hpx.a"
 run_log "replace_bridge_$label" ar r "$qb_results/objects/$label/libfftw3_hpx.a" "$qb_results/objects/$label/hpx-comm.o"
}
compile_hpx()
{
 local label=$1 driver=$2 archive=$3 threads=$4
 shift 4
 run_log "compile_matched_$label" g++ -O3 -march=native -DNDEBUG -std=c++20 -DFFTW_BENCH_HPX \
  "${qb_app_flags[@]}" -I"$qb_source/api" -I"$qb_source/hpx" -I"$(dirname "$driver")" \
  "$driver" "$@" "$archive" "$threads" "$qb_base_build/.libs/libfftw3.a" \
  "${qb_app_libs[@]}" -lm -pthread -o "$qb_results/bin/$label"
}
finish_checks()
{
 run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
 (cd "$qb_root" && sha256sum -c inputs/SHA256SUMS) > "$qb_results/input_recheck.log"
 (cd "$qb_results" && find bin objects -type f -print0 | sort -z | xargs -0 sha256sum) > "$qb_results/artifacts.sha256"
 qb_stage=complete
}
