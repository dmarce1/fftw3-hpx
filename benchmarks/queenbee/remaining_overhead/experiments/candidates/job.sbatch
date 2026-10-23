#!/bin/bash -l
#SBATCH --job-name=fftw_remaining_candidates
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:45:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/candidates-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/candidates-%j.err
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



# Prepared only. Root owns review, staging, submission and all remote access.
# All builds execute sequentially in this allocation; no original artifact is changed.
. /work/dmarce1/fftw3_hpx_remaining_20261023/candidates/common.sh
qb_lean_root=$qb_root/lean_hpx
qb_lean=$qb_lean_root/install
qb_hwloc=/usr/local/packages/hwloc/2.9.1/7ka44tz
qb_boost=/usr/local/packages/boost/1.83.0/dbicuu5
qb_threads=$qb_base_build/threads/.libs/libfftw3_threads.a
qb_driver=$qb_source/benchmarks/matched_3d.cpp
cp -a "$qb_bundle/drivers" "$qb_results/drivers"
qb_original_ld=$LD_LIBRARY_PATH
qb_lean_ld=$qb_lean/lib64:$qb_lean/lib
IFS=: read -r -a qb_ld_entries <<< "$qb_original_ld"
for entry in "${qb_ld_entries[@]}"; do
    case "$entry" in "$qb_hpx/lib"|"$qb_hpx/lib64"|"$qb_lean/lib"|"$qb_lean/lib64"|'') ;;
        *) qb_lean_ld=$qb_lean_ld:$entry ;;
    esac
done
printf 'original_LD_LIBRARY_PATH=%s\nlean_LD_LIBRARY_PATH=%s\n' "$qb_original_ld" "$qb_lean_ld" > "$qb_results/library_environments.txt"
grep -q $'^status\tPASS$' "$qb_lean_root/results/1125886/FINAL_STATUS"
cp "$qb_lean_root/results/1125886/FINAL_STATUS" "$qb_results/reused_artifacts/lean_FINAL_STATUS"
cp "$qb_lean_root/results/1125886/installed-artifacts.sha256" "$qb_results/reused_artifacts/lean_installed-artifacts.sha256"
run_log lean_install_verified sha256sum -c "$qb_results/reused_artifacts/lean_installed-artifacts.sha256"

compile_comm_check()
{
    local label=$1 archive=$2 source=$qb_source/hpx/hpx-comm-check.cpp
    case "$label" in rendezvous|rendezvous_diagnostic) source=$qb_bundle/prototypes/$label/hpx-comm-check.cpp;; esac
    run_log "compile_comm_$label" g++ -O3 -march=native -std=c++20 "${qb_app_flags[@]}" \
        -I"$qb_build" -I"$qb_source/api" -I"$qb_source/hpx" -UNDEBUG \
        "$source" "$archive" "$qb_threads" "$qb_base_build/.libs/libfftw3.a" \
        "${qb_app_libs[@]}" -lm -pthread -UNDEBUG -o "$qb_results/bin/${label}_comm_check"
}
run_comm_check()
{
    local label=$1 executable=$2
    local options=() option
    for option in "${qb_hpx_options[@]}"; do
        if [ "$option" != --hpx:threads=64 ]; then options+=("$option"); fi
    done
    run_log "communication_$label" "${qb_launcher[@]}" /usr/bin/numactl --interleave=all \
        "$executable" "${options[@]}" --hpx:threads=2
    [ "$(grep -c '^communication check PASS$' "$qb_results/communication_$label.log")" -eq 4 ]
}

for label in pool_release parallel_copy hybrid hybrid_diagnostic rendezvous rendezvous_diagnostic; do
    compile_bridge "$label" "$qb_bundle/prototypes/$label/hpx-comm.cpp"
    driver=$qb_driver
    if [[ "$label" = *_diagnostic ]]; then driver=$qb_bundle/drivers/matched_3d_diagnostic.cpp; fi
    compile_hpx "$label" "$driver" "$qb_results/objects/$label/libfftw3_hpx.a" "$qb_threads"
    compile_comm_check "$label" "$qb_results/objects/$label/libfftw3_hpx.a"
    cp "$qb_bundle/prototypes/$label/hpx-comm.cpp" "$qb_results/objects/$label/source-hpx-comm.cpp"
