/*
 * Copyright (c) 2026 Dominic C. Marcello
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 */

// Experimental diagnostic-only copy: reset/report receive counters outside
// the unchanged forward timer and barrier before inverse counter activity.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <functional>
#include <limits>
#include <numeric>
#include <stddef.h>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef FFTW_BENCH_HPX
#include <hpx/async.hpp>
#include <hpx/collectives/all_reduce.hpp>
#include <hpx/collectives/create_communicator.hpp>
#include <hpx/executors/parallel_executor.hpp>
#include <hpx/hpx_init.hpp>
#include <hpx/include/runtime.hpp>
#include <hpx/runtime_local/get_os_thread_count.hpp>
#else
#include <mpi.h>
#endif

#ifdef FFTW_BENCH_HPX
#include "fftw3-hpx.h"
#include "receive-diagnostics.hpp"
#else
#include "fftw3-mpi.h"
#endif

namespace
{
using Clock = std::chrono::steady_clock;
using Complex = std::complex<double>;

struct Options
{
    ptrdiff_t extent = 1024;
    int threads = 1;
    int warmups = 2;
    int samples = 7;
};

long long integerOption(std::string const & text, std::string const & prefix)
{
    size_t parsed = 0;
    std::string const value = text.substr(prefix.size());
    long long const result = std::stoll(value, &parsed);
    if (parsed != value.size())
    {
        throw std::runtime_error("invalid option: " + text);
    }
    return result;
}

Options parseOptions(int const argc, char ** const argv)
{
    Options result;
    for (int argument = 1; argument < argc; ++argument)
    {
        std::string const text(argv[argument]);
        if (text.rfind("--size=", 0) == 0)
        {
            long long const value = integerOption(text, "--size=");
            if (value < 2 || value > std::numeric_limits<ptrdiff_t>::max())
            {
                throw std::runtime_error("size must be a representable positive power of two");
            }
            result.extent = static_cast<ptrdiff_t>(value);
        }
        else
        {
            std::string const prefix = text.rfind("--threads=", 0) == 0   ? "--threads="
                                       : text.rfind("--warmups=", 0) == 0 ? "--warmups="
                                       : text.rfind("--samples=", 0) == 0 ? "--samples="
                                                                          : "";
            if (prefix.empty())
            {
                throw std::runtime_error("unknown option: " + text);
            }
            long long const value = integerOption(text, prefix);
            if (value < 1 || value > std::numeric_limits<int>::max())
            {
                throw std::runtime_error("option must be a positive integer: " + text);
            }
            if (prefix == "--threads=")
            {
                result.threads = static_cast<int>(value);
            }
            else if (prefix == "--warmups=")
            {
                result.warmups = static_cast<int>(value);
            }
            else
            {
                result.samples = static_cast<int>(value);
            }
        }
    }
    ptrdiff_t const n = result.extent;
    if ((n & (n - 1)) != 0 || n > std::numeric_limits<ptrdiff_t>::max() / n / n ||
        static_cast<size_t>(n) > std::numeric_limits<size_t>::max() / sizeof(fftw_complex) / n / n)
    {
        throw std::runtime_error("size must be a power of two with representable array size");
    }
    return result;
}

struct Backend
{
    int rank = 0;
    int ranks = 1;
#ifdef FFTW_BENCH_HPX
    static constexpr char const * name = "hpx";
    fftw_hpx_comm world = FFTW_HPX_COMM_NULL;
    hpx::collectives::communicator statistics;
    size_t generation = 0;
#else
    static constexpr char const * name = "mpi";
#endif

    void initialize(int const threads)
    {
#ifdef FFTW_BENCH_HPX
        rank = static_cast<int>(hpx::get_locality_id());
        ranks = static_cast<int>(hpx::get_num_localities(hpx::launch::sync));
        if (hpx::get_os_thread_count() != static_cast<size_t>(threads))
        {
            throw std::runtime_error("HPX worker count must equal --threads");
        }
        fftw_hpx_init();
        world = fftw_hpx_comm_world();
        statistics = hpx::collectives::create_communicator("fftw_hpx/matched3d_statistics",
                                                           hpx::collectives::num_sites_arg(ranks),
                                                           hpx::collectives::this_site_arg(rank));
#else
        MPI_Comm_rank(MPI_COMM_WORLD, &rank);
        MPI_Comm_size(MPI_COMM_WORLD, &ranks);
        if (!fftw_init_threads())
        {
            throw std::runtime_error("fftw_init_threads failed");
        }
        fftw_mpi_init();
#endif
        fftw_plan_with_nthreads(threads);
    }

