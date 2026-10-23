#!/bin/bash -l
#SBATCH --job-name=fftw_alltoall
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --time=01:00:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/alltoall-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/alltoall-%j.err
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
. /work/dmarce1/fftw3_hpx_remaining_20261023/alltoall/common.sh
run_log prior_artifacts verify_prior_artifacts
printf '%s  %s\n' 73d8ee96ada747e806af2c220c99a85f92152cda73385bf4797d55a5a462fcd0 "$qb_mpi_exe" \
    42c8821d64faaf27411e1714fe05ed37d4feb4aa21fe79d4db6ec1b742f66496 "$qb_old_hpx_exe" | sha256sum -c -
cmp "$qb_bundle/source/benchmarks/matched_3d.cpp" "$qb_source/benchmarks/matched_3d.cpp"
cmp "$qb_bundle/source/benchmarks/matched_3d.cpp" "$qb_prior/matched_3d.cpp"
sha256sum "$qb_mpi_exe" "$qb_old_hpx_exe" "$qb_archive" "$qb_threads" "$qb_core" \
    "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_build/config.h" "$qb_base_build/config.h" \
    "$qb_prior/lean_hpx-flags.sh" "$qb_bundle/SHA256SUMS" "$qb_prior/artifacts.sha256" \
    "$qb_prior/fixed_inputs.sha256" "$qb_prior/reused_binaries.sha256" > "$qb_results/fixed_inputs.sha256"
for name in FINAL_STATUS artifacts.sha256 fixed_inputs.sha256 reused_binaries.sha256 archive_members.log lean_hpx-flags.sh; do
    cp "$qb_prior/$name" "$qb_results/reused_artifacts/1125925_$name"
done
{
    date -u; hostname; module -t list 2>&1; gcc --version; "$qb_mpi/bin/mpiexec" --version
    for name in PATH LD_LIBRARY_PATH HWLOC_COMPONENTS APEX_DISABLE OMPI_MCA_accelerator OMPI_MCA_pml OMPI_MCA_btl UCX_TLS OMPI_MPI_THREAD_LEVEL SLURM_JOB_ID SLURM_JOB_NODELIST; do printf '%s=%s\n' "$name" "${!name-}"; done
} > "$qb_results/metadata.txt"
scontrol show hostnames "$SLURM_JOB_NODELIST" > "$qb_results/nodes.txt"
run_log node_inventory srun --mpi=none --nodes=4 --ntasks=4 --ntasks-per-node=1 --cpus-per-task=1 --label sh -c 'hostname; uname -a; lscpu; numactl --show; cat /proc/meminfo'
qb_candidate=$qb_results/candidate_source
cp -a "$qb_source" "$qb_candidate"
cp "$qb_bundle/source/hpx/"* "$qb_candidate/hpx/"
cp "$qb_bundle/source/benchmarks/"* "$qb_candidate/benchmarks/"
run_log source_overlay python3 -I "$qb_bundle/check_source.py" "$qb_source" "$qb_candidate" "$qb_bundle/source"
qb_comm_member=$(ar t "$qb_archive" | awk '/(^|_la-)hpx-comm[.]o$/ {print}')
qb_transpose_member=$(ar t "$qb_archive" | awk '/(^|_la-)transpose-pairwise[.]o$/ {print}')
for member in "$qb_comm_member" "$qb_transpose_member"; do
    [ -n "$member" ] && [ "$(printf '%s\n' "$member" | wc -l)" -eq 1 ]
