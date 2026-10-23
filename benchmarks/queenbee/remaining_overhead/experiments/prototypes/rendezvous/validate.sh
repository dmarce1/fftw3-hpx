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
phase=${1:?bridge or units or link or runtime}
repo=$(cd "$(dirname "$0")/../../.." && pwd)
root=$repo/build/qb_remaining/rendezvous
out=$root/validation
mkdir -p "$out"
. "$repo/build/hpx_env.sh"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
cd "$repo"
exec > >(stdbuf -oL -eL tee "$out/$phase.log") 2>&1
stage=setup
finish()
{
    local result=$?
    trap - EXIT
    printf 'exit_status=%s\nstage=%s\nfinished_utc=%s\n' "$result" "$stage" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"
    exit "$result"
}
trap finish EXIT
run()
{
    local label=$1
    shift
    stage=$label
    printf '%q ' "$@" > "$out/$label.command"
    printf '\n' >> "$out/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$out/$label.log"
    printf '%s PASS\n' "$label"
}
read -r -a component_flags <<< "$(pkg-config --cflags hpx_component)"
read -r -a component_libs <<< "$(pkg-config --libs hpx_component)"
read -r -a app_flags <<< "$(pkg-config --cflags hpx_application)"
read -r -a app_libs <<< "$(pkg-config --libs hpx_application)"
case "$phase" in
bridge)
    sha256sum "$root/hpx-comm.cpp" "$root/hpx-comm-check.cpp" \
        "$repo/hpx/hpx-comm.cpp" "$repo/hpx/hpx-comm.h" "$repo/benchmarks/matched_3d.cpp" \
        "$repo/build/double/hpx/.libs/libfftw3_hpx.a" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" "$repo/build/double/.libs/libfftw3.a" > "$out/inputs.sha256"
    run compile_bridge g++ -O3 -DNDEBUG -DHAVE_CONFIG_H "${component_flags[@]}" \
        -Ibuild/double -I. -Iapi -Ihpx -c "$root/hpx-comm.cpp" -o "$out/hpx-comm.o"
    cp build/double/hpx/.libs/libfftw3_hpx.a "$out/libfftw3_hpx.a"
    run replace_bridge ar r "$out/libfftw3_hpx.a" "$out/hpx-comm.o"
    python3 - "$repo/build/double/hpx/.libs/libfftw3_hpx.a" "$out/libfftw3_hpx.a" > "$out/archive_members.json" <<'PYCODE'
import hashlib,json,subprocess,sys

def members(path):
    names=subprocess.check_output(['ar','t',path],universal_newlines=True).splitlines()
    assert len(names)==len(set(names))==32
    return names,{name:hashlib.sha256(subprocess.check_output(['ar','p',path,name])).hexdigest() for name in names}
oldnames,old=members(sys.argv[1]);newnames,new=members(sys.argv[2])
assert oldnames==newnames
changed=[name for name in old if old[name]!=new[name]]
assert changed==['hpx-comm.o'],changed
print(json.dumps({'changed':changed,'member_count':32,'before':old,'after':new},indent=2))
PYCODE
    ;;
units)
    link_flags=()
    for flag in "${component_libs[@]}"; do
        if [ "$flag" != -shared ]; then
            link_flags+=("$flag")
        fi
    done
    run compile_units g++ -O2 -DHAVE_CONFIG_H "${component_flags[@]}" \
        -Ibuild/double -I. -Iapi -Ihpx -UNDEBUG "$root/rendezvous_units.cpp" \
        "${link_flags[@]}" -lm -pthread -UNDEBUG -o "$out/rendezvous_units"
    run units_check timeout --kill-after=5s 45s "$out/rendezvous_units"
    ;;
link)
    grep -q '^exit_status=0$' "$out/BRIDGE_STATUS"
    run compile_comm g++ -O2 "${app_flags[@]}" -Ibuild/double -Iapi -Ihpx -UNDEBUG \
        "$root/hpx-comm-check.cpp" "$out/libfftw3_hpx.a" \
        build/double/threads/.libs/libfftw3_threads.a build/double/.libs/libfftw3.a \
        "${app_libs[@]}" -lm -pthread -UNDEBUG -o "$out/hpx-comm-check"
    run compile_matched g++ -O3 -DNDEBUG "${app_flags[@]}" -DFFTW_BENCH_HPX -Iapi -Ihpx \
        benchmarks/matched_3d.cpp "$out/libfftw3_hpx.a" \
        build/double/threads/.libs/libfftw3_threads.a build/double/.libs/libfftw3.a \
        "${app_libs[@]}" -lm -pthread -o "$out/matched_3d"
    ;;
runtime)
    grep -q '^exit_status=0$' "$out/LINK_STATUS"
    hpxrun=$(command -v hpxrun.py)
    run comm_1x2 timeout --kill-after=10s 180s sh hpx/hpx-run.sh "$hpxrun" 1 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_1x2.log")" -eq 1 ]
    run comm_3x2 timeout --kill-after=10s 180s sh hpx/hpx-run.sh "$hpxrun" 3 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_3x2.log")" -eq 3 ]
    run matched_3x2 timeout --kill-after=15s 360s sh hpx/hpx-run.sh "$hpxrun" 3 2 "$out/matched_3d" \
        --size=128 --threads=2 --warmups=2 --samples=7
    run inputs_unchanged sha256sum -c "$out/inputs.sha256"
    ;;
*) exit 2;;
esac
stage=complete
