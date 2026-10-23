#!/usr/bin/env python3
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
"""Instrument a temporary FFTW source snapshot for HPX forward-sample profiling.

Usage: python3 instrument.py SOURCE_DIR
No build or runtime commands are executed. Refuses Git working trees and an
already-instrumented snapshot. Both files are validated before either is written.
All PROFILE timings are inclusive; overlapping metrics must not be summed.
"""
import json
from pathlib import Path
import re
import sys

MARKER = "FFTW_HPX_DIAGNOSTIC_PROFILE"
BRIDGE_PROFILE = r'''
// FFTW_HPX_DIAGNOSTIC_PROFILE: temporary diagnostic snapshot only.
namespace
{
enum class ProfileMetric
{
    copyBytes,
    messageBytes,
    receiveBytes,
    runJobs,
    send,
    recv,
    sendrecv,
    count
};

struct ProfileCounter
{
    std::atomic<unsigned long long> nanoseconds{0};
    std::atomic<unsigned long long> calls{0};
};

std::array<ProfileCounter, static_cast<size_t>(ProfileMetric::count)> profileCounters;
std::atomic<bool> profileActive{false};
char const * const profileNames[] = {
    "copy_bytes_inclusive", "message_bytes_inclusive", "receive_bytes_inclusive",
    "run_jobs_inclusive", "send_inclusive", "recv_inclusive", "sendrecv_inclusive"};

struct ProfileScope
{
    using ProfileClock = std::chrono::steady_clock;
    ProfileMetric const metric;
    bool const active;
    ProfileClock::time_point const started;

    explicit ProfileScope(ProfileMetric const selected)
        : metric(selected), active(profileActive.load(std::memory_order_relaxed)),
          started(active ? ProfileClock::now() : ProfileClock::time_point{})
    {
    }

    ~ProfileScope()
    {
        if (active)
        {
            auto const elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                ProfileClock::now() - started).count();
            auto & counter = profileCounters[static_cast<size_t>(metric)];
            counter.nanoseconds.fetch_add(static_cast<unsigned long long>(elapsed),
                                          std::memory_order_relaxed);
            counter.calls.fetch_add(1, std::memory_order_relaxed);
        }
    }
};
} // namespace

extern "C" void FFTW_HPX_COMM_FN(profile_reset)(void)
{
    profileActive.store(false, std::memory_order_relaxed);
    for (auto & counter : profileCounters)
    {
        counter.nanoseconds.store(0, std::memory_order_relaxed);
        counter.calls.store(0, std::memory_order_relaxed);
    }
    profileActive.store(true, std::memory_order_relaxed);
}

extern "C" void FFTW_HPX_COMM_FN(profile_report)(int const rank, int const sample)
{
    profileActive.store(false, std::memory_order_relaxed);
    for (size_t index = 0; index < profileCounters.size(); ++index)
    {
        auto const calls = profileCounters[index].calls.load(std::memory_order_relaxed);
        auto const nanoseconds =
            profileCounters[index].nanoseconds.load(std::memory_order_relaxed);
        std::fprintf(stderr,
                     "PROFILE rank=%d sample=%d metric=%s calls=%llu seconds=%.17g\n",
                     rank, sample, profileNames[index], calls,
                     static_cast<double>(nanoseconds) * 1e-9);
    }
    std::fflush(stderr);
}

'''

DRIVER_DECLARATIONS = r'''
// FFTW_HPX_DIAGNOSTIC_PROFILE: these hooks exist only in diagnostic snapshots.
#ifdef FFTW_BENCH_HPX
extern "C" void fftw_hpx_profile_reset(void);
extern "C" void fftw_hpx_profile_report(int rank, int sample);
#endif

'''

DRIVER_CONFIG = r'''        char const * const diagnosticKeys[] = {
            "hpx.parcel.zero_copy_optimization",
            "hpx.parcel.zero_copy_receive_optimization",
            "hpx.parcel.mpi.zero_copy_optimization",
            "hpx.parcel.mpi.zero_copy_receive_optimization",
            "hpx.parcel.mpi.background_threads", "hpx.parcel.mpi.multithreaded",
            "hpx.parcel.mpi.sendimm", "hpx.parcel.mpi.ack_handshake",
            "hpx.parcel.mpi.enable", "hpx.max_background_threads",
            "hpx.max_idle_loop_count", "hpx.max_busy_loop_count",
            "hpx.max_idle_backoff_time", "hpx.default_scheduler_mode",
            "hpx.scheduler", "hpx.numa_sensitive", "hpx.os_threads",
            "hpx.affinity", "hpx.bind", "hpx.pu_offset", "hpx.pu_step",
            "hpx.stacks.large_size", "hpx.stacks.use_guard_pages"};
        for (char const * const key : diagnosticKeys)
        {
            std::string const value = hpx::get_config_entry(key, "<unset>");
            std::fprintf(stderr, "CONFIG_DIAGNOSTIC rank=%d key=%s value=%s\n",
                         rank, key, value.c_str());
        }
        std::fflush(stderr);
'''


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError("Expected exactly one " + label + " anchor")
    return text.replace(old, new, 1)


