#!/bin/bash -l
#SBATCH --job-name=fftw_lean_hpx
#SBATCH --partition=workq
#SBATCH --account=loni_graphshpx
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=32
#SBATCH --exclusive
#SBATCH --time=00:30:00
#SBATCH --mail-type=NONE
#SBATCH --output=/work/dmarce1/fftw3_hpx_remaining_20261023/lean_hpx/build-%j.out
#SBATCH --error=/work/dmarce1/fftw3_hpx_remaining_20261023/lean_hpx/build-%j.err
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

# Review/submission and all QB access belong to the root agent. This script
# performs no network downloads and never configures or installs over old HPX.
set -Eeuo pipefail
: "${SLURM_JOB_ID:?Run inside the authorized one-node Slurm allocation}"
qb_original=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx
qb_lean=/work/dmarce1/fftw3_hpx_remaining_20261023/lean_hpx
qb_source=$qb_original/src
qb_build=$qb_lean/build
qb_install=$qb_lean/install
qb_results=$qb_lean/results/$SLURM_JOB_ID
qb_mpi=/work/dmarce1/OctotigerII/packages/openmpi-5.0.11-gcc13.2/install
qb_hwloc=/usr/local/packages/hwloc/2.9.1/7ka44tz
qb_jemalloc=/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/jemalloc/install
qb_commit=c9b81b401fbe6ba4a0306feff71d18ef01c71b34
qb_stage=setup
qb_started=$(date -u +%FT%TZ)
mkdir -p "$qb_results"
exec > >(stdbuf -oL -eL tee -a "$qb_results/job.log") 2>&1

finish()
{
    local result=$1
    trap - EXIT
    set +e
    local outcome=FAIL
    if [ "$result" -eq 0 ] && [ "$qb_stage" = complete ]; then
        outcome=PASS
    elif [ "$result" -eq 0 ]; then
        result=1
    fi
    {
        printf 'status\t%s\nexit_status\t%s\njob_id\t%s\nstage\t%s\n' "$outcome" "$result" "$SLURM_JOB_ID" "$qb_stage"
        printf 'started_utc\t%s\nfinished_utc\t%s\nsource_commit\t%s\n' "$qb_started" "$(date -u +%FT%TZ)" "$qb_commit"
        printf 'build\t%s\ninstall\t%s\n' "$qb_build" "$qb_install"
    } > "$qb_results/FINAL_STATUS"
    cp "$qb_results/FINAL_STATUS" "$qb_lean/FINAL_STATUS"
    printf 'FINAL_STATUS %s exit=%s stage=%s\n' "$outcome" "$result" "$qb_stage"
    exit "$result"
}
trap 'finish "$?"' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

run_log()
{
    local label=$1
    shift
    qb_stage=$label
    printf '%q ' "$@" > "$qb_results/$label.command"
    printf '\n' >> "$qb_results/$label.command"
    "$@" 2>&1 | stdbuf -oL -eL tee "$qb_results/$label.log"
}

[ "${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-0}}" -eq 1 ]
[ "${SLURM_NTASKS:-0}" -eq 1 ]
[ "${SLURM_CPUS_PER_TASK:-0}" -eq 32 ]
# Refuse an existing tree. Failed builds remain available for diagnosis; a
# reviewed follow-up can choose another fresh path instead of deleting evidence.
test ! -e "$qb_build"
test ! -e "$qb_install"
test -f "$qb_lean/prepare.py"
test -f "$qb_lean/original-CMakeCache.txt"
test -f "$qb_original/build/_deps/asio-src/asio/include/asio.hpp"
test -f "$qb_source/CMakeLists.txt"
test -x "$qb_mpi/bin/mpicxx"
cmp "$qb_lean/original-CMakeCache.txt" "$qb_original/build/CMakeCache.txt"
[ "$(git -C "$qb_source" rev-parse HEAD)" = "$qb_commit" ]
git -C "$qb_source" diff --quiet HEAD --
git -C "$qb_source" status --porcelain=v1 --untracked-files=normal > "$qb_results/source-before.status"
cp "$0" "$qb_results/build.sbatch"
cp "$qb_lean/prepare.py" "$qb_results/prepare.py"
cp "$qb_lean/original-CMakeCache.txt" "$qb_results/original-CMakeCache.txt"
sha256sum "$qb_original/build/CMakeCache.txt" \
    "$qb_original/install/include/hpx/config/defines.hpp" \
    "$qb_original/install/lib64/cmake/HPX/HPXCacheVariables.cmake" \
    "$qb_original/install/lib64/libhpx.so" \
    "$qb_original/install/lib64/libhpx_core.so" > "$qb_results/original-inputs.sha256"

module purge
module load gcc/13.2.0
export PATH="$qb_mpi/bin:$PATH"
export LD_LIBRARY_PATH="$qb_mpi/lib:$qb_mpi/lib64:$qb_hwloc/lib:$qb_jemalloc/lib:${LD_LIBRARY_PATH:-}"
export HWLOC_COMPONENTS=-cuda,-nvml,-opencl
unset HPXRUN_NODES HPXRUN_ARGS
{
    date -u
    hostname
    module -t list 2>&1
    cmake --version
    python3 --version
    /usr/local/packages/compilers/gcc/13.2.0/bin/g++ --version
    "$qb_mpi/bin/mpicxx" --showme
    printf 'source=%s\nsource_commit=%s\nworkers=32\n' "$qb_source" "$qb_commit"
} > "$qb_results/metadata.txt"
run_log prepare python3 -I "$qb_lean/prepare.py" prepare "$qb_lean/original-CMakeCache.txt" "$qb_results"
run_log configure cmake -S "$qb_source" -B "$qb_build" -G 'Unix Makefiles' -C "$qb_results/initial-cache.cmake"
run_log audit_configuration python3 -I "$qb_lean/prepare.py" audit "$qb_results/configuration.json" "$qb_build"
run_log build cmake --build "$qb_build" --parallel 32
run_log install cmake --install "$qb_build"
run_log audit_install python3 -I "$qb_lean/prepare.py" audit "$qb_results/configuration.json" "$qb_build" --install "$qb_install"
run_log verify_original sha256sum -c "$qb_results/original-inputs.sha256"
git -C "$qb_source" diff --quiet HEAD --
git -C "$qb_source" status --porcelain=v1 --untracked-files=normal > "$qb_results/source-after.status"
cmp "$qb_results/source-before.status" "$qb_results/source-after.status"
cp "$qb_build/CMakeCache.txt" "$qb_results/lean-CMakeCache.txt"
cp "$qb_build/compile_commands.json" "$qb_results/compile_commands.json"
cp "$qb_install/include/hpx/config/defines.hpp" "$qb_results/lean-defines.hpp"
cp "$qb_install/include/hpx/config/config_strings.hpp" "$qb_results/lean-config_strings.hpp"
run_log dynamic_dependencies ldd "$qb_install/lib64/libhpx.so" "$qb_install/lib64/libhpx_core.so"
if grep -Eiq 'not found|libapex' "$qb_results/dynamic_dependencies.log"; then
    printf 'Unexpected missing dependency or APEX dependency in lean HPX\n' >&2
    exit 1
fi
sha256sum "$qb_install/lib64/libhpx.so" "$qb_install/lib64/libhpx_core.so" \
    "$qb_install/include/hpx/config/defines.hpp" "$qb_install/lib64/cmake/HPX/HPXCacheVariables.cmake" \
    > "$qb_results/installed-artifacts.sha256"
qb_stage=complete
