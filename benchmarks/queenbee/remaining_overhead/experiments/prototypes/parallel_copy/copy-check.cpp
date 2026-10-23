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
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include <array>
#include <cstdio>
#include <stdexcept>
#include <vector>

#include <hpx/hpx_init.hpp>

#include "hpx-comm.cpp"

namespace
{
char pattern(size_t const index)
{
    return static_cast<char>((index * 131 + index / 251 + 19) & 255);
}

void checkCopy(size_t const bytes, bool const owned)
{
    constexpr size_t guard = 37;
    std::vector<char> source(bytes);
    for (size_t index = 0; index < bytes; ++index)
    {
        source[index] = pattern(index);
    }
    Message const message = bytes == 0 ? Message() :
        Message(source.data(), bytes, owned ? Message::copy : Message::reference);
    if (owned)
    {
        std::fill(source.begin(), source.end(), char(0));
    }
    std::vector<char> destination(bytes + 2 * guard, char(0x5a));
    receiveBytes(destination.data() + guard, bytes, message);
    for (size_t index = 0; index < destination.size(); ++index)
    {
        char const expected = index < guard || index >= guard + bytes
                                  ? char(0x5a)
                                  : pattern(index - guard);
        if (destination[index] != expected)
        {
            throw std::runtime_error("copy payload or guard mismatch");
        }
    }
    std::printf("COPY_PASS bytes=%zu owned=%d jobs=%zu\n", bytes, owned,
                receiveCopyJobs(bytes));
}

int hpxMain(int, char **)
{
    size_t const threshold = 32 * 1024 * 1024;
    for (size_t const bytes : std::array<size_t, 6>{0, 1, threshold - 1,
                                                   threshold, threshold + 17,
                                                   2 * threshold + 3})
    {
        checkCopy(bytes, false);
    }
    checkCopy(threshold + 17, true);
    std::puts("PARALLEL_COPY_CHECK_PASS");
    return hpx::finalize();
}
} // namespace

int main(int argc, char ** argv)
{
    checkCopy(32 * 1024 * 1024 + 17, false);
    hpx::init_params parameters;
    parameters.cfg = {"hpx.run_hpx_main!=1"};
    return hpx::init(hpxMain, argc, argv, parameters);
}
