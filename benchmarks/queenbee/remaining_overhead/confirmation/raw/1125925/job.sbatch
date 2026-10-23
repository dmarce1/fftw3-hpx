#!/bin/bash -l
#SBATCH --job-name=fftw_remaining_confirmation
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/confirmation-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/confirmation-%j.err
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



# Prepared only. Root owns review, selection, staging and submission.
. /work/dmarce1/fftw3_hpx_remaining_20261023/confirmation/common.sh
qb_stage=prior_validation
grep -q $'^status\tPASS$' "$qb_prior/FINAL_STATUS"
run_log prior_artifacts verify_prior_artifacts
run_log prior_all_checks python3 -I "$qb_bundle/verify_prior.py" "$qb_prior" "$qb_candidates" "$qb_source" "$FFTW_CANDIDATE"
printf '%s  %s\n' "$qb_source_sha" "$qb_bridge" | sha256sum -c -
cmp "$qb_bridge" "$qb_prior/objects/$FFTW_CANDIDATE/source-hpx-comm.cpp"
cmp "$qb_driver" "$qb_candidates/drivers/matched_3d.cpp"
cmp "$qb_driver" "$qb_original/source/benchmarks/matched_3d.cpp"
sha256sum "$qb_mpi_exe" "$qb_pool_exe" "$qb_selected_exe" "$qb_archive" "$qb_threads" "$qb_core" \
 "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_bridge" "$qb_comm" "$qb_driver" "$qb_build/config.h" \
 "$qb_source/hpx/hpx-comm.h" "$qb_source/hpx/fftw3-hpx.h" "$qb_source/benchmarks/summarize.py" \
 "$qb_prior/hpx-flags.sh" "$qb_prior/lean_metadata/hpx-flags.sh" "$qb_prior/FINAL_STATUS" \
 "$qb_prior/candidate_comparison.json" "$qb_prior/results.tsv" "$qb_prior/artifacts.sha256" \
 "$qb_prior/fixed_inputs.sha256" "$qb_prior/reused_artifacts/lean_installed-artifacts.sha256" \
 "$qb_prior"/benchmark_*.log "$qb_prior"/comparison_*.log "$qb_prior"/communication_*.log \
 "$qb_root/SOURCE_COMMIT" "$qb_candidates/SHA256SUMS" "$qb_bundle/SHA256SUMS" > "$qb_results/fixed_inputs.sha256"
