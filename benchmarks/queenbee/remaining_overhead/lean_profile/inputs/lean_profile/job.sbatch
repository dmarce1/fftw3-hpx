#!/bin/bash -l
#SBATCH --job-name=fftw_lean_profile
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/lean-profile-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/lean-profile-%j.err
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



# Prepared only. All compilation is sequential inside this compute allocation.
. /work/dmarce1/fftw3_hpx_remaining_20261023/lean_profile/common.sh
qb_stage=prior_validation
grep -q $'^status\tPASS$' "$qb_prior/FINAL_STATUS"
run_log prior_artifacts verify_prior_artifacts
run_log prior_all_checks python3 -I "$qb_bundle/verify_prior.py" "$qb_prior" "$qb_root/confirmation" "$qb_source"
printf '%s  %s\n' cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c "$qb_bridge" | sha256sum -c -
cmp "$qb_bridge" "$qb_prior/objects/selected_lean/source-hpx-comm.cpp"
cmp "$qb_driver" "$qb_prior/matched_3d.cpp"
cmp "$qb_driver" "$qb_candidates/drivers/matched_3d.cpp"
qb_threads=$qb_base_build/threads/.libs/libfftw3_threads.a
qb_mpi_archive=$qb_base_build/mpi/.libs/libfftw3_mpi.a
qb_core=$qb_base_build/.libs/libfftw3.a
qb_comm_source=$qb_prior/hpx-comm-check.cpp
sha256sum "$qb_mpi_exe" "$qb_lean_exe" "$qb_comm_exe" "$qb_archive" "$qb_threads" "$qb_mpi_archive" "$qb_core" \
 "$qb_bridge" "$qb_driver" "$qb_comm_source" "$qb_build/config.h" "$qb_base_build/config.h" \
 "$qb_source/hpx/transpose-pairwise.c" "$qb_source/mpi/transpose-pairwise.c" "$qb_source/threads/threads.c" \
 "$qb_prior/lean_hpx-flags.sh" "$qb_prior/FINAL_STATUS" "$qb_prior/confirmation_comparison.json" \
 "$qb_prior/artifacts.sha256" "$qb_prior/fixed_inputs.sha256" "$qb_prior/reused_binaries.sha256" \
 "$qb_root/SOURCE_COMMIT" "$qb_candidates/SHA256SUMS" "$qb_root/confirmation/SHA256SUMS" \
 "$qb_bundle/SHA256SUMS" > "$qb_results/fixed_inputs.sha256"
for name in FINAL_STATUS artifacts.sha256 fixed_inputs.sha256 reused_binaries.sha256 archive_members.log selection.txt lean_hpx-flags.sh; do
 cp "$qb_prior/$name" "$qb_results/reused_artifacts/1125925_$name"
