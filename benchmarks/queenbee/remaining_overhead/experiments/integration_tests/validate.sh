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
variant=${1:?hybrid or rendezvous}
precision=${2:-double}
case "$variant" in hybrid|rendezvous) ;; *) exit 2 ;; esac
case "$precision" in double|single|long_double) ;; *) exit 2 ;; esac
unit_root=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$unit_root/../../.." && pwd)
candidate=$repo/build/qb_remaining/$variant
out=$unit_root/validation/$variant/$precision
mkdir -p "$out"
. "$repo/build/hpx_env.sh"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
finish()
{
    local result=$?
    trap - EXIT
    printf 'exit_status=%s\nfinished_utc=%s\n' "$result" "$(date -u +%FT%TZ)" > "$out/STATUS"
    exit "$result"
}
trap finish EXIT
cd "$repo"
read -r -a compile_flags <<< "$(pkg-config --cflags hpx_component)"
read -r -a component_libs <<< "$(pkg-config --libs hpx_component)"
link_flags=()
for flag in "${component_libs[@]}"; do
    if [ "$flag" != -shared ]; then
        link_flags+=("$flag")
    fi
done
sha256sum "$unit_root/$variant/hpx-message-check.cpp" \
    "$unit_root/validate.sh" "$candidate/hpx-comm.cpp" \
    "$repo/build/$precision/config.h" "$repo/hpx/hpx-comm.h" \
    "$repo/hpx/fftw3-hpx.h" "$repo/hpx/hpx-message-check.hpp" \
    "$repo/build/hpx_env.sh" > "$out/input.sha256"
# The quoted source include resolves through this candidate directory first.
# Ordinary main uses component libraries without -shared or HPX application main.
# No FFTW archive is linked, so the bridge appears exactly once.
command=(g++ -O3 -DHAVE_CONFIG_H "${compile_flags[@]}"
    -I"$repo/build/$precision" -I"$candidate" -I"$repo" -I"$repo/api" -I"$repo/hpx"
    "$unit_root/$variant/hpx-message-check.cpp" "${link_flags[@]}" -lm -pthread -UNDEBUG
    -o "$out/hpx-message-check")
printf '%q ' "${command[@]}" > "$out/build.command"
printf '\n' >> "$out/build.command"
"${command[@]}" > "$out/build.log" 2>&1
sha256sum "$out/hpx-message-check" > "$out/output.sha256"
{
    printf 'PKG_CONFIG_PATH=%s\nLD_LIBRARY_PATH=%s\n' "$PKG_CONFIG_PATH" "$LD_LIBRARY_PATH"
    g++ --version
    pkg-config --modversion hpx_component
} > "$out/environment.txt"
sha256sum -c "$out/input.sha256" > "$out/input_check.log"
command=(timeout --kill-after=5s 45s "$out/hpx-message-check")
printf '%q ' "${command[@]}" > "$out/test.command"
printf '\n' >> "$out/test.command"
"${command[@]}" > "$out/test.log" 2>&1
sha256sum -c "$out/input.sha256" > "$out/input_recheck.log"
cat "$out/test.log"
