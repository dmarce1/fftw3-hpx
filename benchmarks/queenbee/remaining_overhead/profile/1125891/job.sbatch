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



. /work/dmarce1/fftw3_hpx_remaining_20261023/inputs_v3/common.sh
qb_previous=$qb_root/results/1125884
run_log verify_previous_fixed sha256sum -c "$qb_previous/fixed_inputs.sha256"
(cd "$qb_root" && sha256sum -c inputs_v2/SHA256SUMS) > "$qb_results/previous_input_verification.log"
run_log reuse_artifacts python3 -I "$qb_root/inputs_v3/reuse_artifacts.py" "$qb_previous" "$qb_results" "$qb_source" "$qb_root/inputs_v3"
run_log archive_members python3 -I "$qb_root/inputs_v3/check_members.py" "$qb_archive" "$qb_base_build/mpi/.libs/libfftw3_mpi.a" "$qb_base_build/threads/.libs/libfftw3_threads.a" "$qb_results/objects"
# The full member/digest gate above must succeed before any benchmark launch.
run_mpi mpi "$qb_mpi_exe"
run_hpx pooled_control "$qb_pool_exe"
run_hpx pool_release "$qb_results/bin/pool_release"
run_mpi mpi_profile "$qb_results/bin/mpi_profile"
run_hpx hpx_profile "$qb_results/bin/hpx_profile"
run_log profile_comparison python3 -I "$qb_source/benchmarks/summarize.py" "$qb_results/benchmark_mpi_profile.log" "$qb_results/benchmark_hpx_profile.log"
run_log reused_inputs_unchanged sha256sum -c "$qb_results/reused_inputs.sha256"
finish_checks
