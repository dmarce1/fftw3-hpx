#!/bin/bash -l
#SBATCH --job-name=fftw_no_backoff
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/no-backoff-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/no-backoff-%j.err
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


# Prepared only: no builds; root owns staging and submission. Scheduler mode 1255 removes only idle backoff from default 3303.
. /work/dmarce1/fftw3_hpx_remaining_20261023/no_backoff/common.sh
qb_stage=prior_validation
run_log expected_binaries sha256sum -c "$qb_bundle/EXPECTED_BINARIES.sha256"
run_log prior_artifacts verify_prior_artifacts
run_log prior_clean_checks python3 -I "$qb_profile_bundle/verify_prior.py" "$qb_prior" "$qb_root/confirmation" "$qb_source"
run_log prior_profile_checks python3 -I "$qb_bundle/verify_profile_prior.py" "$qb_profile_prior" "$qb_profile_bundle" "$qb_source"
printf '%s  %s\n' cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c "$qb_bridge" | sha256sum -c -
cmp "$qb_bridge" "$qb_prior/objects/selected_lean/source-hpx-comm.cpp"
cmp "$qb_driver" "$qb_prior/matched_3d.cpp"
cmp "$qb_driver" "$qb_candidates/drivers/matched_3d.cpp"
sha256sum "$qb_mpi_exe" "$qb_lean_exe" "$qb_comm_exe" "$qb_profile_exe" "$qb_archive" \
 "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" \
 "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_bridge" "$qb_driver" "$qb_prior/hpx-comm-check.cpp" \
 "$qb_prior/lean_hpx-flags.sh" "$qb_prior/FINAL_STATUS" "$qb_prior/artifacts.sha256" \
 "$qb_prior/fixed_inputs.sha256" "$qb_prior/reused_binaries.sha256" \
 "$qb_profile_prior/FINAL_STATUS" "$qb_profile_prior/artifacts.sha256" "$qb_profile_prior/fixed_inputs.sha256" \
 "$qb_profile_prior/reused_binaries.sha256" "$qb_profile_prior/remaining_profile_manifest.json" \
 "$qb_profile_prior/lean_profile_comparison.json" "$qb_profile_prior/profile_analysis.json" \
 "$qb_profile_prior"/benchmark_*.log "$qb_profile_prior"/analysis_*_profile.log \
 "$qb_profile_prior/archive_members.log" "$qb_root/SOURCE_COMMIT" "$qb_candidates/SHA256SUMS" \
 "$qb_root/confirmation/SHA256SUMS" "$qb_profile_bundle/SHA256SUMS" "$qb_bundle/SHA256SUMS" \
 > "$qb_results/fixed_inputs.sha256"
for name in FINAL_STATUS artifacts.sha256 fixed_inputs.sha256 reused_binaries.sha256 archive_members.log; do
 cp "$qb_prior/$name" "$qb_results/reused_artifacts/1125925_$name"
 cp "$qb_profile_prior/$name" "$qb_results/reused_artifacts/1125966_$name"
done
{
 date -u; hostname; module -t list 2>&1; "$qb_mpi/bin/mpiexec" --version
 printf 'source_commit='; cat "$qb_root/SOURCE_COMMIT"
 for name in PATH LD_LIBRARY_PATH HWLOC_COMPONENTS APEX_DISABLE OMPI_MCA_accelerator OMPI_MCA_pml OMPI_MCA_btl UCX_TLS OMPI_MPI_THREAD_LEVEL SLURM_JOB_ID SLURM_JOB_NODELIST; do printf '%s=%s\n' "$name" "${!name-}"; done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 --ntasks-per-node=1 --cpus-per-task=1 --label sh -c 'hostname; uname -a; lscpu; numactl --show'
qb_original_ld=$LD_LIBRARY_PATH
qb_lean_ld=$qb_lean/lib64:$qb_lean/lib
IFS=: read -r -a qb_ld_entries <<< "$qb_original_ld"
for entry in "${qb_ld_entries[@]}"; do
 case "$entry" in "$qb_hpx/lib"|"$qb_hpx/lib64"|"$qb_lean/lib"|"$qb_lean/lib64"|'') ;;
  *) qb_lean_ld=$qb_lean_ld:$entry ;;
 esac
