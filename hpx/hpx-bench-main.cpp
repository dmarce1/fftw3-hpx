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
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
 *
 */

#include <hpx/async.hpp>
#include <hpx/executors/parallel_executor.hpp>
#include <hpx/hpx_init.hpp>

extern "C" int fftw_hpx_bench_main(int argc, char ** argv);

namespace
{
int hpxMain(int const argc, char ** const argv)
{
    hpx::execution::parallel_executor const executor(
        hpx::threads::thread_stacksize::large);
    int const result = hpx::async(executor, [argc, argv]
                                  { return fftw_hpx_bench_main(argc, argv); })
                           .get();
    hpx::finalize();
    return result;
}
} // namespace

int main(int argc, char ** argv)
{
    hpx::init_params params;
    params.cfg = {"hpx.run_hpx_main!=1", "hpx.commandline.allow_unknown=1",
                  "hpx.commandline.aliasing=0"};
    return hpx::init(hpxMain, argc, argv, params);
}