    void barrier()
    {
#ifdef FFTW_BENCH_HPX
        hpx::collectives::all_reduce(hpx::launch::sync, statistics, 1, std::plus<>{},
                                     hpx::collectives::this_site_arg(rank),
                                     hpx::collectives::generation_arg(++generation));
#else
        MPI_Barrier(MPI_COMM_WORLD);
#endif
    }

    double maximum(double const value)
    {
#ifdef FFTW_BENCH_HPX
        return hpx::collectives::all_reduce(
            hpx::launch::sync, statistics, value,
            [](double const left, double const right) { return std::max(left, right); },
            hpx::collectives::this_site_arg(rank), hpx::collectives::generation_arg(++generation));
#else
        double result = 0;
        MPI_Allreduce(&value, &result, 1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);
        return result;
#endif
    }

    ptrdiff_t localSize(ptrdiff_t const n, ptrdiff_t & localN, ptrdiff_t & start) const
    {
#ifdef FFTW_BENCH_HPX
        return fftw_hpx_local_size_3d(n, n, n, world, &localN, &start);
#else
        return fftw_mpi_local_size_3d(n, n, n, MPI_COMM_WORLD, &localN, &start);
#endif
    }

    fftw_plan plan(ptrdiff_t const n, fftw_complex * const data, int const sign) const
    {
#ifdef FFTW_BENCH_HPX
        return fftw_hpx_plan_dft_3d(n, n, n, data, data, world, sign, FFTW_ESTIMATE);
#else
        return fftw_mpi_plan_dft_3d(n, n, n, data, data, MPI_COMM_WORLD, sign, FFTW_ESTIMATE);
#endif
    }

    void cleanup()
    {
#ifdef FFTW_BENCH_HPX
        statistics.free();
        fftw_hpx_cleanup();
#else
        fftw_mpi_cleanup();
        fftw_cleanup_threads();
#endif
    }
};

struct Mode
{
    int x;
    int y;
    int z;
    Complex amplitude;
};

std::array<Mode, 3> const modes = {
    {{1, 2, 3, {0.375, 0.25}}, {3, 1, 2, {-0.5, 0.125}}, {-2, -3, 1, {0.125, -0.25}}}};

ptrdiff_t frequency(int const value, ptrdiff_t const n)
{
    return (static_cast<ptrdiff_t>(value) % n + n) % n;
}

class AnalyticInput
{
    std::array<std::array<std::vector<Complex>, 3>, 3> phases;

  public:
    explicit AnalyticInput(ptrdiff_t const n)
    {
        double const pi = std::acos(-1.0);
        for (size_t mode = 0; mode < modes.size(); ++mode)
        {
            std::array<int, 3> const wave = {modes[mode].x, modes[mode].y, modes[mode].z};
            for (size_t axis = 0; axis < wave.size(); ++axis)
            {
                auto & table = phases[mode][axis];
                table.resize(static_cast<size_t>(n));
                for (ptrdiff_t index = 0; index < n; ++index)
                {
                    double const angle = 2 * pi * wave[axis] * static_cast<double>(index) / n;
                    table[static_cast<size_t>(index)] = {std::cos(angle), std::sin(angle)};
                }
            }
        }
    }

