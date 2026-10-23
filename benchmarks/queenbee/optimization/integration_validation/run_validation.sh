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
phase=${1:?build, focused, or full}
precision=${2:?double, single, or long_double}
case "$precision" in double|single|long_double) ;; *) exit 2 ;; esac
case "$phase:$precision" in build:*|focused:*|full:double) ;; *) exit 2 ;; esac
validation_root=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$validation_root/../../.." && pwd)
out=$validation_root/$precision
mkdir -p "$out"
. "$repo/build/hpx_env.sh"
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
unset HPXRUN_NODES HPXRUN_ARGS
finish()
{
    local result=$?
    trap - EXIT
    printf 'exit_status=%s\nfinished_utc=%s\n' "$result" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"
    exit "$result"
}
trap finish EXIT
run_logged()
{
    local name=$1
    shift
    printf '%q ' "$@" > "$out/$name.command"
    printf '\n' >> "$out/$name.command"
    "$@" > "$out/$name.log" 2>&1
}
cd "$repo"
sha256sum -c "$validation_root/source_inputs.sha256" > "$out/${phase}_source_check.log"
if [ "$phase" = build ]; then
    run_logged build make -C "$repo/build/$precision" -j2
    {
        printf 'precision=%s\n' "$precision"
        g++ --version
        sed -n '/^CXXFLAGS = /p; /^HPX_CFLAGS = /p; /^HPX_LIBS = /p; /^HPX_APP_CFLAGS = /p; /^HPX_APP_LIBS = /p; /^HPXRUN = /p' "$repo/build/$precision/hpx/Makefile"
    } > "$out/environment.txt"
    sha256sum "$repo/build/$precision/config.h" "$repo/build/$precision/hpx/Makefile" > "$out/build_config.sha256"
    for program in hpx-bench hpx-comm-check hpx-message-check; do
        sha256sum "$repo/build/$precision/hpx/$program"
        if [ -f "$repo/build/$precision/hpx/.libs/$program" ]; then
            sha256sum "$repo/build/$precision/hpx/.libs/$program"
        fi
    done > "$out/binaries.sha256"
elif [ "$phase" = focused ]; then
    test "$(sed -n 's/^exit_status=//p' "$out/BUILD_STATUS")" = 0
    run_logged message timeout --kill-after=10s 60s "$repo/build/$precision/hpx/hpx-message-check"
    grep -q '^HPX_MESSAGE_CHECK pooled_receive PASS$' "$out/message.log"
    for localities in 1 3; do
        run_logged "comm_${localities}x2" timeout --kill-after=10s 180s \
            sh "$repo/hpx/hpx-run.sh" /home/dmarce1/local/hpx/Release/bin/hpxrun.py \
            "$localities" 2 "$repo/build/$precision/hpx/hpx-comm-check"
        test "$(grep -c '^communication check PASS' "$out/comm_${localities}x2.log")" = "$localities"
    done
else
    test "$(sed -n 's/^exit_status=//p' "$out/FOCUSED_STATUS")" = 0
    run_logged make_check timeout --kill-after=10s 3600s make -C "$repo/build/double" -j1 check
    grep -q '^HPX_MESSAGE_CHECK pooled_receive PASS$' "$out/make_check.log"
    grep -q '^HPX FFTW threaded transforms passed 10 tests, 3 localities, 2 threads each$' "$out/make_check.log"
fi
sha256sum -c "$validation_root/source_inputs.sha256" > "$out/${phase}_source_recheck.log"
printf '%s %s PASS\n' "$phase" "$precision"
