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
name=${2:?direct_receive or pooled_receive}
precision=${3:?double or single or long_double}
case "$phase" in build|test) ;; *) exit 2;; esac
case "$name" in direct_receive|pooled_receive) ;; *) exit 2;; esac
case "$precision" in double) suffix=;; single) suffix=f;; long_double) suffix=l;; *) exit 2;; esac
repo=$(cd "$(dirname "$0")/../.." && pwd)
. "$repo/build/hpx_env.sh"
source_file=$repo/build/qb_optimize/$name/hpx-comm.cpp
original=$repo/build/$precision
out=$repo/build/qb_optimize/precision_validation/$name/$precision
base_archive=$original/hpx/.libs/libfftw3${suffix}_hpx.a
archive=$out/libfftw3${suffix}_hpx.a
serial=$original/.libs/libfftw3${suffix}.a
threaded=$original/threads/.libs/libfftw3${suffix}_threads.a
benchlib=$original/libbench2/libbench2.a
mkdir -p "$out"
exec > >(stdbuf -oL -eL tee "$out/$phase.log") 2>&1
exec 3> "$out/$phase.commands.log"
BASH_XTRACEFD=3
PS4='+ ${BASH_SOURCE}:${LINENO} ${PWD}: '
stage=setup
finish()
{
    local result=$1
    trap - EXIT
    set +e
    set +x
    printf 'exit_status=%s\nstage=%s\nfinished_utc=%s\n' "$result" "$stage" "$(date -u +%FT%TZ)" > "$out/${phase^^}_STATUS"
    exit "$result"
}
trap 'finish "$?"' EXIT
set -x
run_log()
{
    local label=$1
    shift
    stage=$label
    local started=$SECONDS
    printf 'START %s/%s %s %s\n' "$name" "$precision" "$label" "$(date -u +%FT%TZ)"
    printf '%q ' "$@" > "$out/$label.command"
    printf '\n' >> "$out/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$out/$label.log"
    printf '%s\tPASS\t%s\n' "$label" "$((SECONDS-started))" >> "$out/${phase}_results.tsv"
    printf 'PASS %s/%s %s %s\n' "$name" "$precision" "$label" "$(date -u +%FT%TZ)"
}
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
cd "$repo"
if [ "$phase" = build ]; then
    read -r -a component_flags <<< "$(pkg-config --cflags hpx_component)"
    read -r -a app_flags <<< "$(pkg-config --cflags hpx_application)"
    read -r -a app_libs <<< "$(pkg-config --libs hpx_application)"
    objects=("$original/hpx/hpx_bench-hpx-bench.o" "$original/hpx/hpx_bench-hpx-bench-main.o"
        "$original/hpx/hpx_bench-fftw-bench.o" "$original/hpx/hpx_bench-hook.o")
    sha256sum "$source_file" "$base_archive" "$original/config.h" \
        "$repo/hpx/hpx-comm.h" "$repo/hpx/hpx-comm-check.cpp" "$repo/tests/check.pl" \
        "$serial" "$threaded" "$benchlib" "${objects[@]}" > "$out/input.sha256"
    if [ "$precision" = double ]; then
        previous=$repo/build/qb_optimize/local_validation/$name
        run_log previous_inputs_unchanged sha256sum -c "$previous/input.sha256"
        run_log previous_outputs_unchanged sha256sum -c "$previous/output.sha256"
        cp "$previous/libfftw3_hpx.a" "$archive"
    else
        run_log compile_bridge g++ -g -O2 -DHAVE_CONFIG_H \
            "${component_flags[@]}" -I"$original" -I"$repo" -I"$repo/api" -I"$repo/hpx" \
            -c "$source_file" -o "$out/hpx-comm.o"
        cp "$base_archive" "$archive"
        run_log replace_bridge ar r "$archive" "$out/hpx-comm.o"
    fi
    stage=verify_archive
    python3 - "$base_archive" "$archive" <<'PY' | tee "$out/archive_members.json"
import hashlib,json,subprocess,sys

def members(path):
    names=subprocess.check_output(['ar','t',path],text=True).splitlines()
    assert len(names)==len(set(names))==32
    return names,{name:hashlib.sha256(subprocess.check_output(['ar','p',path,name])).hexdigest() for name in names}
old_names,old=members(sys.argv[1]);new_names,new=members(sys.argv[2])
assert old_names==new_names
changed=[name for name in old_names if old[name]!=new[name]]
assert changed==['hpx-comm.o'],changed
print(json.dumps(dict(changed=changed,member_count=len(new),before=old,after=new),indent=2))
PY
    run_log link_bench g++ -g -O2 "${objects[@]}" "$archive" "$threaded" "$serial" "$benchlib" \
        "${app_libs[@]}" -lm -pthread -o "$out/hpx-bench"
    run_log compile_comm_check g++ -g -O2 "${app_flags[@]}" \
        -I"$original" -I"$repo/api" -I"$repo/hpx" -UNDEBUG \
        "$repo/hpx/hpx-comm-check.cpp" "$archive" "$threaded" "$serial" \
        "${app_libs[@]}" -lm -pthread -UNDEBUG -o "$out/hpx-comm-check"
    sha256sum "$archive" "$out/hpx-bench" "$out/hpx-comm-check" > "$out/output.sha256"
else
    grep -q '^exit_status=0$' "$out/BUILD_STATUS"
    run_log input_unchanged sha256sum -c "$out/input.sha256"
    run_log output_unchanged sha256sum -c "$out/output.sha256"
    hpxrun=$(command -v hpxrun.py)
    run_log comm_1x2 timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 1 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_1x2.log")" -eq 1 ]
    run_log comm_3x2 timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 3 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_3x2.log")" -eq 3 ]
    for localities in 1 2 3 4; do
        launcher="sh \"$repo/hpx/hpx-run.sh\" \"$hpxrun\" $localities 1 \"$out/hpx-bench\""
        run_log "matrix_${localities}x1" timeout --kill-after=15s 600s perl -w "$repo/tests/check.pl" \
            --verbose --random --maxsize=10000 -c=10 --mpi "$launcher"
    done
    launcher="sh \"$repo/hpx/hpx-run.sh\" \"$hpxrun\" 3 2 \"$out/hpx-bench\""
    run_log matrix_3x2 timeout --kill-after=15s 600s perl -w "$repo/tests/check.pl" \
        --verbose --random --maxsize=10000 -c=10 --mpi --nthreads=2 "$launcher"
    run_log inputs_still_unchanged sha256sum -c "$out/input.sha256"
fi
stage=complete