    Complex value(ptrdiff_t const x, ptrdiff_t const y, ptrdiff_t const z) const
    {
        Complex result = 0;
        for (size_t mode = 0; mode < modes.size(); ++mode)
        {
            result += modes[mode].amplitude * phases[mode][0][x] * phases[mode][1][y] *
                      phases[mode][2][z];
        }
        return result;
    }
};

double spectralError(fftw_complex const * const data, ptrdiff_t const localN, ptrdiff_t const start,
                     ptrdiff_t const n, Backend & backend)
{
    double error = 0;
    double const volume = static_cast<double>(n) * n * n;
    double scale = 0;
    std::array<ptrdiff_t, 3> locations;
    for (size_t mode = 0; mode < modes.size(); ++mode)
    {
        scale = std::max(scale, std::abs(modes[mode].amplitude));
        ptrdiff_t const x = frequency(modes[mode].x, n) - start;
        locations[mode] = x >= 0 && x < localN ? (x * n + frequency(modes[mode].y, n)) * n +
                                                     frequency(modes[mode].z, n)
                                               : -1;
    }
    for (ptrdiff_t index = 0; index < localN * n * n; ++index)
    {
        Complex expected = 0;
        for (size_t mode = 0; mode < modes.size(); ++mode)
        {
            if (index == locations[mode])
            {
                expected += modes[mode].amplitude;
            }
        }
        Complex const actual(data[index][0] / volume, data[index][1] / volume);
        double const difference = std::abs(actual - expected);
        error = !std::isfinite(difference) ? std::numeric_limits<double>::infinity()
                                           : std::max(error, difference);
    }
    return backend.maximum(error) / scale;
}

double roundtripError(fftw_complex const * const data, AnalyticInput const & input,
                      ptrdiff_t const localN, ptrdiff_t const start, ptrdiff_t const n,
                      Backend & backend)
{
    double error = 0;
    double scale = 0;
    for (ptrdiff_t x = 0; x < localN; ++x)
    {
        for (ptrdiff_t y = 0; y < n; ++y)
        {
            for (ptrdiff_t z = 0; z < n; ++z)
            {
                ptrdiff_t const index = (x * n + y) * n + z;
                Complex const expected = input.value(x + start, y, z);
                Complex const actual(data[index][0], data[index][1]);
                double const difference = std::abs(actual - expected);
                error = !std::isfinite(difference) ? std::numeric_limits<double>::infinity()
                                                   : std::max(error, difference);
                scale = std::max(scale, std::abs(expected));
            }
        }
    }
    double const globalError = backend.maximum(error);
    return globalError / backend.maximum(scale);
}

void normalize(fftw_complex * const data, ptrdiff_t const localCount, ptrdiff_t const n)
{
    double const inverseVolume = 1 / (static_cast<double>(n) * n * n);
    for (ptrdiff_t index = 0; index < localCount; ++index)
    {
        data[index][0] *= inverseVolume;
        data[index][1] *= inverseVolume;
    }
}

void checkError(char const * const stage, double const error, Backend const & backend)
{
    double constexpr tolerance = 1e-10;
    if (backend.rank == 0)
    {
        std::printf("CHECK backend=%s stage=%s relative_max_error=%.17g tolerance=%.17g\n",
                    Backend::name, stage, error, tolerance);
        std::fflush(stdout);
    }
    if (!std::isfinite(error) || error > tolerance)
    {
        throw std::runtime_error(std::string("correctness check failed: ") + stage);
    }
}

void runBenchmark(Options const & options)
{
    Backend backend;
    backend.initialize(options.threads);
    ptrdiff_t const n = options.extent;
    ptrdiff_t localN = 0;
    ptrdiff_t start = 0;
    ptrdiff_t const allocation = backend.localSize(n, localN, start);
    ptrdiff_t const localCount = localN * n * n;
    fftw_complex * const data =
        fftw_alloc_complex(static_cast<size_t>(std::max<ptrdiff_t>(1, allocation)));
    if (data == nullptr)
    {
        throw std::runtime_error("FFTW allocation failed");
    }
    double const maxAllocation =
        backend.maximum(static_cast<double>(allocation) * sizeof(fftw_complex));
    if (backend.rank == 0)
    {
        std::printf("CONFIG backend=%s extent=%td ranks=%d threads=%d precision=double "
                    "inplace=1 layout=normal planner=FFTW_ESTIMATE warmups=%d samples=%d "
                    "global_data_bytes=%.0f max_local_allocation_bytes=%.0f\n",
                    Backend::name, n, backend.ranks, options.threads, options.warmups,
                    options.samples, static_cast<double>(n) * n * n * sizeof(fftw_complex),
                    maxAllocation);
        std::fflush(stdout);
    }
    backend.barrier();
    auto const planStart = Clock::now();
    fftw_plan const forward = backend.plan(n, data, FFTW_FORWARD);
    fftw_plan const backward = backend.plan(n, data, FFTW_BACKWARD);
    double const planning =
        backend.maximum(std::chrono::duration<double>(Clock::now() - planStart).count());
    if (forward == nullptr || backward == nullptr)
    {
        throw std::runtime_error("FFTW plan creation failed");
    }
    if (backend.rank == 0)
    {
        std::printf("PLAN_SECONDS backend=%s value=%.17g\nPLAN_FORWARD_BEGIN\n", Backend::name,
                    planning);
        fftw_print_plan(forward);
        std::printf("\nPLAN_FORWARD_END\nPLAN_BACKWARD_BEGIN\n");
        fftw_print_plan(backward);
        std::printf("\nPLAN_BACKWARD_END\n");
        std::fflush(stdout);
    }
    AnalyticInput const input(n);
    for (ptrdiff_t x = 0; x < localN; ++x)
    {
        for (ptrdiff_t y = 0; y < n; ++y)
        {
            for (ptrdiff_t z = 0; z < n; ++z)
            {
                ptrdiff_t const index = (x * n + y) * n + z;
                Complex const value = input.value(x + start, y, z);
                data[index][0] = value.real();
                data[index][1] = value.imag();
            }
        }
    }
    fftw_execute(forward);
    checkError("forward_spectrum", spectralError(data, localN, start, n, backend), backend);
    fftw_execute(backward);
    normalize(data, localCount, n);
    checkError("initial_roundtrip", roundtripError(data, input, localN, start, n, backend),
               backend);
    for (int warmup = 0; warmup < options.warmups; ++warmup)
    {
        fftw_execute(forward);
        fftw_execute(backward);
        normalize(data, localCount, n);
    }
    std::vector<double> samples;
    samples.reserve(static_cast<size_t>(options.samples));
    for (int sample = 0; sample < options.samples; ++sample)
    {
        // Diagnostic-only: the previous local inverse has completed. All ranks
        // reset before the existing barrier permits the next forward transform.
        FFTW_HPX_COMM_FN(receive_diagnostics_reset)();
        backend.barrier();
        auto const begin = Clock::now();
        fftw_execute(forward);
        double const localElapsed = std::chrono::duration<double>(Clock::now() - begin).count();
        double const elapsed = backend.maximum(localElapsed);
        FFTW_HPX_COMM_FN(receive_diagnostics_report)(backend.rank, sample);
        // Keep every inverse behind all reports so a fast rank cannot change
        // another rank's counters while it reports the completed forward.
        backend.barrier();
        samples.push_back(elapsed);
        if (backend.rank == 0)
        {
            std::printf("SAMPLE backend=%s index=%d max_rank_seconds=%.17g\n", Backend::name,
                        sample, elapsed);
            std::fflush(stdout);
        }
        fftw_execute(backward);
        normalize(data, localCount, n);
    }
    checkError("final_roundtrip", roundtripError(data, input, localN, start, n, backend), backend);
    std::vector<double> sorted = samples;
    std::sort(sorted.begin(), sorted.end());
    size_t const middle = sorted.size() / 2;
    double const median =
        sorted.size() % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    double const mean = std::accumulate(samples.begin(), samples.end(), 0.0) / samples.size();
    if (backend.rank == 0)
    {
        std::printf("RESULT backend=%s extent=%td ranks=%d threads=%d samples=%d "
                    "min_seconds=%.17g median_seconds=%.17g mean_seconds=%.17g max_seconds=%.17g "
                    "status=PASS\n",
                    Backend::name, n, backend.ranks, options.threads, options.samples,
                    sorted.front(), median, mean, sorted.back());
        std::fflush(stdout);
    }
    fftw_destroy_plan(backward);
    fftw_destroy_plan(forward);
    fftw_free(data);
    backend.cleanup();
}

[[noreturn]] void fail(char const * const message)
{
    std::fprintf(stderr, "matched_3d failure: %s\n", message);
    std::fflush(stderr);
#ifdef FFTW_BENCH_HPX
    hpx::terminate();
#else
    MPI_Abort(MPI_COMM_WORLD, 1);
    std::abort();
#endif
}

int application(int const argc, char ** const argv)
{
    try
    {
        runBenchmark(parseOptions(argc, argv));
    }
    catch (std::exception const & error)
    {
        fail(error.what());
    }
    catch (...)
    {
        fail("unknown exception");
    }
    return 0;
}

#ifdef FFTW_BENCH_HPX
int hpxMain(int const argc, char ** const argv)
{
    hpx::execution::parallel_executor const executor(hpx::threads::thread_stacksize::large);
    int const result = hpx::async(executor, [argc, argv] { return application(argc, argv); }).get();
    hpx::finalize();
    return result;
}
#endif
} // namespace

int main(int argc, char ** argv)
{
#ifdef FFTW_BENCH_HPX
    hpx::init_params parameters;
    parameters.cfg = {"hpx.run_hpx_main!=1",        "hpx.commandline.allow_unknown=1",
                      "hpx.commandline.aliasing=0", "hpx.parcel.tcp.enable!=0",
                      "hpx.parcel.mpi.enable!=1",   "hpx.parcel.bootstrap!=mpi"};
    return hpx::init(hpxMain, argc, argv, parameters);
#else
    int provided = 0;
    MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);
    if (provided < MPI_THREAD_FUNNELED)
    {
        fail("MPI_THREAD_FUNNELED is required");
    }
    int const result = application(argc, argv);
    MPI_Finalize();
    return result;
#endif
}
