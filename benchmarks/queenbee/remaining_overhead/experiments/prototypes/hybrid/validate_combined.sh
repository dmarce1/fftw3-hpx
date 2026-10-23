#!/usr/bin/env bash
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# See the repository COPYING file for the complete license.
set -Eeuo pipefail
phase=${1:?build or test}
case "$phase" in build|test) ;; *) exit 2;; esac
repo=$(cd "$(dirname "$0")/../../.." && pwd)
. "$repo/build/hpx_env.sh"
out=$repo/build/qb_remaining/hybrid/validation/combined
mkdir -p "$out"
exec > >(stdbuf -oL -eL tee "$out/$phase.log") 2>&1
exec 3> "$out/$phase.commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
finish()
{
    local result=$1
    trap - EXIT
    set +e
    set +x
    printf 'exit_status=%s\nfinished_utc=%s\n' "$result" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"
    exit "$result"
}
trap 'finish "$?"' EXIT
set -x
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
cd "$repo"
if [ "$phase" = build ]; then
    read -r -a app_flags <<< "$(pkg-config --cflags hpx_application)"
    read -r -a app_libs <<< "$(pkg-config --libs hpx_application)"
    archives=()
    for precision in double single long_double; do
        case "$precision" in double) suffix=;; single) suffix=f;; long_double) suffix=l;; esac
        grep -q '^exit_status=0$' "$repo/build/qb_remaining/hybrid/validation/$precision/BUILD_STATUS"
        archives+=("$repo/build/qb_remaining/hybrid/validation/$precision/libfftw3${suffix}_hpx.a"
            "$repo/build/$precision/threads/.libs/libfftw3${suffix}_threads.a"
            "$repo/build/$precision/.libs/libfftw3${suffix}.a")
    done
    sha256sum "$repo/build/combined_precision_smoke.cpp" "${archives[@]}" > "$out/input.sha256"
    command=(g++ -g -O2 "${app_flags[@]}" -I"$repo/hpx" -I"$repo/api" -UNDEBUG
        "$repo/build/combined_precision_smoke.cpp" "${archives[@]}" "${app_libs[@]}" -lm -pthread
        -UNDEBUG -o "$out/combined_precision_smoke")
    printf '%q ' "${command[@]}" > "$out/build.command"
    printf '\n' >> "$out/build.command"
    "${command[@]}"
    sha256sum "$out/combined_precision_smoke" > "$out/output.sha256"
else
    grep -q '^exit_status=0$' "$out/BUILD_STATUS"
    sha256sum -c "$out/input.sha256"
    sha256sum -c "$out/output.sha256"
    command=(timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$(command -v hpxrun.py)" 3 2
        "$out/combined_precision_smoke")
    printf '%q ' "${command[@]}" > "$out/test.command"
    printf '\n' >> "$out/test.command"
    "${command[@]}" 2>&1 | tee "$out/runtime.log"
    grep -q '^combined double/single/long-double precision smoke PASS$' "$out/runtime.log"
    sha256sum -c "$out/input.sha256"
fi