done
printf 'original_LD_LIBRARY_PATH=%s\nlean_LD_LIBRARY_PATH=%s\n' "$qb_original_ld" "$qb_lean_ld" > "$qb_results/library_environments.txt"
[ "${OMPI_MPI_THREAD_LEVEL+x}" = "$qb_inherited_mpi_thread_level_set" ]
[ "${OMPI_MPI_THREAD_LEVEL-}" = "$qb_inherited_mpi_thread_level" ]
{
 printf 'case\trole\texecutable\tworkers\tbackoff_cap_ms\tscheduler_mode\tsendimm\n'
 printf 'mpi_start\tprimary\t%s\t64\tn/a\tn/a\tn/a\n' "$qb_mpi_exe"
 printf 'hpx_cap10\tprimary\t%s\t64\t10\tdefault_3303\t0\n' "$qb_lean_exe"
 printf 'hpx_no_backoff\tprimary\t%s\t64\t10\t1255\t0\n' "$qb_lean_exe"
 printf 'hpx_cap10repeat\tprimary\t%s\t64\t10\tdefault_3303\t0\n' "$qb_lean_exe"
 printf 'mpi_end\tprimary\t%s\t64\tn/a\tn/a\tn/a\n' "$qb_mpi_exe"
} > "$qb_results/case_table.tsv"
run_log mpi_ldd ldd "$qb_mpi_exe"
run_log mpi_dependencies python3 -I "$qb_profile_bundle/check_mpi_ldd.py" "$qb_results/mpi_ldd.log" "$qb_mpi"
qb_stage=lean_dependencies_and_communication
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 for label in lean comm profile; do
  executable=$qb_lean_exe
  if [ "$label" = comm ]; then executable=$qb_comm_exe; fi
  if [ "$label" = profile ]; then executable=$qb_profile_exe; fi
  run_log "ldd_$label" ldd "$executable"
  run_log "dependencies_$label" python3 -I "$qb_profile_bundle/check_lean_ldd.py" "$qb_results/ldd_$label.log" "$qb_lean" "$qb_mpi"
 done
 run_log communication_cap10 "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
  "$qb_comm_exe" "${qb_hpx_options[@]}" --hpx:threads=2 \
  --hpx:ini=hpx.max_idle_backoff_time=10 --hpx:ini=hpx.parcel.mpi.sendimm=0
 [ "$(grep -c '^communication check PASS$' "$qb_results/communication_cap10.log")" -eq 4 ]
 run_log communication_no_backoff "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
  "$qb_comm_exe" "${qb_hpx_options[@]}" --hpx:threads=2 \
  --hpx:ini=hpx.max_idle_backoff_time=10 --hpx:ini=hpx.default_scheduler_mode=1255 --hpx:ini=hpx.parcel.mpi.sendimm=0
 [ "$(grep -c '^communication check PASS$' "$qb_results/communication_no_backoff.log")" -eq 4 ]
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
sha256sum "$qb_mpi_exe" "$qb_lean_exe" "$qb_comm_exe" "$qb_profile_exe" > "$qb_results/reused_binaries.sha256"
run_log benchmark_mpi_start "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
qb_stage=clean_three_case_sequence
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_hpx hpx_cap10 "$qb_lean_exe" 10 --hpx:ini=hpx.parcel.mpi.sendimm=0
 run_hpx hpx_no_backoff "$qb_lean_exe" 10 --hpx:ini=hpx.default_scheduler_mode=1255 --hpx:ini=hpx.parcel.mpi.sendimm=0
 run_hpx hpx_cap10repeat "$qb_lean_exe" 10 --hpx:ini=hpx.parcel.mpi.sendimm=0
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log benchmark_mpi_end "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
[ "${OMPI_MPI_THREAD_LEVEL+x}" = "$qb_inherited_mpi_thread_level_set" ]
[ "${OMPI_MPI_THREAD_LEVEL-}" = "$qb_inherited_mpi_thread_level" ]
run_log no_backoff_checks python3 -I "$qb_bundle/check_results.py" "$qb_results" "$qb_source"
run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
run_log reused_binaries_unchanged sha256sum -c "$qb_results/reused_binaries.sha256"
run_log prior_artifacts_unchanged verify_prior_artifacts
qb_stage=complete
