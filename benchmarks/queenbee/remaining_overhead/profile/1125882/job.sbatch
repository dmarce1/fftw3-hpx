#!/bin/bash -l
#SBATCH --job-name=fftw_remaining_profile
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=4
#SBATCH --ntasks=4
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=64
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/profile-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/profile-%j.err
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



. /work/dmarce1/fftw3_hpx_remaining_20261023/inputs/common.sh
qb_diag=$qb_results/diagnostic_source
cp -a "$qb_source" "$qb_diag"
run_log instrument python3 -I "$qb_root/inputs/profile/instrument.py" "$qb_diag" --threads --pairwise
cp "$qb_diag/remaining_profile_manifest.json" "$qb_results/remaining_profile_manifest.json"
compile_bridge pool_release "$qb_source/hpx/hpx-comm.cpp"
compile_hpx pool_release "$qb_source/benchmarks/matched_3d.cpp" "$qb_results/objects/pool_release/libfftw3_hpx.a" "$qb_base_build/threads/.libs/libfftw3_threads.a"
mkdir -p "$qb_results/objects/diagnostic" "$qb_results/objects/mpi_profile" "$qb_results/objects/hpx_profile" "$qb_results/objects/threads_profile"
run_log compile_profile g++ -O3 -march=native -DNDEBUG -std=c++20 -pthread -I"$qb_diag/benchmarks" -c "$qb_diag/benchmarks/remaining_profile.cpp" -o "$qb_results/objects/diagnostic/remaining_profile.o"
run_log compile_mpi_interposer "$qb_mpi/bin/mpicxx" -O3 -march=native -DNDEBUG -std=c++20 -pthread -I"$qb_diag/benchmarks" -c "$qb_diag/benchmarks/remaining_mpi_profile.cpp" -o "$qb_results/objects/diagnostic/remaining_mpi_profile.o"
run_log compile_threads_profile gcc -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_base_build" -I"$qb_diag" -I"$qb_diag/threads" -I"$qb_diag/api" -c "$qb_diag/threads/threads.c" -o "$qb_results/objects/threads_profile/threads.o"
cp "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_results/objects/threads_profile/libfftw3_threads.a"
run_log replace_threads ar r "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_results/objects/threads_profile/threads.o"
run_log compile_mpi_pairwise "$qb_mpi/bin/mpicc" -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_base_build" -I"$qb_diag" -I"$qb_diag/mpi" -I"$qb_diag/api" -c "$qb_diag/mpi/transpose-pairwise.c" -o "$qb_results/objects/mpi_profile/transpose-pairwise.o"
cp "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_results/objects/mpi_profile/libfftw3_mpi.a"
run_log replace_mpi_pairwise ar r "$qb_results/objects/mpi_profile/libfftw3_mpi.a" "$qb_results/objects/mpi_profile/transpose-pairwise.o"
run_log compile_hpx_pairwise gcc -O3 -march=native -DNDEBUG -DHAVE_CONFIG_H -I"$qb_build" -I"$qb_diag" -I"$qb_diag/hpx" -I"$qb_diag/api" -c "$qb_diag/hpx/transpose-pairwise.c" -o "$qb_results/objects/hpx_profile/transpose-pairwise.o"
compile_bridge hpx_profile "$qb_diag/hpx/hpx-comm.cpp"
run_log replace_hpx_pairwise ar r "$qb_results/objects/hpx_profile/libfftw3_hpx.a" "$qb_results/objects/hpx_profile/transpose-pairwise.o"
compile_hpx hpx_profile "$qb_diag/benchmarks/matched_3d.cpp" "$qb_results/objects/hpx_profile/libfftw3_hpx.a" "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_results/objects/diagnostic/remaining_profile.o"
run_log compile_mpi_profile "$qb_mpi/bin/mpicxx" -O3 -march=native -DNDEBUG -std=c++20 -I"$qb_diag/api" -I"$qb_diag/mpi" -I"$qb_diag/benchmarks" "$qb_diag/benchmarks/matched_3d.cpp" "$qb_results/objects/diagnostic/remaining_profile.o" "$qb_results/objects/diagnostic/remaining_mpi_profile.o" "$qb_results/objects/mpi_profile/libfftw3_mpi.a" "$qb_results/objects/threads_profile/libfftw3_threads.a" "$qb_base_build/.libs/libfftw3.a" -lm -pthread -o "$qb_results/bin/mpi_profile"
run_log archive_members python3 -I "$qb_root/inputs/check_members.py" "$qb_archive" "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_results/objects"
run_mpi mpi "$qb_mpi_exe"
run_hpx pooled_control "$qb_pool_exe"
run_hpx pool_release "$qb_results/bin/pool_release"
run_mpi mpi_profile "$qb_results/bin/mpi_profile"
run_hpx hpx_profile "$qb_results/bin/hpx_profile"
run_log profile_comparison python3 -I "$qb_source/benchmarks/summarize.py" "$qb_results/benchmark_mpi_profile.log" "$qb_results/benchmark_hpx_profile.log"
finish_checks
