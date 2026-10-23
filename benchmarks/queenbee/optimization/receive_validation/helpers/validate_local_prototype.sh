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
case "$phase:$name" in
    build:direct_receive|build:pooled_receive|test:direct_receive|test:pooled_receive) ;;
    *) exit 2 ;;
esac
repo=$(cd "$(dirname "$0")/../.." && pwd)
. "$repo/build/hpx_env.sh"
source_file=$repo/build/qb_optimize/$name/hpx-comm.cpp
out=$repo/build/qb_optimize/local_validation/$name
base_archive=$repo/build/double/hpx/.libs/libfftw3_hpx.a
archive=$out/libfftw3_hpx.a
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
    printf 'START %s %s\n' "$label" "$(date -u +%FT%TZ)"
    printf '%q ' "$@" > "$out/$label.command"
    printf '\n' >> "$out/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$out/$label.log"
    printf 'PASS %s %s\n' "$label" "$(date -u +%FT%TZ)"
}
export APEX_DISABLE=1
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
cd "$repo"
if [ "$phase" = build ]; then
    read -r -a component_flags <<< "$(pkg-config --cflags hpx_component)"
    read -r -a app_flags <<< "$(pkg-config --cflags hpx_application)"
    read -r -a app_libs <<< "$(pkg-config --libs hpx_application)"
    sha256sum "$source_file" "$base_archive" "$repo/build/double/config.h" \
        "$repo/hpx/hpx-comm.h" "$repo/hpx/hpx-comm-check.cpp" \
        "$repo/benchmarks/matched_3d.cpp" "$repo/build/double/.libs/libfftw3.a" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" > "$out/input.sha256"
    run_log compile_bridge g++ -g -O2 -DHAVE_CONFIG_H \
        "${component_flags[@]}" -I"$repo/build/double" -I"$repo" -I"$repo/api" -I"$repo/hpx" \
        -c "$source_file" -o "$out/hpx-comm.o"
    cp "$base_archive" "$archive"
    run_log replace_bridge ar r "$archive" "$out/hpx-comm.o"
    python3 - "$base_archive" "$archive" <<'PY' | tee "$out/archive_members.json"
import hashlib, json, subprocess, sys

def members(path):
    names=subprocess.check_output(['ar','t',path],text=True).splitlines()
    assert len(names)==len(set(names))
    return names,{name:hashlib.sha256(subprocess.check_output(['ar','p',path,name])).hexdigest() for name in names}
old_names,old=members(sys.argv[1]);new_names,new=members(sys.argv[2])
assert old_names==new_names
changed=[name for name in old_names if old[name]!=new[name]]
assert changed==['hpx-comm.o'],changed
print(json.dumps(dict(changed=changed,member_count=len(new),members=new),indent=2))
PY
    run_log compile_comm_check g++ -g -O2 "${app_flags[@]}" -UNDEBUG \
        -I"$repo/build/double" -I"$repo/api" -I"$repo/hpx" \
        "$repo/hpx/hpx-comm-check.cpp" "$archive" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" "$repo/build/double/.libs/libfftw3.a" \
        "${app_libs[@]}" -lm -pthread -o "$out/hpx-comm-check"
    run_log compile_matched g++ -g -O2 "${app_flags[@]}" -DFFTW_BENCH_HPX \
        -I"$repo/api" -I"$repo/hpx" "$repo/benchmarks/matched_3d.cpp" "$archive" \
        "$repo/build/double/threads/.libs/libfftw3_threads.a" "$repo/build/double/.libs/libfftw3.a" \
        "${app_libs[@]}" -lm -pthread -o "$out/matched_3d"
    sha256sum "$archive" "$out/hpx-comm-check" "$out/matched_3d" > "$out/output.sha256"
else
    grep -q '^exit_status=0$' "$out/BUILD_STATUS"
    run_log input_unchanged sha256sum -c "$out/input.sha256"
    hpxrun=$(command -v hpxrun.py)
    run_log comm_1x2 timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 1 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_1x2.log")" -eq 1 ]
    run_log comm_3x2 timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 3 2 "$out/hpx-comm-check"
    [ "$(grep -c '^communication check PASS$' "$out/comm_3x2.log")" -eq 3 ]
    run_log matched_4x2 timeout --kill-after=15s 180s sh "$repo/hpx/hpx-run.sh" "$hpxrun" 4 2 "$out/matched_3d" \
        '--hpx:ini=hpx.parcel.mpi.enable!=0' '--hpx:ini=hpx.parcel.tcp.enable!=1' \
        '--hpx:ini=hpx.parcel.bootstrap!=tcp' --size=64 --threads=2 --warmups=2 --samples=7
    python3 - "$out/matched_4x2.log" <<'PY' | tee "$out/numerical_validation.json"
from pathlib import Path
import json,math,statistics,sys
text=Path(sys.argv[1]).read_text()
def rows(prefix):
    return [dict(part.split('=',1) for part in line.split()[1:]) for line in text.splitlines() if line.startswith(prefix+' ')]
cfg,=rows('CONFIG');result,=rows('RESULT');samples=rows('SAMPLE');checks=rows('CHECK')
assert all(cfg[key]==value for key,value in dict(backend='hpx',extent='64',ranks='4',threads='2',warmups='2',samples='7',planner='FFTW_ESTIMATE').items())
assert result['status']=='PASS'
assert [int(item['index']) for item in samples]==list(range(7))
assert {item['stage'] for item in checks}=={'forward_spectrum','initial_roundtrip','final_roundtrip'} and len(checks)==3
assert all(math.isfinite(float(item['relative_max_error'])) and 0<=float(item['relative_max_error'])<=1e-10 for item in checks)
values=[float(item['max_rank_seconds']) for item in samples]
assert all(math.isfinite(value) and value>0 for value in values)
for key,value in dict(min_seconds=min(values),median_seconds=statistics.median(values),mean_seconds=statistics.mean(values),max_seconds=max(values)).items():
    assert math.isclose(float(result[key]),value,rel_tol=1e-13)
print(json.dumps(dict(configuration=cfg,checks=checks,result=result,scope='local correctness only'),indent=2))
PY
    run_log inputs_still_unchanged sha256sum -c "$out/input.sha256"
fi
stage=complete
