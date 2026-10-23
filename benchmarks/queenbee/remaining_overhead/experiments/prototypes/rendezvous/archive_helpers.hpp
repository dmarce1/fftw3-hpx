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
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
 */

#ifndef FFTW_HPX_PROTOTYPE_ARCHIVE_HELPERS_HPP
#define FFTW_HPX_PROTOTYPE_ARCHIVE_HELPERS_HPP

#include <algorithm>
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

#include <hpx/serialization/input_archive.hpp>
#include <hpx/serialization/output_archive.hpp>

namespace prototype_units
{
inline void require(bool const condition, char const * const explanation)
{
    if (!condition)
    {
        throw std::runtime_error(explanation);
    }
}

template <typename Exception, typename Function>
void requireThrows(Function && function, char const * const explanation)
{
    try
    {
        function();
    }
    catch (Exception const &)
    {
        return;
    }
    throw std::runtime_error(explanation);
}

inline std::vector<char> payload(size_t const count, unsigned int const salt)
{
    std::vector<char> result(count);
    for (size_t index = 0; index < count; ++index)
    {
        result[index] = static_cast<char>((index * 37 + salt * 11) % 101 + 1);
    }
    return result;
}

template <typename Message>
std::vector<char> encode(Message const & message)
{
    std::vector<char> wire;
    hpx::serialization::output_archive archive(wire);
    archive << message;
    archive.flush();
    return wire;
}

template <typename Message>
Message decode(std::vector<char> const & encoded)
{
    auto wire = encoded;
    Message result;
    hpx::serialization::input_archive archive(wire);
    archive >> result;
    return result;
}

template <typename Message>
void requirePayload(Message const & message, std::vector<char> const & expected)
{
    require(message.size() == expected.size(), "payload size differs");
    if (!expected.empty())
    {
        require(std::equal(expected.begin(), expected.end(), message.data()),
                "payload contents differ");
    }
}

inline void pass(char const * const description)
{
    std::printf("CHECK %s PASS\n", description);
}
} // namespace prototype_units

#endif
