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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

set -Eeuo pipefail
phase=${1:?build or test}
repo=$(cd "$(dirname "$0")/../../.." && pwd)
source_dir=$repo/build/qb_remaining/parallel_copy
out=$source_dir/validation
mkdir -p "$out"
. "$repo/build/hpx_env.sh"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
exec > >(stdbuf -oL -eL tee "$out/$phase.log") 2>&1
trap 'result=$?; printf "exit_status=%s\nfinished_utc=%s\n" "$result" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"; exit "$result"' EXIT
run_log() {
    local label=$1
    shift
    printf '%q ' "$@" > "$out/$label.command"
    printf '\n' >> "$out/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$out/$label.log"
}
cd "$repo"
if [ "$phase" = build ]; then
    read -r -a component_flags <<< "$(pkg-config --cflags hpx_component)"
    read -r -a app_flags <<< "$(pkg-config --cflags hpx_application)"
    read -r -a app_libs <<< "$(pkg-config --libs hpx_application)"
    sha256sum "$source_dir/hpx-comm.cpp" "$source_dir/copy-check.cpp" "$repo/hpx/hpx-comm-check.cpp" \
        "$repo/benchmarks/matched_3d.cpp" "$repo/build/double/config.h" \
        "$repo/build/double/hpx/.libs/libfftw3_hpx.a" "$repo/build/double/threads/.libs/libfftw3_threads.a" \
        "$repo/build/double/.libs/libfftw3.a" > "$out/input.sha256"
    run_log compile_bridge g++ -O3 -DNDEBUG -DHAVE_CONFIG_H "${component_flags[@]}" \
        -I"$repo/build/double" -I"$repo" -I"$repo/api" -I"$repo/hpx" \
        -c "$source_dir/hpx-comm.cpp" -o "$out/hpx-comm.o"
    cp "$repo/build/double/hpx/.libs/libfftw3_hpx.a" "$out/libfftw3_hpx.a"
    run_log replace_bridge ar r "$out/libfftw3_hpx.a" "$out/hpx-comm.o"
    run_log compile_copy_check g++ -O3 -DNDEBUG "${app_flags[@]}" \
        -I"$repo/build/double" -I"$repo/api" -I"$repo/hpx" \
        "$source_dir/copy-check.cpp" "${app_libs[@]}" -lm -pthread -o "$out/copy-check"
    run_log compile_comm_check g++ -O3 "${app_flags[@]}" -UNDEBUG \
        -I"$repo/build/double" -I"$repo/api" -I"$repo/hpx" \
        "$repo/hpx/hpx-comm-check.cpp" "$out/libfftw3_hpx.a" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" "$repo/build/double/.libs/libfftw3.a" \
        "${app_libs[@]}" -lm -pthread -o "$out/hpx-comm-check"
    run_log compile_matched g++ -O3 -DNDEBUG "${app_flags[@]}" -DFFTW_BENCH_HPX \
        -I"$repo/api" -I"$repo/hpx" "$repo/benchmarks/matched_3d.cpp" "$out/libfftw3_hpx.a" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" "$repo/build/double/.libs/libfftw3.a" \
        "${app_libs[@]}" -lm -pthread -o "$out/matched_3d"
    sha256sum "$out/libfftw3_hpx.a" "$out/hpx-comm-check" "$out/copy-check" "$out/matched_3d" > "$out/output.sha256"
elif [ "$phase" = test ]; then
    grep -q '^exit_status=0$' "$out/BUILD_STATUS"
    run_log inputs_before sha256sum -c "$out/input.sha256"
    hpxrun=$(command -v hpxrun.py)
    run_log copy_1x1 timeout --kill-after=10s 120s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 1 1 "$out/copy-check"
    run_log copy_1x4 timeout --kill-after=10s 120s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 1 4 "$out/copy-check"
    run_log comm_1x2 timeout --kill-after=10s 120s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 1 2 "$out/hpx-comm-check"
    run_log comm_2x2 timeout --kill-after=10s 120s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 2 2 "$out/hpx-comm-check"
    run_log matched_2x2 timeout --kill-after=10s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 2 2 "$out/matched_3d" \
        '--hpx:ini=hpx.parcel.mpi.enable!=0' '--hpx:ini=hpx.parcel.tcp.enable!=1' \
        '--hpx:ini=hpx.parcel.bootstrap!=tcp' --size=256 --threads=2 --warmups=1 --samples=3
    run_log inputs_after sha256sum -c "$out/input.sha256"
else
    exit 2
fi