def instrument_function(text, pattern, metric, minimum=1, maximum=1):
    def replacement(match):
        return match.group(0) + "\n    ProfileScope const profileScope(ProfileMetric::" + metric + ");"
    text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count < minimum or (maximum is not None and count > maximum):
        raise RuntimeError("Unexpected definition count for " + metric + ": " + str(count))
    return text, count


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    source = Path(sys.argv[1]).resolve()
    if (source / ".git").exists():
        raise RuntimeError("Refusing to instrument a Git working tree: " + str(source))
    bridge_path = source / "hpx/hpx-comm.cpp"
    driver_path = source / "benchmarks/matched_3d.cpp"
    bridge = bridge_path.read_text()
    driver = driver_path.read_text()
    if MARKER in bridge or MARKER in driver:
        raise RuntimeError("Snapshot is already instrumented; start from a fresh copy")
    for header in ("array", "atomic", "chrono"):
        if "#include <" + header + ">" not in bridge:
            bridge = replace_once(bridge, "#include <algorithm>\n",
                                  "#include <algorithm>\n#include <" + header + ">\n",
                                  "bridge standard includes")
    namespace_anchor = "\nnamespace\n{\n"
    if namespace_anchor not in bridge:
        raise RuntimeError("Missing first bridge namespace anchor")
    bridge = bridge.replace(namespace_anchor, BRIDGE_PROFILE + "namespace\n{\n", 1)
    counts = {}
    for name, return_type, minimum, maximum in (
        ("copyBytes", "Bytes", 1, 1), ("messageBytes", "Message", 0, 1),
        ("receiveBytes", "void", 1, None), ("runJobs", "void", 1, 1)
    ):
        pattern = r"^" + return_type + r"\s+" + name + r"\([^{};]*\n\{"
        bridge, counts[name] = instrument_function(bridge, pattern, name, minimum, maximum)
    for name in ("send", "recv", "sendrecv"):
        pattern = r'^extern "C" void FFTW_HPX_COMM_FN\(' + name + r'\)\([^{};]*\ntry\n\{'
        bridge, counts[name] = instrument_function(bridge, pattern, name)
    driver = replace_once(driver, "#include <hpx/runtime_local/get_os_thread_count.hpp>\n",
                          "#include <hpx/runtime_local/config_entry.hpp>\n#include <hpx/runtime_local/get_os_thread_count.hpp>\n",
                          "driver runtime includes")
    driver = replace_once(driver, "\nnamespace\n{\n", DRIVER_DECLARATIONS + "namespace\n{\n",
                          "driver namespace")
    driver = replace_once(driver, "        fftw_hpx_init();\n", DRIVER_CONFIG + "        fftw_hpx_init();\n",
                          "driver HPX initialization")
    driver = replace_once(driver, "        auto const begin = Clock::now();\n",
                          "#ifdef FFTW_BENCH_HPX\n        fftw_hpx_profile_reset();\n#endif\n        auto const begin = Clock::now();\n",
                          "forward timing start")
    elapsed = "        double const localElapsed = std::chrono::duration<double>(Clock::now() - begin).count();\n"
    driver = replace_once(driver, elapsed,
                          elapsed + "#ifdef FFTW_BENCH_HPX\n        fftw_hpx_profile_report(backend.rank, sample);\n"
                          "        std::fprintf(stderr, \"PROFILE_TOTAL rank=%d sample=%d seconds=%.17g\\n\",\n"
                          "                     backend.rank, sample, localElapsed);\n"
                          "        std::fflush(stderr);\n#endif\n",
                          "forward timing end")
    bridge_path.write_text(bridge)
    driver_path.write_text(driver)
    print("Instrumented " + str(source))
    print("Definition counts: " + json.dumps(counts, sort_keys=True))
    print("PROFILE timings are inclusive and overlap; do not sum different metrics.")


if __name__ == "__main__":
    main()
