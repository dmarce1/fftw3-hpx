#!/usr/bin/env bash
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
. build/hpx_env.sh
out=$PWD/build/qb_remaining/rendezvous_profile/compile_check
src=$PWD/build/qb_remaining/rendezvous_profile/transform_check
mkdir -p "$out"
read -r -a hpxflags <<< "$(sed -n 's/^HPX_CFLAGS = //p' build/double/hpx/Makefile)"
read -r -a appflags <<< "$(sed -n 's/^HPX_APP_CFLAGS = //p' build/double/hpx/Makefile)"
run()
{
    local name=$1
    shift
    printf '%q ' "$@" > "$out/$name.command"
    printf '\n' >> "$out/$name.command"
    "$@" > "$out/$name.log" 2>&1
    printf '%s PASS\n' "$name"
}
if [ "$1" = bridge ]; then
    run bridge g++ -O3 -DNDEBUG -DHAVE_CONFIG_H "${hpxflags[@]}" -Ibuild/double -Iapi -Ihpx -I. -c "$src/hpx/hpx-comm.cpp" -o "$out/hpx-comm.o"
else
    run common g++ -O3 -DNDEBUG -pthread -std=c++20 -I"$src/benchmarks" -c "$src/benchmarks/remaining_profile.cpp" -o "$out/remaining_profile.o"
    run mpi_interpose mpicxx -O3 -DNDEBUG -pthread -std=c++20 -I"$src/benchmarks" -c "$src/benchmarks/remaining_mpi_profile.cpp" -o "$out/remaining_mpi_profile.o"
    run threads gcc -O3 -DNDEBUG -DHAVE_CONFIG_H -Ibuild/double -I. -Ithreads -c "$src/threads/threads.c" -o "$out/threads.o"
    run hpx_pairwise gcc -O3 -DNDEBUG -DHAVE_CONFIG_H -Ibuild/double -I. -Iapi -Ihpx -c "$src/hpx/transpose-pairwise.c" -o "$out/hpx-transpose-pairwise.o"
    run mpi_pairwise mpicc -O3 -DNDEBUG -DHAVE_CONFIG_H -Ibuild/double -I. -Iapi -Impi -c "$src/mpi/transpose-pairwise.c" -o "$out/mpi-transpose-pairwise.o"
    run mpi_driver mpicxx -O3 -DNDEBUG -pthread -std=c++20 -Iapi -Impi -c "$src/benchmarks/matched_3d.cpp" -o "$out/mpi-driver.o"
    run hpx_driver g++ -O3 -DNDEBUG -DFFTW_BENCH_HPX "${appflags[@]}" -Iapi -Ihpx -c "$src/benchmarks/matched_3d.cpp" -o "$out/hpx-driver.o"
fi