done
run_log compile_transpose gcc -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H \
    -I"$qb_build" -I"$qb_candidate" -I"$qb_candidate/hpx" -I"$qb_candidate/api" \
    -c "$qb_candidate/hpx/transpose-pairwise.c" -o "$qb_results/objects/$qb_transpose_member"
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    . "$qb_prior/lean_hpx-flags.sh"
    read -r -a qb_component_flags <<< "$HPX_CFLAGS"
    read -r -a qb_app_flags <<< "$HPX_APP_CFLAGS"
    read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
    run_log compile_bridge g++ -O3 -march=native -DHAVE_CONFIG_H "${qb_component_flags[@]}" -DNDEBUG \
        -I"$qb_build" -I"$qb_candidate" -I"$qb_candidate/api" -I"$qb_candidate/hpx" \
        -c "$qb_candidate/hpx/hpx-comm.cpp" -o "$qb_results/objects/$qb_comm_member"
    cp "$qb_archive" "$qb_results/objects/libfftw3_hpx.a"
    run_log replace_objects ar r "$qb_results/objects/libfftw3_hpx.a" \
        "$qb_results/objects/$qb_comm_member" "$qb_results/objects/$qb_transpose_member"
    run_log compile_driver g++ -O3 -march=native -DNDEBUG -std=c++20 -DFFTW_BENCH_HPX "${qb_app_flags[@]}" -DNDEBUG \
        -I"$qb_candidate/api" -I"$qb_candidate/hpx" "$qb_candidate/benchmarks/matched_3d.cpp" \
        "$qb_results/objects/libfftw3_hpx.a" "$qb_threads" "$qb_core" "${qb_app_libs[@]}" -lm -pthread -o "$qb_results/bin/hpx_candidate"
    run_log compile_comm_check g++ -O3 -march=native -std=c++20 "${qb_app_flags[@]}" \
        -I"$qb_build" -I"$qb_candidate/api" -I"$qb_candidate/hpx" -UNDEBUG \
        "$qb_candidate/hpx/hpx-comm-check.cpp" "$qb_results/objects/libfftw3_hpx.a" \
        "$qb_threads" "$qb_core" "${qb_app_libs[@]}" -lm -pthread -UNDEBUG -o "$qb_results/bin/hpx_comm_check"
    for label in hpx_candidate hpx_comm_check; do
        run_log "ldd_$label" ldd "$qb_results/bin/$label"
        run_log "dependencies_$label" python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/ldd_$label.log" "$qb_lean" "$qb_mpi"
    done
)
run_log archive_members python3 -I "$qb_bundle/check_members.py" "$qb_archive" "$qb_results/objects/libfftw3_hpx.a" "$qb_results/objects"
run_log mpi_ldd ldd "$qb_mpi_exe"
run_log mpi_dependencies python3 -I "$qb_bundle/check_mpi_ldd.py" "$qb_results/mpi_ldd.log" "$qb_mpi"
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    for mode in pairwise all_to_all; do
        run_log "communication_$mode" timeout --signal=TERM --kill-after=30s 180s "${qb_launcher[@]}" \
            /usr/bin/numactl --interleave=all env "FFTW_HPX_TRANSPOSE_EXCHANGE=$mode" \
            "$qb_results/bin/hpx_comm_check" "${qb_hpx_options[@]}"
        [ "$(grep -c '^communication check PASS$' "$qb_results/communication_$mode.log")" -eq 4 ]
    done
    for size in 32 64; do
        for mode in pairwise all_to_all; do
            run_hpx "small_${size}_$mode" "$mode" "--size=$size" --threads=64 --warmups=1 --samples=2
        done
    done
)
run_log correctness_gates python3 -I "$qb_bundle/check_results.py" "$qb_results" --gates-only
sha256sum "$qb_mpi_exe" "$qb_old_hpx_exe" > "$qb_results/reused_binaries.sha256"
(cd "$qb_results" && find bin objects candidate_source -type f -print0 | sort -z | xargs -0 sha256sum) > "$qb_results/artifacts.sha256"
{
    printf 'case\trole\texecutable\tworkers\texchange\tbackoff_cap_ms\n'
    printf 'mpi_start\tprimary\t%s\t64\tMPI_pairwise\tn/a\n' "$qb_mpi_exe"
    for label in pairwise all_to_all all_to_allrepeat pairwiserepeat; do
        mode=${label%repeat}
        printf 'hpx_%s\tprimary\t%s\t64\t%s\t10\n' "$label" "$qb_results/bin/hpx_candidate" "$mode"
    done
    printf 'mpi_end\tprimary\t%s\t64\tMPI_pairwise\tn/a\n' "$qb_mpi_exe"
} > "$qb_results/case_table.tsv"
run_log benchmark_mpi_start timeout --signal=TERM --kill-after=30s 900s "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    run_hpx benchmark_hpx_pairwise pairwise "${qb_options[@]}"
    run_hpx benchmark_hpx_all_to_all all_to_all "${qb_options[@]}"
    run_hpx benchmark_hpx_all_to_allrepeat all_to_all "${qb_options[@]}"
    run_hpx benchmark_hpx_pairwiserepeat pairwise "${qb_options[@]}"
)
run_log benchmark_mpi_end timeout --signal=TERM --kill-after=30s 900s "${qb_launcher[@]}" /usr/bin/numactl --interleave=all "$qb_mpi_exe" "${qb_options[@]}"
[ "${OMPI_MPI_THREAD_LEVEL+x}" = "$qb_inherited_mpi_thread_level_set" ]
[ "${OMPI_MPI_THREAD_LEVEL-}" = "$qb_inherited_mpi_thread_level" ]
run_log alltoall_checks python3 -I "$qb_bundle/check_results.py" "$qb_results"
run_log fixed_inputs_unchanged sha256sum -c "$qb_results/fixed_inputs.sha256"
run_log reused_binaries_unchanged sha256sum -c "$qb_results/reused_binaries.sha256"
run_log source_overlay_unchanged python3 -I "$qb_bundle/check_source.py" "$qb_source" "$qb_candidate" "$qb_bundle/source"
cmp "$qb_results/source_overlay.log" "$qb_results/source_overlay_unchanged.log"
qb_stage=artifacts_unchanged
(cd "$qb_results" && sha256sum -c artifacts.sha256) > "$qb_results/artifacts_recheck.log"
run_log prior_artifacts_unchanged verify_prior_artifacts
qb_stage=complete
