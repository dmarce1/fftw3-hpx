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
phase=${1:?build or test}
name=hybrid
case "$phase:$name" in
    build:hybrid|test:hybrid) ;;
    *) exit 2 ;;
esac
unit_root=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$unit_root/../../.." && pwd)
out=$unit_root/validation/units
mkdir -p "$out"
. "$repo/build/hpx_env.sh"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
finish()
{
    local result=$?
    trap - EXIT
    printf 'exit_status=%s\nfinished_utc=%s\n' "$result" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"
    exit "$result"
}
trap finish EXIT
cd "$repo"
if [ "$phase" = build ]; then
    read -r -a compile_flags <<< "$(pkg-config --cflags hpx_component)"
    read -r -a component_libs <<< "$(pkg-config --libs hpx_component)"
    link_flags=()
    for flag in "${component_libs[@]}"; do
        if [ "$flag" != -shared ]; then
            link_flags+=("$flag")
        fi
    done
    sha256sum "$unit_root/hybrid_units.cpp" "$unit_root/archive_helpers.hpp" \
        "$unit_root/validate_units.sh" "$unit_root/hpx-comm.cpp" "$unit_root/hpx-comm-diagnostic.cpp" "$unit_root/receive-diagnostics.hpp" \
        "$repo/build/double/config.h" "$repo/hpx/hpx-comm.h" \
        "$repo/hpx/fftw3-hpx.h" "$repo/build/hpx_env.sh" > "$out/input.sha256"
    command=(g++ -g -O2 -DHAVE_CONFIG_H -UNDEBUG "${compile_flags[@]}"
        -I"$repo/build/double" -I"$repo" -I"$repo/api" -I"$repo/hpx"
        "$unit_root/hybrid_units.cpp" "${link_flags[@]}" -lm -pthread -UNDEBUG
        -o "$out/${name}_units")
    printf '%q ' "${command[@]}" > "$out/build.command"
    printf '\n' >> "$out/build.command"
    "${command[@]}" 2>&1 | tee "$out/build.log"
    sha256sum "$out/${name}_units" > "$out/output.sha256"
    {
        printf 'PKG_CONFIG_PATH=%s\nLD_LIBRARY_PATH=%s\n' "$PKG_CONFIG_PATH" "$LD_LIBRARY_PATH"
        g++ --version
        pkg-config --modversion hpx_component
    } > "$out/environment.txt"
else
    test "$(sed -n 's/^exit_status=//p' "$out/BUILD_STATUS")" = 0
    sha256sum -c "$out/input.sha256" > "$out/input_check.log"
    command=(timeout --kill-after=5s 45s "$out/${name}_units")
    printf '%q ' "${command[@]}" > "$out/test.command"
    printf '\n' >> "$out/test.command"
    "${command[@]}" 2>&1 | tee "$out/test.log"
    sha256sum -c "$out/input.sha256" > "$out/input_recheck.log"
fi