done

# The subshell guarantees that lean flags and loader paths cannot leak into the
# original-HPX candidates, including if a compile or dependency check fails.
qb_stage=lean_metadata_and_build
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    run_log lean_metadata python3 -I "$qb_bundle/hpx_cmake_flags.py" "$qb_lean" "$qb_results/lean_metadata" \
        -DCMAKE_CXX_COMPILER=/usr/local/packages/compilers/gcc/13.2.0/bin/g++ \
        -DMPI_CXX_COMPILER="$qb_mpi/bin/mpicxx" -DMPI_HOME="$qb_mpi" \
        -DBoost_DIR="$qb_boost/lib/cmake/Boost-1.83.0" \
        -DHwloc_INCLUDE_DIR="$qb_hwloc/include" -DHwloc_LIBRARY="$qb_hwloc/lib/libhwloc.so"
    . "$qb_results/lean_metadata/hpx-flags.sh"
    read -r -a qb_component_flags <<< "$HPX_CFLAGS"
    read -r -a qb_app_flags <<< "$HPX_APP_CFLAGS"
    read -r -a qb_app_libs <<< "$HPX_APP_LIBS"
    compile_bridge lean_pool "$qb_bundle/prototypes/pool_release/hpx-comm.cpp"
    compile_hpx lean_pool "$qb_driver" "$qb_results/objects/lean_pool/libfftw3_hpx.a" "$qb_threads"
    compile_comm_check lean_pool "$qb_results/objects/lean_pool/libfftw3_hpx.a"
    cp "$qb_bundle/prototypes/pool_release/hpx-comm.cpp" "$qb_results/objects/lean_pool/source-hpx-comm.cpp"
    run_log lean_ldd ldd "$qb_results/bin/lean_pool"
    run_log lean_comm_ldd ldd "$qb_results/bin/lean_pool_comm_check"
    run_log lean_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_ldd.log" "$qb_lean" "$qb_mpi"
    run_log lean_comm_dependencies python3 -I "$qb_bundle/check_lean_ldd.py" "$qb_results/lean_comm_ldd.log" "$qb_lean" "$qb_mpi"
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_log archive_members python3 -I "$qb_bundle/check_members.py" "$qb_archive" "$qb_results/objects"
for label in pool_release parallel_copy hybrid hybrid_diagnostic rendezvous rendezvous_diagnostic; do
    run_log "ldd_$label" ldd "$qb_results/bin/$label"
    run_comm_check "$label" "$qb_results/bin/${label}_comm_check"
done
qb_stage=communication_lean_pool
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    run_comm_check lean_pool "$qb_results/bin/lean_pool_comm_check"
)

# The first seven are primary timings. Diagnostic output is analyzed separately.
run_mpi mpi "$qb_mpi_exe"
run_hpx pooled_current "$qb_pool_exe"
run_hpx pool_release "$qb_results/bin/pool_release"
qb_stage=benchmark_lean_pool
(
    export LD_LIBRARY_PATH="$qb_lean_ld"
    run_hpx lean_pool "$qb_results/bin/lean_pool"
)
[ "$LD_LIBRARY_PATH" = "$qb_original_ld" ]
run_hpx parallel_copy "$qb_results/bin/parallel_copy"
run_hpx hybrid "$qb_results/bin/hybrid"
run_hpx rendezvous "$qb_results/bin/rendezvous"
run_hpx hybrid_diagnostic "$qb_results/bin/hybrid_diagnostic"
run_hpx rendezvous_diagnostic "$qb_results/bin/rendezvous_diagnostic"
run_log candidate_checks python3 -I "$qb_bundle/check_results.py" "$qb_results"
run_log lean_install_unchanged sha256sum -c "$qb_results/reused_artifacts/lean_installed-artifacts.sha256"
finish_checks
