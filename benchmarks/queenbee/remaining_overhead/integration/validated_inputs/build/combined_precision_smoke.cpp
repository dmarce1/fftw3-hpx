/* Copyright (c) 2026 Dominic C. Marcello
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * General Public License for more details.
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software Foundation,
 * Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include <cassert>
#include <cmath>
#include <cstdio>
#include <stddef.h>

#include <hpx/async.hpp>
#include <hpx/executors/parallel_executor.hpp>
#include <hpx/hpx_init.hpp>
#include <hpx/include/runtime.hpp>

#include "fftw3-hpx.h"

namespace
{
#define DEFINE_CHECK(PREFIX, REAL)                                             \
void check_##PREFIX(fftw_hpx_comm const comm, ptrdiff_t const n0)                 \
{                                                                              \
    ptrdiff_t localN0 = 0;                                                      \
    ptrdiff_t start = 0;                                                        \
    ptrdiff_t const n1 = 8;                                                     \
    ptrdiff_t const count = PREFIX##_hpx_local_size_2d(                          \
        n0, n1, comm, &localN0, &start);                                         \
    PREFIX##_complex * const input =                                           \
        PREFIX##_alloc_complex(static_cast<size_t>(count > 0 ? count : 1));     \
    PREFIX##_complex * const output =                                          \
        PREFIX##_alloc_complex(static_cast<size_t>(count > 0 ? count : 1));     \
    assert(input && output);                                                   \
    PREFIX##_plan const plan = PREFIX##_hpx_plan_dft_2d(                        \
        n0, n1, input, output, comm, FFTW_FORWARD, FFTW_ESTIMATE);               \
    assert(plan);                                                              \
    for (ptrdiff_t index = 0; index < count; ++index)                            \
    {                                                                          \
        input[index][0] = 0;                                                   \
        input[index][1] = 0;                                                   \
    }                                                                          \
    if (start == 0 && localN0 != 0)                                             \
    {                                                                          \
        input[0][0] = 1;                                                       \
    }                                                                          \
    PREFIX##_execute(plan);                                                    \
    for (ptrdiff_t index = 0; index < localN0 * n1; ++index)                     \
    {                                                                          \
        assert(std::abs(output[index][0] - static_cast<REAL>(1)) <              \
               static_cast<REAL>(0.00001));                                    \
        assert(std::abs(output[index][1]) < static_cast<REAL>(0.00001));          \
    }                                                                          \
    PREFIX##_destroy_plan(plan);                                               \
    PREFIX##_free(input);                                                      \
    PREFIX##_free(output);                                                     \
}

DEFINE_CHECK(fftw, double)
DEFINE_CHECK(fftwf, float)
DEFINE_CHECK(fftwl, long double)
#undef DEFINE_CHECK

void checkPrecisions()
{
    fftw_hpx_init();
    fftwf_hpx_init();
    fftwl_hpx_init();
    fftw_plan_with_nthreads(2);
    fftwf_plan_with_nthreads(2);
    fftwl_plan_with_nthreads(2);
    fftw_hpx_comm const doubleWorld = fftw_hpx_comm_world();
    fftw_hpx_comm const floatWorld = fftwf_hpx_comm_world();
    fftw_hpx_comm const longWorld = fftwl_hpx_comm_world();
    assert(doubleWorld != floatWorld && doubleWorld != longWorld &&
           floatWorld != longWorld);
    check_fftw(doubleWorld, 6);
    check_fftwf(floatWorld, 6);
    check_fftwl(longWorld, 6);
    // Advance each precision's group by different amounts, then release
    // one precision while continuing to use both remaining groups.
    check_fftwf(floatWorld, 9);
    check_fftwf(floatWorld, 6);
    fftwf_hpx_cleanup();
    check_fftwl(longWorld, 9);
    check_fftw(doubleWorld, 9);
    fftwf_hpx_init();
    fftwf_plan_with_nthreads(2);
    check_fftwf(fftwf_hpx_comm_world(), 6);
    fftwl_hpx_cleanup();
    check_fftw(doubleWorld, 6);
    fftwf_hpx_cleanup();
    fftw_hpx_cleanup();
    if (hpx::get_locality_id() == 0)
    {
        std::puts("combined double/single/long-double precision smoke PASS");
    }
}

int hpxMain(int, char **)
{
    hpx::execution::parallel_executor const executor(
        hpx::threads::thread_stacksize::large);
    hpx::async(executor, checkPrecisions).get();
    return hpx::finalize();
}
}

int main(int argc, char ** argv)
{
    hpx::init_params parameters;
    parameters.cfg = {"hpx.run_hpx_main!=1"};
    return hpx::init(hpxMain, argc, argv, parameters);
}