cp "$qb_prior/FINAL_STATUS" "$qb_results/reused_artifacts/1125899_FINAL_STATUS"
cp "$qb_prior/candidate_comparison.json" "$qb_results/reused_artifacts/1125899_candidate_comparison.json"
cp "$qb_prior/artifacts.sha256" "$qb_results/reused_artifacts/1125899_artifacts.sha256"
cp "$qb_prior/fixed_inputs.sha256" "$qb_results/reused_artifacts/1125899_fixed_inputs.sha256"
cp "$qb_prior/hpx-flags.sh" "$qb_results/original_hpx-flags.sh"
cp "$qb_prior/lean_metadata/hpx-flags.sh" "$qb_results/lean_hpx-flags.sh"
cp "$qb_bridge" "$qb_results/objects/selected_lean/source-hpx-comm.cpp"
cp "$qb_driver" "$qb_results/matched_3d.cpp"
cp "$qb_comm" "$qb_results/hpx-comm-check.cpp"
{
 date -u; hostname; module -t list 2>&1; gcc --version; "$qb_mpi/bin/mpiexec" --version
 printf 'source_commit='; cat "$qb_root/SOURCE_COMMIT"
 for name in FFTW_CANDIDATE PATH LD_LIBRARY_PATH HWLOC_COMPONENTS APEX_DISABLE OMPI_MCA_accelerator OMPI_MCA_pml OMPI_MCA_btl UCX_TLS SLURM_JOB_ID SLURM_JOB_NODELIST; do printf '%s=%s\n' "$name" "${!name-}"; done
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
# All HPX-consuming C++ code is rebuilt with the existing lean metadata. The
# subprocess scope restores original flags and loader state without eval.
qb_stage=lean_build_and_communication
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 . "$qb_prior/lean_metadata/hpx-flags.sh"
 read -r -a qb_component_flags <<< "$HPX_CFLAGS"
 read -r -a qb_app_flags <<< "$HPX_APP_CFLAGS"
 read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
 qb_out=$qb_results/objects/selected_lean
 run_log compile_bridge_selected_lean g++ -O3 -march=native -DHAVE_CONFIG_H "${qb_component_flags[@]}" -DNDEBUG \
  -I"$qb_build" -I"$qb_source" -I"$qb_source/api" -I"$qb_source/hpx" -I"$(dirname "$qb_bridge")" \
  -c "$qb_bridge" -o "$qb_out/hpx-comm.o"
 cp "$qb_archive" "$qb_out/libfftw3_hpx.a"
 run_log replace_bridge_selected_lean ar r "$qb_out/libfftw3_hpx.a" "$qb_out/hpx-comm.o"
 run_log archive_members python3 -I "$qb_bundle/check_members.py" "$qb_archive" "$qb_out/libfftw3_hpx.a"
 run_log compile_matched_selected_lean g++ -O3 -march=native -DNDEBUG -std=c++20 -DFFTW_BENCH_HPX \
  "${qb_app_flags[@]}" -DNDEBUG -I"$qb_source/api" -I"$qb_source/hpx" \
  "$qb_driver" "$qb_out/libfftw3_hpx.a" "$qb_threads" "$qb_core" \
  "${qb_app_libs[@]}" -lm -pthread -o "$qb_results/bin/selected_lean"
 run_log compile_comm_selected_lean g++ -O3 -march=native -std=c++20 "${qb_app_flags[@]}" \
  -I"$qb_build" -I"$qb_source/api" -I"$qb_source/hpx" -UNDEBUG \
  "$qb_comm" "$qb_out/libfftw3_hpx.a" "$qb_threads" "$qb_core" \
  "${qb_app_libs[@]}" -lm -pthread -UNDEBUG -o "$qb_results/bin/selected_lean_comm_check"
 run_log lean_ldd ldd "$qb_results/bin/selected_lean"
 run_log lean_comm_ldd ldd "$qb_results/bin/selected_lean_comm_check"
 run_log lean_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_ldd.log" "$qb_lean" "$qb_mpi"
 run_log lean_comm_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_comm_ldd.log" "$qb_lean" "$qb_mpi"
 qb_comm_options=()
 for option in "${qb_hpx_options[@]}"; do
  if [ "$option" != --hpx:threads=64 ]; then qb_comm_options+=("$option"); fi
 done
 run_log communication_selected_lean "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
  "$qb_results/bin/selected_lean_comm_check" "${qb_comm_options[@]}" --hpx:threads=2
 [ "$(grep -c '^communication check PASS$' "$qb_results/communication_selected_lean.log")" -eq 4 ]
 run_log communication_selected_lean_sendimm "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
  "$qb_results/bin/selected_lean_comm_check" "${qb_comm_options[@]}" --hpx:threads=2 --hpx:ini=hpx.parcel.mpi.sendimm=1
 [ "$(grep -c '^communication check PASS$' "$qb_results/communication_selected_lean_sendimm.log")" -eq 4 ]
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
# Freeze both the reused executable hashes and every newly built artifact
# before the first primary timing, then verify the same files after all runs.
sha256sum "$qb_mpi_exe" "$qb_pool_exe" "$qb_selected_exe" > "$qb_results/reused_binaries.sha256"
(cd "$qb_results" && find bin objects -type f -print0 | sort -z | xargs -0 sha256sum) > "$qb_results/artifacts.sha256"
run_log ldd_pool_release ldd "$qb_pool_exe"
run_log ldd_selected_original ldd "$qb_selected_exe"
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
run_hpx pool_release "$qb_pool_exe"
run_hpx selected_original "$qb_selected_exe"
qb_stage=benchmark_selected_lean
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_hpx selected_lean "$qb_results/bin/selected_lean"
 run_hpx selected_lean_sendimm "$qb_results/bin/selected_lean" --hpx:ini=hpx.parcel.mpi.sendimm=1
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log confirmation_checks python3 -I "$qb_bundle/check_results.py" "$qb_results" "$FFTW_CANDIDATE"
run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
run_log reused_binaries_unchanged sha256sum -c "$qb_results/reused_binaries.sha256"
qb_stage=artifacts_unchanged
(cd "$qb_results" && sha256sum -c artifacts.sha256) > "$qb_results/artifacts_recheck.log"
run_log prior_artifacts_unchanged verify_prior_artifacts
qb_stage=complete