done
{
 date -u; hostname; module -t list 2>&1; gcc --version; "$qb_mpi/bin/mpiexec" --version
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
# Normal MPI runs retain the inherited thread-level environment verbatim.
[ "${OMPI_MPI_THREAD_LEVEL+x}" = "$qb_inherited_mpi_thread_level_set" ]
[ "${OMPI_MPI_THREAD_LEVEL-}" = "$qb_inherited_mpi_thread_level" ]
run_log compile_mpi_thread_probe "$qb_mpi/bin/mpicc" -O2 "$qb_bundle/mpi_thread_probe.c" -o "$qb_results/bin/mpi_thread_probe"
run_log mpi_thread_probe_normal "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_results/bin/mpi_thread_probe"
run_log mpi_thread_probe_multiple "${qb_launcher[@]}" /usr/bin/numactl --interleave=all env OMPI_MPI_THREAD_LEVEL=3 "$qb_results/bin/mpi_thread_probe" --expect-multiple
qb_diag=$qb_results/diagnostic_source
cp -a "$qb_source" "$qb_diag"
cp "$qb_bridge" "$qb_diag/hpx/hpx-comm.cpp"
run_log instrument python3 -I "$qb_bundle/profile/instrument.py" "$qb_diag" --threads --pairwise
cp "$qb_diag/remaining_profile_manifest.json" "$qb_results/remaining_profile_manifest.json"
run_log transformed_sources python3 -I "$qb_bundle/verify_transformation.py" "$qb_source" "$qb_diag" "$qb_bundle/profile" "$qb_bridge"
# A shared new helper/header ABI is used by both diagnostics. No old diagnostic
# binary/object is reused. All original C archives and clean controls stay fixed.
run_log compile_profile g++ -O3 -march=native -DNDEBUG -std=c++20 -pthread -I"$qb_diag/benchmarks" \
 -c "$qb_diag/benchmarks/remaining_profile.cpp" -o "$qb_results/objects/diagnostic/remaining_profile.o"
run_log compile_mpi_interposer "$qb_mpi/bin/mpicxx" -O3 -march=native -DNDEBUG -std=c++20 -pthread -I"$qb_diag/benchmarks" \
 -c "$qb_diag/benchmarks/remaining_mpi_profile.cpp" -o "$qb_results/objects/diagnostic/remaining_mpi_profile.o"
qb_threads_member=$(ar t "$qb_threads" | awk '/(^|_la-)threads[.]o$/ {print}')
qb_mpi_member=$(ar t "$qb_mpi_archive" | awk '/(^|_la-)transpose-pairwise[.]o$/ {print}')
qb_hpx_member=$(ar t "$qb_archive" | awk '/(^|_la-)transpose-pairwise[.]o$/ {print}')
for member in "$qb_threads_member" "$qb_mpi_member" "$qb_hpx_member"; do
 [ -n "$member" ] && [ "$(printf '%s\n' "$member" | wc -l)" -eq 1 ]
done
run_log compile_threads gcc -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_base_build" -I"$qb_diag" -I"$qb_diag/threads" -I"$qb_diag/api" \
 -c "$qb_diag/threads/threads.c" -o "$qb_results/objects/threads_profile/$qb_threads_member"
cp "$qb_threads" "$qb_results/objects/threads_profile/libfftw3_threads.a"
run_log replace_threads ar r "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_results/objects/threads_profile/$qb_threads_member"
run_log compile_mpi_pairwise "$qb_mpi/bin/mpicc" -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_base_build" -I"$qb_diag" -I"$qb_diag/mpi" -I"$qb_diag/api" \
 -c "$qb_diag/mpi/transpose-pairwise.c" -o "$qb_results/objects/mpi_profile/$qb_mpi_member"
cp "$qb_mpi_archive" "$qb_results/objects/mpi_profile/libfftw3_mpi.a"
run_log replace_mpi_pairwise ar r "$qb_results/objects/mpi_profile/libfftw3_mpi.a" "$qb_results/objects/mpi_profile/$qb_mpi_member"
run_log compile_hpx_pairwise gcc -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_build" -I"$qb_diag" -I"$qb_diag/hpx" -I"$qb_diag/api" \
 -c "$qb_diag/hpx/transpose-pairwise.c" -o "$qb_results/objects/hpx_profile/$qb_hpx_member"
run_log compile_mpi_profile "$qb_mpi/bin/mpicxx" -O3 -march=native -DNDEBUG -std=c++20 -I"$qb_diag/api" -I"$qb_diag/mpi" -I"$qb_diag/benchmarks" \
 "$qb_diag/benchmarks/matched_3d.cpp" "$qb_results/objects/diagnostic/remaining_profile.o" "$qb_results/objects/diagnostic/remaining_mpi_profile.o" \
 "$qb_results/objects/mpi_profile/libfftw3_mpi.a" "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_core" -lm -pthread -o "$qb_results/bin/mpi_profile"
qb_stage=lean_diagnostic_build
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 . "$qb_prior/lean_hpx-flags.sh"
 read -r -a qb_component_flags <<< "$HPX_CFLAGS"
 read -r -a qb_app_flags <<< "$HPX_APP_CFLAGS"
 read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
 run_log compile_bridge g++ -O3 -march=native -DHAVE_CONFIG_H "${qb_component_flags[@]}" -DNDEBUG \
  -I"$qb_build" -I"$qb_diag" -I"$qb_diag/api" -I"$qb_diag/hpx" -I"$qb_diag/benchmarks" \
  -c "$qb_diag/hpx/hpx-comm.cpp" -o "$qb_results/objects/hpx_profile/hpx-comm.o"
 cp "$qb_archive" "$qb_results/objects/hpx_profile/libfftw3_hpx.a"
 run_log replace_bridge ar r "$qb_results/objects/hpx_profile/libfftw3_hpx.a" "$qb_results/objects/hpx_profile/hpx-comm.o"
 run_log replace_hpx_pairwise ar r "$qb_results/objects/hpx_profile/libfftw3_hpx.a" "$qb_results/objects/hpx_profile/$qb_hpx_member"
 run_log compile_hpx_profile g++ -O3 -march=native -DNDEBUG -std=c++20 -DFFTW_BENCH_HPX "${qb_app_flags[@]}" -DNDEBUG \
  -I"$qb_diag/api" -I"$qb_diag/hpx" -I"$qb_diag/benchmarks" "$qb_diag/benchmarks/matched_3d.cpp" \
  "$qb_results/objects/diagnostic/remaining_profile.o" "$qb_results/objects/hpx_profile/libfftw3_hpx.a" \
  "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_core" "${qb_app_libs[@]}" -lm -pthread -o "$qb_results/bin/hpx_profile"
 run_log compile_profile_comm g++ -O3 -march=native -std=c++20 "${qb_app_flags[@]}" -I"$qb_build" -I"$qb_diag/api" -I"$qb_diag/hpx" -UNDEBUG \
  "$qb_comm_source" "$qb_results/objects/diagnostic/remaining_profile.o" "$qb_results/objects/hpx_profile/libfftw3_hpx.a" \
  "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_core" "${qb_app_libs[@]}" -lm -pthread -UNDEBUG -o "$qb_results/bin/hpx_profile_comm_check"
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log archive_members python3 -I "$qb_bundle/check_members.py" "$qb_archive" "$qb_mpi_archive" "$qb_threads" "$qb_results/objects"
run_log ldd_mpi_control ldd "$qb_mpi_exe"
run_log mpi_control_dependencies python3 -I "$qb_bundle/check_mpi_ldd.py" "$qb_results/ldd_mpi_control.log" "$qb_mpi"
run_log ldd_mpi_profile ldd "$qb_results/bin/mpi_profile"
run_log mpi_profile_dependencies python3 -I "$qb_bundle/check_mpi_ldd.py" "$qb_results/ldd_mpi_profile.log" "$qb_mpi"
qb_stage=lean_dependencies_and_communication
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 for label in lean_control hpx_profile hpx_profile_comm_check; do
  executable=$qb_results/bin/$label
  if [ "$label" = lean_control ]; then executable=$qb_lean_exe; fi
  run_log "ldd_$label" ldd "$executable"
  run_log "dependencies_$label" python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/ldd_$label.log" "$qb_lean" "$qb_mpi"
 done
 for label in lean_control hpx_profile; do
  executable=$qb_comm_exe
  if [ "$label" = hpx_profile ]; then executable=$qb_results/bin/hpx_profile_comm_check; fi
  run_log "communication_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$executable" "${qb_hpx_options[@]}" \
   --hpx:threads=2 --hpx:ini=hpx.max_idle_backoff_time=1000 --hpx:ini=hpx.parcel.mpi.sendimm=0
  [ "$(grep -c '^communication check PASS$' "$qb_results/communication_$label.log")" -eq 4 ]
 done
)
sha256sum "$qb_mpi_exe" "$qb_lean_exe" "$qb_comm_exe" > "$qb_results/reused_binaries.sha256"
(cd "$qb_results" && find bin objects -type f -print0 | sort -z | xargs -0 sha256sum) > "$qb_results/artifacts.sha256"
run_log benchmark_mpi "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
qb_stage=primary_lean
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_hpx lean_control "$qb_lean_exe" 1000 --hpx:ini=hpx.parcel.mpi.sendimm=0
)
mkdir "$qb_results/profile_mpi" "$qb_results/profile_hpx"
run_log benchmark_mpi_profile "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
 env "FFTW_REMAINING_PROFILE_DIR=$qb_results/profile_mpi" "$qb_results/bin/mpi_profile" "${qb_options[@]}"
