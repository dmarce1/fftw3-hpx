#!/usr/bin/env bash
set -Eeuo pipefail
repo=/home/dmarce1/workspace/fftw3-hpx
cd "$repo"
. build/hpx_env.sh
export APEX_DISABLE=1 HWLOC_COMPONENTS=-cuda,-nvml,-opencl
phase=${1:?build or test}
precisions=(double single long_double)
if [ -n "${2:-}" ]; then
    case "$2" in double|single|long_double) precisions=("$2");; *) exit 2;; esac
fi
out=$repo/build/qb_alltoall/local
mkdir -p "$out"
status_label=${phase}${2:+_$2}
trap 'printf "exit_status=%s\nfinished_utc=%s\n" "$?" "$(date -u +%FT%TZ)" > "$out/${status_label}_STATUS"' EXIT
run()
{
    local label=$1
    shift
    printf '%q ' "$@" > "$out/$label.command"
    printf '\n' >> "$out/$label.command"
    "$@" > "$out/$label.log" 2>&1
    printf '%s PASS\n' "$label"
}
for precision in "${precisions[@]}"; do
    if [ "$phase" = build ]; then
        case "$precision" in double) suffix=;; single) suffix=f;; long_double) suffix=l;; esac
        run "build_$precision" make -C "build/$precision/hpx" -j2 CXXFLAGS='-O3 -DNDEBUG' "libfftw3${suffix}_hpx.la" hpx-bench
        run "build_checks_$precision" make -C "build/$precision/hpx" -j2 CXXFLAGS='-O3 -UNDEBUG' hpx-message-check hpx-comm-check
    elif [ "$phase" = test ]; then
        run "all_to_all_$precision" timeout --kill-after=10s 900s env FFTW_HPX_TRANSPOSE_EXCHANGE=all_to_all make -j1 -C "build/$precision/hpx" check
        run "pairwise_$precision" timeout --kill-after=10s 900s env FFTW_HPX_TRANSPOSE_EXCHANGE=pairwise make -j1 -C "build/$precision/hpx" smallcheck
        for mode in pairwise all_to_all; do
            run "inactive_${mode}_$precision" timeout --kill-after=10s 180s env FFTW_HPX_TRANSPOSE_EXCHANGE="$mode" sh hpx/hpx-run.sh "$(command -v hpxrun.py)" 4 2 "$repo/build/$precision/hpx/hpx-bench" -o estimate -o nthreads=2 --verify ifc2x2x2 --verify ibc2x2x2 --verify ofc2x2x2
            run "uneven_${mode}_$precision" timeout --kill-after=10s 180s env FFTW_HPX_TRANSPOSE_EXCHANGE="$mode" sh hpx/hpx-run.sh "$(command -v hpxrun.py)" 3 2 "$repo/build/$precision/hpx/hpx-bench" -o estimate -o nthreads=2 --verify ifc5x7x3 --verify ibc5x7x3 --verify ofc5x7x3
        done
    else
        exit 2
    fi
done
sha256sum -c "$out/protected_archives.sha256" > "$out/${phase}_protected_check.log"
git diff --check
