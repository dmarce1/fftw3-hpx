#!/bin/bash -l
#SBATCH --job-name=fftw_remaining_progress
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/progress-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/progress-%j.err
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



# Prepared only. Root owns review, parameter selection, staging and submission.
# This experiment reuses immutable executables; it performs no builds.
. /work/dmarce1/fftw3_hpx_remaining_20261023/progress/common.sh
qb_stage=prior_validation
grep -q $'^status\tPASS$' "$qb_prior/FINAL_STATUS"
run_log prior_artifacts verify_prior_artifacts
run_log prior_all_checks python3 -I "$qb_bundle/verify_prior.py" "$qb_prior" "$qb_root/confirmation" "$qb_source"
printf '%s  %s\n' cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c "$qb_bridge" | sha256sum -c -
cmp "$qb_bridge" "$qb_prior/objects/selected_lean/source-hpx-comm.cpp"
cmp "$qb_driver" "$qb_prior/matched_3d.cpp"
cmp "$qb_driver" "$qb_candidates/drivers/matched_3d.cpp"
sha256sum "$qb_mpi_exe" "$qb_pool_exe" "$qb_lean_exe" "$qb_comm_exe" "$qb_archive" \
 "$qb_candidate_run/objects/pool_release/libfftw3_hpx.a" "$qb_base_build/threads/.libs/libfftw3_threads.a" \
 "$qb_base_build/.libs/libfftw3.a" "$qb_base_build/mpi/.libs/libfftw3_mpi.a" \
 "$qb_bridge" "$qb_driver" "$qb_prior/hpx-comm-check.cpp" "$qb_prior/lean_hpx-flags.sh" \
 "$qb_prior/original_hpx-flags.sh" "$qb_prior/FINAL_STATUS" "$qb_prior/results.tsv" \
 "$qb_prior/confirmation_comparison.json" "$qb_prior/archive_members.log" \
 "$qb_prior/artifacts.sha256" "$qb_prior/fixed_inputs.sha256" "$qb_prior/reused_binaries.sha256" \
 "$qb_prior"/benchmark_*.log "$qb_prior"/comparison_*.log "$qb_prior"/communication_*.log \
 "$qb_root/SOURCE_COMMIT" "$qb_candidates/SHA256SUMS" "$qb_root/confirmation/SHA256SUMS" \
 "$qb_bundle/SHA256SUMS" > "$qb_results/fixed_inputs.sha256"
for name in FINAL_STATUS artifacts.sha256 fixed_inputs.sha256 reused_binaries.sha256 archive_members.log selection.txt lean_hpx-flags.sh original_hpx-flags.sh; do
 cp "$qb_prior/$name" "$qb_results/reused_artifacts/1125925_$name"
done
{
 date -u; hostname; module -t list 2>&1; gcc --version; "$qb_mpi/bin/mpiexec" --version
 printf 'source_commit='; cat "$qb_root/SOURCE_COMMIT"
 for name in FFTW_SENDIMM PATH LD_LIBRARY_PATH HWLOC_COMPONENTS APEX_DISABLE OMPI_MCA_accelerator OMPI_MCA_pml OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST; do printf '%s=%s\n' "$name" "${!name-}"; done
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
{
 printf 'case\texecutable\tHPX_install\tworkers\tmax_idle_backoff_time\tsendimm\tidle_loop_count\n'
 printf 'mpi_start\t%s\tnone\t64\tn/a\tn/a\tn/a\n' "$qb_mpi_exe"
 printf 'pool_release\t%s\toriginal\t64\t1000\tdefault0\tdefault200000\n' "$qb_pool_exe"
 printf 'lean_baseline1000\t%s\tlean\t64\t1000\t%s\tdefault200000\n' "$qb_lean_exe" "$FFTW_SENDIMM"
 printf 'lean_backoff1\t%s\tlean\t64\t1\t%s\tdefault200000\n' "$qb_lean_exe" "$FFTW_SENDIMM"
 printf 'lean_baseline1000repeat\t%s\tlean\t64\t1000\t%s\tdefault200000\n' "$qb_lean_exe" "$FFTW_SENDIMM"
 printf 'mpi_end\t%s\tnone\t64\tn/a\tn/a\tn/a\n' "$qb_mpi_exe"
} > "$qb_results/case_table.tsv"
qb_stage=lean_dependencies_and_communication
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_log lean_ldd ldd "$qb_lean_exe"
 run_log lean_comm_ldd ldd "$qb_comm_exe"
 run_log lean_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_ldd.log" "$qb_lean" "$qb_mpi"
 run_log lean_comm_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_comm_ldd.log" "$qb_lean" "$qb_mpi"
 for cap in 1000 1; do
  label=lean_baseline1000
  if [ "$cap" = 1 ]; then label=lean_backoff1; fi
  run_log "communication_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
   "$qb_comm_exe" "${qb_hpx_options[@]}" --hpx:threads=2 \
   "--hpx:ini=hpx.max_idle_backoff_time=$cap" "--hpx:ini=hpx.parcel.mpi.sendimm=$FFTW_SENDIMM"
  [ "$(grep -c '^communication check PASS$' "$qb_results/communication_$label.log")" -eq 4 ]
 done
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
sha256sum "$qb_mpi_exe" "$qb_pool_exe" "$qb_lean_exe" "$qb_comm_exe" > "$qb_results/reused_binaries.sha256"
run_log ldd_pool_release ldd "$qb_pool_exe"
run_log benchmark_mpi_start "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
run_hpx pool_release "$qb_pool_exe" 1000
qb_stage=lean_three_case_sequence
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_hpx lean_baseline1000 "$qb_lean_exe" 1000 "--hpx:ini=hpx.parcel.mpi.sendimm=$FFTW_SENDIMM"
 run_hpx lean_backoff1 "$qb_lean_exe" 1 "--hpx:ini=hpx.parcel.mpi.sendimm=$FFTW_SENDIMM"
 run_hpx lean_baseline1000repeat "$qb_lean_exe" 1000 "--hpx:ini=hpx.parcel.mpi.sendimm=$FFTW_SENDIMM"
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log benchmark_mpi_end "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
run_log progress_checks python3 -I "$qb_bundle/check_results.py" "$qb_results" "$qb_source" "$FFTW_SENDIMM"
run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
run_log reused_binaries_unchanged sha256sum -c "$qb_results/reused_binaries.sha256"
run_log prior_artifacts_unchanged verify_prior_artifacts
qb_stage=complete