qb_stage=diagnostic_lean
(
 export LD_LIBRARY_PATH="$qb_lean_ld"
 run_log benchmark_hpx_profile "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
  env "FFTW_REMAINING_PROFILE_DIR=$qb_results/profile_hpx" "$qb_results/bin/hpx_profile" "${qb_hpx_options[@]}" \
  --hpx:threads=64 --hpx:ini=hpx.max_idle_backoff_time=1000 --hpx:ini=hpx.parcel.mpi.sendimm=0 "${qb_options[@]}"
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log benchmark_mpi_thread_multiple "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
 env OMPI_MPI_THREAD_LEVEL=3 "$qb_mpi_exe" "${qb_options[@]}"
[ "${OMPI_MPI_THREAD_LEVEL+x}" = "$qb_inherited_mpi_thread_level_set" ]
[ "${OMPI_MPI_THREAD_LEVEL-}" = "$qb_inherited_mpi_thread_level" ]
qb_stage=assemble_analysis_logs
for backend in mpi hpx; do
 cp "$qb_results/benchmark_${backend}_profile.log" "$qb_results/analysis_${backend}_profile.log"
 for rank in 0 1 2 3; do
  [ -s "$qb_results/profile_${backend}/${backend}-${rank}.log" ]
  cat "$qb_results/profile_${backend}/${backend}-${rank}.log" >> "$qb_results/analysis_${backend}_profile.log"
 done
 [ "$(find "$qb_results/profile_${backend}" -maxdepth 1 -type f | wc -l)" -eq 4 ]
done
run_log diagnostic_analysis python3 -I "$qb_bundle/profile/analyze.py" "$qb_results/analysis_mpi_profile.log" "$qb_results/analysis_hpx_profile.log" --json "$qb_results/profile_analysis.json"
run_log profile_checks python3 -I "$qb_bundle/check_results.py" "$qb_results" "$qb_source"
run_log transformed_sources_unchanged python3 -I "$qb_bundle/verify_transformation.py" "$qb_source" "$qb_diag" "$qb_bundle/profile" "$qb_bridge"
run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
run_log reused_binaries_unchanged sha256sum -c "$qb_results/reused_binaries.sha256"
qb_stage=artifacts_unchanged
(cd "$qb_results" && sha256sum -c artifacts.sha256) > "$qb_results/artifacts_recheck.log"
run_log prior_artifacts_unchanged verify_prior_artifacts
qb_stage=complete
