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

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <exception>
#include <string>
#include <vector>

#include <hpx/serialization/detail/allow_zero_copy_receive.hpp>
#include <hpx/serialization/serialization_chunk.hpp>

#include "archive_helpers.hpp"
#include "../direct_receive/hpx-comm.cpp"

namespace
{
using namespace prototype_units;

transport::Key key(size_t const tag)
{
    return {std::string(precisionPrefix) + "/unit/e1", 2, tag};
}

void checkPostedDestination()
{
    auto source = payload(193, 1);
    auto const expected = source;
    std::vector<char> destination(source.size() + 16, 117);
    auto const match = key(41);
    transport::Registration const posted(match, destination.data() + 8,
                                         source.size(), true);
    auto const wire = encode(Message(match, source.data(), source.size(), false));
    auto incoming = decode<Message>(wire);
    require(incoming.data() == destination.data() + 8,
            "posted receive did not use the exact destination");
    requirePayload(incoming, expected);
    require(std::all_of(destination.begin(), destination.begin() + 8,
                        [](char const value) { return value == 117; }),
            "prefix guard overwritten");
    require(std::all_of(destination.end() - 8, destination.end(),
                        [](char const value) { return value == 117; }),
            "suffix guard overwritten");
    std::fill(source.begin(), source.end(), 0);
    requirePayload(incoming, expected);
    requireThrows<std::logic_error>([&] { decode<Message>(wire); },
                                   "posted destination was claimed twice");
    pass("posted_destination_exact_pointer_contents_guards_and_single_claim");
}

void checkOwnedFallback()
{
    auto source = payload(257, 2);
    auto const expected = source;
    auto wire = encode(Message(key(42), source.data(), source.size(), false));
    auto incoming = decode<Message>(wire);
    require(incoming.data() != source.data(), "fallback retained sender storage");
    auto held = incoming;
    auto const ownedAddress = incoming.data();
    incoming = Message();
    std::fill(source.begin(), source.end(), 0);
    std::fill(wire.begin(), wire.end(), 0);
    require(held.data() == ownedAddress, "Message copy lost shared ownership");
    requirePayload(held, expected);
    pass("missing_target_fallback_owns_storage_beyond_source_archive_and_original_message");
}

void checkMismatch()
{
    auto const shortSource = payload(31, 3);
    auto const correctSource = payload(32, 4);
    std::vector<char> destination(32, 119);
    auto const match = key(43);
    transport::Registration const posted(match, destination.data(),
                                         destination.size(), true);
    auto const wrongWire = encode(Message(match, shortSource.data(),
                                          shortSource.size(), false));
    requireThrows<std::length_error>([&] { decode<Message>(wrongWire); },
                                    "byte count mismatch did not throw");
    require(std::all_of(destination.begin(), destination.end(),
                        [](char const value) { return value == 119; }),
            "size mismatch wrote to the posted destination");
    auto const correctWire = encode(Message(match, correctSource.data(),
                                            correctSource.size(), false));
    auto const incoming = decode<Message>(correctWire);
    require(incoming.data() == destination.data(),
            "mismatch consumed the valid posted destination");
    requirePayload(incoming, correctSource);
    pass("size_mismatch_throws_before_write_or_claim");
}

void checkKeyIsolation()
{
    auto const source = payload(97, 5);
    std::vector<char> destination(source.size(), 123);
    auto const match = key(44);
    transport::Registration const posted(match, destination.data(),
                                         destination.size(), true);
    auto wrongGroup = match;
    std::get<0>(wrongGroup) += "/split/1";
    auto wrongEpoch = match;
    std::get<0>(wrongEpoch) += "/e2";
    auto wrongPrecision = match;
    std::get<0>(wrongPrecision) =
        std::string(precisionPrefix) == "fftw_hpx" ? "fftwf_hpx/unit/e1"
                                                  : "fftw_hpx/unit/e1";
    auto wrongSource = match;
    ++std::get<1>(wrongSource);
    auto wrongTag = match;
    ++std::get<2>(wrongTag);
    auto wrongSequence = match;
    std::get<2>(wrongSequence) += size_t(1) << 15;
    for (auto const & other : {wrongGroup, wrongEpoch, wrongPrecision,
                               wrongSource, wrongTag, wrongSequence})
    {
        auto const wire = encode(Message(other, source.data(), source.size(), false));
        auto const incoming = decode<Message>(wire);
        require(incoming.data() != destination.data(),
                "unmatched key claimed the posted destination");
        requirePayload(incoming, source);
        require(std::all_of(destination.begin(), destination.end(),
                            [](char const value) { return value == 123; }),
                "unmatched key changed the posted destination");
    }
    auto const wire = encode(Message(match, source.data(), source.size(), false));
    auto const incoming = decode<Message>(wire);
    require(incoming.data() == destination.data(), "matching key was lost");
    requirePayload(incoming, source);
    pass("precision_group_epoch_source_tag_sequence_isolation");
}

void checkZeroCopyArchive()
{
    auto const source = payload(4096, 6);
    std::vector<char> destination(source.size(), 125);
    auto const match = key(45);
    transport::Registration const posted(match, destination.data(),
                                         destination.size(), true);
    Message const outgoing(match, source.data(), source.size(), false);
    std::vector<char> wire;
    std::vector<hpx::serialization::serialization_chunk> outgoingChunks;
    {
        hpx::serialization::output_archive archive(wire, 0, &outgoingChunks,
                                                    nullptr, 128);
        archive << outgoing;
        archive.flush();
    }
    auto incomingChunks = outgoingChunks;
    size_t pointerChunks = 0;
    for (auto & chunk : incomingChunks)
    {
        if (chunk.type_ == hpx::serialization::chunk_type::chunk_type_pointer)
        {
            chunk = hpx::serialization::create_pointer_chunk(nullptr, chunk.size());
            ++pointerChunks;
        }
    }
    require(pointerChunks == 1, "archive did not expose exactly one payload chunk");
    Message incoming;
    {
        hpx::serialization::input_archive archive(wire, wire.size(), &incomingChunks);
        archive.get_extra_data<hpx::serialization::detail::allow_zero_copy_receive>();
        archive >> incoming;
    }
    require(incoming.data() == destination.data(),
            "zero-copy deserialization did not claim the posted destination");
    require(std::all_of(destination.begin(), destination.end(),
                        [](char const value) { return value == 125; }),
            "zero-copy deserialization copied before chunk reception");
    for (size_t index = 0; index < incomingChunks.size(); ++index)
    {
        auto & chunk = incomingChunks[index];
        if (chunk.type_ == hpx::serialization::chunk_type::chunk_type_pointer)
        {
            require(chunk.data() == destination.data() && chunk.size() == source.size(),
                    "network chunk destination differs from posted storage");
            // Model the subsequent transport write, after actual HPX archive
            // decoding has selected the exact address MPI_Irecv would receive.
            std::memcpy(chunk.data(), outgoingChunks[index].data(), chunk.size());
        }
    }
    requirePayload(incoming, source);
    pass("actual_hpx_zero_copy_archive_exports_exact_posted_chunk_destination");
}

void checkEmptySelfAndOverlap()
{
    auto source = payload(83, 7);
    auto const expected = source;
    Message const self(key(46), source.data(), source.size(), true);
    std::fill(source.begin(), source.end(), 0);
    requirePayload(self, expected);
    requirePayload(decode<Message>(encode(self)), expected);
    auto const empty = decode<Message>(encode(Message(key(47), nullptr, 0, false)));
    require(empty.size() == 0 && empty.data() == nullptr, "empty payload acquired storage");
    std::array<char, 64> buffer{};
    require(buffersOverlap(buffer.data(), 8, buffer.data(), 8), "exact overlap missed");
    require(buffersOverlap(buffer.data(), 8, buffer.data() + 7, 8), "right overlap missed");
    require(buffersOverlap(buffer.data() + 7, 8, buffer.data(), 8), "left overlap missed");
    require(buffersOverlap(buffer.data(), 32, buffer.data() + 8, 4), "contained overlap missed");
    require(!buffersOverlap(buffer.data(), 8, buffer.data() + 8, 8), "adjacent spans overlap");
    require(!buffersOverlap(buffer.data() + 8, 8, buffer.data(), 8), "reversed adjacent spans overlap");
    require(!buffersOverlap(nullptr, 0, buffer.data(), buffer.size()), "empty span overlaps");
    require(!buffersOverlap(buffer.data(), buffer.size(), nullptr, 0), "empty second span overlaps");
    pass("empty_payload_self_copy_and_overlap_boundaries");
}
} // namespace

int main()
try
{
    checkPostedDestination();
    checkOwnedFallback();
    checkMismatch();
    checkKeyIsolation();
    checkZeroCopyArchive();
    checkEmptySelfAndOverlap();
    transport::ensureNoReceives();
    std::puts("DIRECT_RECEIVE_UNITS PASS");
    return 0;
}
catch (std::exception const & error)
{
    std::fprintf(stderr, "DIRECT_RECEIVE_UNITS FAIL: %s\n", error.what());
    return 1;
}
