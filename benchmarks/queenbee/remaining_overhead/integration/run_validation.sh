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
phase=${1:?build or focused}
precision=${2:?double, single, or long_double}
case "$precision" in double) suffix=;; single) suffix=f;; long_double) suffix=l;; *) exit 2 ;; esac
case "$phase" in build|focused) ;; *) exit 2 ;; esac
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
sha256sum -c "$validation_root/protected_archives.sha256" > "$out/${phase}_protected_check.log"
if [ "$phase" = build ]; then
    run_logged build_library make -C "$repo/build/$precision/hpx" -j1 \
        CXXFLAGS='-O3 -DNDEBUG' "libfftw3${suffix}_hpx.la"
    run_logged build_checks make -C "$repo/build/$precision/hpx" -j1 \
        CXXFLAGS='-O3 -UNDEBUG' hpx-message-check hpx-comm-check
    {
        printf 'precision=%s\n' "$precision"
        g++ --version
        sed -n '/^CXXFLAGS = /p; /^HPX_CFLAGS = /p; /^HPX_LIBS = /p; /^HPX_APP_CFLAGS = /p; /^HPX_APP_LIBS = /p; /^HPXRUN = /p' "$repo/build/$precision/hpx/Makefile"
    } > "$out/environment.txt"
    sha256sum "$repo/build/$precision/config.h" "$repo/build/$precision/hpx/Makefile" > "$out/build_config.sha256"
    for program in hpx-comm-check hpx-message-check; do
        sha256sum "$repo/build/$precision/hpx/$program"
        if [ -f "$repo/build/$precision/hpx/.libs/$program" ]; then
            sha256sum "$repo/build/$precision/hpx/.libs/$program"
        fi
    done > "$out/binaries.sha256"
else
    test "$(sed -n 's/^exit_status=//p' "$out/BUILD_STATUS")" = 0
    run_logged message timeout --kill-after=10s 60s "$repo/build/$precision/hpx/hpx-message-check"
    grep -q '^HPX_MESSAGE_CHECK rendezvous PASS$' "$out/message.log"
    for localities in 1 3; do
        run_logged "comm_${localities}x2" timeout --kill-after=10s 180s \
            sh "$repo/hpx/hpx-run.sh" /home/dmarce1/local/hpx/Release/bin/hpxrun.py \
            "$localities" 2 "$repo/build/$precision/hpx/hpx-comm-check"
        test "$(grep -c '^communication check PASS' "$out/comm_${localities}x2.log")" = "$localities"
    done
fi
sha256sum -c "$validation_root/source_inputs.sha256" > "$out/${phase}_source_recheck.log"
sha256sum -c "$validation_root/protected_archives.sha256" > "$out/${phase}_protected_recheck.log"
printf '%s %s PASS\n' "$phase" "$precision"
