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
 */

#include <array>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <stddef.h>
#include <vector>

#include <hpx/async.hpp>
#include <hpx/executors/parallel_executor.hpp>
#include <hpx/hpx_init.hpp>
#include <hpx/include/threads.hpp>
#include <hpx/threading_base/thread_data.hpp>

#include "config.h"
#include "hpx-comm.h"

#ifdef NDEBUG
#error The HPX communication check requires assertions enabled; compile with -UNDEBUG last
#endif

namespace
{
void stage(int const rank, int const cycle, char const * const description)
{
    if (rank == 0)
    {
        std::printf("communication check, cycle %d: %s\n", cycle, description);
        std::fflush(stdout);
    }
}

void checkDuplicates(fftw_hpx_comm const world, int const rank, int const size)
{
    for (int iteration = 0; iteration < 16; ++iteration)
    {
        fftw_hpx_comm first = FFTW_HPX_COMM_NULL;
        fftw_hpx_comm second = FFTW_HPX_COMM_NULL;
        FFTW_HPX_COMM_FN(comm_dup)(world, &first);
        FFTW_HPX_COMM_FN(comm_dup)(first, &second);
        fftw_hpx_comm const chosen = rank % 2 == 0 ? first : second;
        double const total = FFTW_HPX_COMM_FN(allreduce_double)(
            rank + iteration, FFTW_HPX_SUM, chosen);
        assert(total == size * iteration + size * (size - 1) / 2);
        assert(FFTW_HPX_COMM_FN(allreduce_int)(rank == 0, FFTW_HPX_LOR,
                                               rank % 2 == 0 ? world
                                                             : chosen) == 1);
        assert(FFTW_HPX_COMM_FN(allreduce_int)(rank < size, FFTW_HPX_LAND,
                                               second) == 1);
        int value = rank == 0 ? 413 + iteration : -1;
        FFTW_HPX_COMM_FN(bcast)(&value, 1, sizeof(value), 0, chosen);
        assert(value == 413 + iteration);
        FFTW_HPX_COMM_FN(comm_free)(&first);
        assert(first == FFTW_HPX_COMM_NULL);
        FFTW_HPX_COMM_FN(comm_free)(&second);
        assert(second == FFTW_HPX_COMM_NULL);
    }
}

void checkSplits(fftw_hpx_comm const world, int const rank, int const size)
{
    for (int parity = 0; parity < 2; ++parity)
    {
        int const color = parity ? rank % 2 : 0;
        int const expectedSize = parity ? (size + 1 - color) / 2 : size;
        int const expectedRank =
            parity ? (size - 1 - rank) / 2 : size - 1 - rank;
        fftw_hpx_comm first = FFTW_HPX_COMM_NULL;
        FFTW_HPX_COMM_FN(comm_split)(world, color, -rank, &first);
        for (int iteration = 0; iteration < 8; ++iteration)
        {
            fftw_hpx_comm repeated = FFTW_HPX_COMM_NULL;
            FFTW_HPX_COMM_FN(comm_split)(world, color, -rank, &repeated);
            int actualRank = -1;
            int actualSize = -1;
            FFTW_HPX_COMM_FN(comm_rank)(repeated, &actualRank);
            FFTW_HPX_COMM_FN(comm_size)(repeated, &actualSize);
            assert(actualRank == expectedRank);
            assert(actualSize == expectedSize);
            // Different members deliberately use different handles. Their
            // collective generation is shared only when the split cache is
            // used.
            fftw_hpx_comm const selected =
                actualRank % 2 == 0 ? first : repeated;
            double const total = FFTW_HPX_COMM_FN(allreduce_double)(
                actualRank + iteration, FFTW_HPX_SUM, selected);
            assert(total == expectedSize * iteration +
                                expectedSize * (expectedSize - 1) / 2);
            int const sent = actualRank + iteration * 100;
            int received = -1;
            int const source = (actualRank + expectedSize - 1) % expectedSize;
            FFTW_HPX_COMM_FN(sendrecv)(&sent, 1, sizeof(int),
                (actualRank + 1) % expectedSize, 76, &received, 1,
                sizeof(int), source, 76, selected);
            assert(received == source + iteration * 100);
            FFTW_HPX_COMM_FN(comm_free)(&repeated);
        }
        FFTW_HPX_COMM_FN(comm_free)(&first);
    }
}

void checkMessages(fftw_hpx_comm const world, int const rank, int const size,
                   int const cycle)
{
    fftw_hpx_comm duplicate = FFTW_HPX_COMM_NULL;
    FFTW_HPX_COMM_FN(comm_dup)(world, &duplicate);
    int const destination = (rank + 1) % size;
    int const source = (rank + size - 1) % size;
    for (int iteration = 0; iteration < 32; ++iteration)
    {
        std::array<int, 4> const sent = {cycle, iteration, rank,
                                         3127 + iteration};
        std::array<int, 4> received = {-1, -1, -1, -1};
        fftw_hpx_comm const comm = iteration % 2 == 0 ? world : duplicate;
        FFTW_HPX_COMM_FN(sendrecv)(
            sent.data(), sent.size(), sizeof(int), destination, 71,
            received.data(), received.size(), sizeof(int), source, 71, comm);
        assert(received[0] == cycle);
        assert(received[1] == iteration);
        assert(received[2] == source);
        assert(received[3] == 3127 + iteration);
        // Empty messages still participate in the same per-peer sequence.
        FFTW_HPX_COMM_FN(sendrecv)(nullptr, 0, 1, destination, 71, nullptr, 0,
                                   1, source, 71, comm);
    }
    FFTW_HPX_COMM_FN(comm_free)(&duplicate);
}

void checkMessageLifetime(fftw_hpx_comm const world, int const rank,
                          int const size)
{
    size_t constexpr count = 32768;
    std::vector<int> data(count);
    std::vector<int> received(count, -1);
    for (size_t index = 0; index < count; ++index)
    {
        data[index] = rank * 100003 + static_cast<int>(index);
    }
    FFTW_HPX_COMM_FN(send)(data.data(), count, sizeof(int), rank, 72, world);
    for (int & value : data)
    {
        value = -2;
    }
    FFTW_HPX_COMM_FN(recv)(received.data(), count, sizeof(int), rank, 72,
                           world);
    for (size_t index = 0; index < count; ++index)
    {
        assert(received[index] == rank * 100003 + static_cast<int>(index));
    }

    int const destination = (rank + 1) % size;
    int const source = (rank + size - 1) % size;
    for (size_t index = 0; index < count; ++index)
    {
        data[index] = rank * 100003 + static_cast<int>(index);
    }
    // Every sender finishes and reuses its source before posting a receive.
    // A completed send must leave an independent payload at the destination.
    FFTW_HPX_COMM_FN(send)(data.data(), count, sizeof(int), destination, 73,
                           world);
    for (int & value : data)
    {
        value = -3;
    }
    FFTW_HPX_COMM_FN(recv)(received.data(), count, sizeof(int), source, 73,
                           world);
    for (size_t index = 0; index < count; ++index)
    {
        assert(received[index] == source * 100003 + static_cast<int>(index));
    }

    for (size_t const offset : {size_t(0), size_t(17)})
    {
        data.resize(count + offset);
        for (size_t index = 0; index < data.size(); ++index)
        {
            data[index] = rank * 100003 + static_cast<int>(index);
        }
        FFTW_HPX_COMM_FN(sendrecv)(data.data(), count, sizeof(int), destination,
                                   74, data.data() + offset, count, sizeof(int),
                                   source, 74, world);
        for (size_t index = 0; index < count; ++index)
        {
            assert(data[index + offset] ==
                   source * 100003 + static_cast<int>(index));
        }
        for (size_t index = 0; index < offset; ++index)
        {
            assert(data[index] == rank * 100003 + static_cast<int>(index));
        }
    }
}

void checkRendezvousMatching(fftw_hpx_comm const world, int const rank,
                             int const size, int const cycle)
{
    if (size < 2)
    {
        return;
    }
    size_t constexpr count = 32768;
    for (int iteration = 0; iteration < 4; ++iteration)
    {
        for (int mode = 0; mode < 6; ++mode)
        {
            if (rank < 2)
            {
                int const peer = 1 - rank;
                bool const overlap = mode == 2 ? rank == 1 :
                    mode == 3 ? rank == 0 : mode == 4;
                size_t const offset = mode == 4 && rank == 1 ? 17 : 0;
                size_t const sendCount = mode == 5 && rank == 0 ? 0 : count;
                size_t const receiveCount = mode == 5 && rank == 1 ? 0 : count;
                std::vector<int> source(count + offset);
                std::vector<int> destination(count, -1);
                for (size_t index = 0; index < source.size(); ++index)
                {
                    source[index] = cycle * 10000000 + iteration * 1000000 +
                        mode * 100000 + rank * 40000 + static_cast<int>(index);
                }
                int * const target = overlap ? source.data() + offset :
                    destination.data();
                if (rank == 1 && mode == 0)
                {
                    FFTW_HPX_COMM_FN(send)(source.data(), sendCount,
                        sizeof(int), peer, 75, world);
                    FFTW_HPX_COMM_FN(recv)(target, receiveCount,
                        sizeof(int), peer, 75, world);
                }
                else if (rank == 1 && mode == 1)
                {
                    FFTW_HPX_COMM_FN(recv)(target, receiveCount,
                        sizeof(int), peer, 75, world);
                    FFTW_HPX_COMM_FN(send)(source.data(), sendCount,
                        sizeof(int), peer, 75, world);
                }
                else
                {
                    FFTW_HPX_COMM_FN(sendrecv)(source.data(), sendCount,
                        sizeof(int), peer, 75, target, receiveCount,
                        sizeof(int), peer, 75, world);
                }
                for (size_t index = 0; index < receiveCount; ++index)
                {
                    assert(target[index] == cycle * 10000000 +
                        iteration * 1000000 + mode * 100000 + peer * 40000 +
                        static_cast<int>(index));
                }
                for (size_t index = 0; index < offset; ++index)
                {
                    assert(source[index] == cycle * 10000000 +
                        iteration * 1000000 + mode * 100000 + rank * 40000 +
                        static_cast<int>(index));
                }
            }
            assert(FFTW_HPX_COMM_FN(allreduce_int)(1, FFTW_HPX_LAND, world));
        }
    }
}

char payload(int const source, int const destination, int const iteration,
             int const index)
{
    return static_cast<char>(
        (source * 11 + destination * 3 + iteration * 31 + index) % 100 + 1);
}

void checkVariableExchange(fftw_hpx_comm const world, int const rank,
                           int const size)
{
    std::vector<int> sendCounts(static_cast<size_t>(size));
    std::vector<int> receiveCounts(static_cast<size_t>(size));
    std::vector<int> sendOffsets(static_cast<size_t>(size));
    std::vector<int> receiveOffsets(static_cast<size_t>(size));
    for (int iteration = 0; iteration < 8; ++iteration)
    {
        int sendExtent = 0;
        int receiveExtent = 0;
        for (int peer = 0; peer < size; ++peer)
        {
            sendCounts[peer] = (rank + 2 * peer + iteration) % 4;
            receiveCounts[peer] = (peer + 2 * rank + iteration) % 4;
            sendOffsets[peer] = sendExtent;
            receiveOffsets[peer] = receiveExtent;
            sendExtent += sendCounts[peer] + 1;
            receiveExtent += receiveCounts[peer] + 1;
        }
        std::vector<char> sent(static_cast<size_t>(sendExtent), -1);
        std::vector<char> received(static_cast<size_t>(receiveExtent), -1);
        for (int peer = 0; peer < size; ++peer)
        {
            for (int index = 0; index < sendCounts[peer]; ++index)
            {
                sent[sendOffsets[peer] + index] =
                    payload(rank, peer, iteration, index);
            }
        }
        FFTW_HPX_COMM_FN(alltoallv)(sent.data(), sendCounts.data(),
                                    sendOffsets.data(), 1, received.data(),
                                    receiveCounts.data(), receiveOffsets.data(),
                                    1, world);
        for (int peer = 0; peer < size; ++peer)
        {
            for (int index = 0; index < receiveCounts[peer]; ++index)
            {
                assert(received[receiveOffsets[peer] + index] ==
                       payload(peer, rank, iteration, index));
            }
            assert(received[receiveOffsets[peer] + receiveCounts[peer]] == -1);
        }
    }
    std::vector<int> const empty(static_cast<size_t>(size), 0);
    FFTW_HPX_COMM_FN(alltoallv)(nullptr, empty.data(), empty.data(), 1, nullptr,
                                empty.data(), empty.data(), 1, world);
}

void checkTransposeExchange(fftw_hpx_comm const world, int const rank,
                            int const size)
{
    for (int const active : {0, 1, size - 1, size})
    {
        for (int iteration = 0; iteration < 3; ++iteration)
        {
            for (bool const overlap : {false, true})
            {
                auto const count = [iteration](int const source,
                                               int const destination) {
                    return (2 * source + destination + iteration) % 5;
                };
                auto const value = [iteration](int const source,
                                               int const destination,
                                               int const index) {
                    return 100000 * iteration + 1000 * source +
                        10 * destination + index;
                };
                std::vector<ptrdiff_t> sendCounts(active, 0);
                std::vector<ptrdiff_t> sendOffsets(active, 0);
                std::vector<ptrdiff_t> receiveCounts(active, 0);
                std::vector<ptrdiff_t> receiveOffsets(active, 0);
                std::vector<int> source(9 * static_cast<size_t>(active) + 32, -7);
                std::vector<int> destination(source.size(), -9);
                for (int peer = 0; peer < active; ++peer)
                {
                    sendOffsets[peer] = 2 + 7 * (active - 1 - peer);
                    receiveOffsets[peer] = 3 + 9 * peer;
                    if (rank < active)
                    {
                        sendCounts[peer] = count(rank, peer);
                        receiveCounts[peer] = count(peer, rank);
                    }
                    for (int index = 0; index < sendCounts[peer]; ++index)
                    {
                        source[sendOffsets[peer] + index] = value(rank, peer, index);
                    }
                }
                std::vector<int> & target = overlap ? source : destination;
                std::vector<int> expected = target;
                for (int peer = 0; peer < active; ++peer)
                {
                    for (int index = 0; index < receiveCounts[peer]; ++index)
                    {
                        expected[receiveOffsets[peer] + index] = value(peer, rank, index);
                    }
                }
                FFTW_HPX_COMM_FN(transpose_alltoallv)(
                    active == 0 ? nullptr : source.data(), sendCounts.data(),
                    sendOffsets.data(), active == 0 ? nullptr : target.data(),
                    receiveCounts.data(), receiveOffsets.data(), sizeof(int),
                    active, world);
                // Compare untouched gaps too: an in-place receive must not
                // overwrite a later outgoing block before it has been packed.
                assert(target == expected);
            }
        }
    }
}

struct Job
{
    std::atomic<int> calls{0};
    hpx::threads::thread_id_type thread;
    bool nested = false;
};

void * work(char * const data)
{
    Job & job = *reinterpret_cast<Job *>(data);
    ++job.calls;
    job.thread = hpx::threads::get_self_id();
    assert(hpx::threads::get_self_id_data()->get_stack_size_enum() ==
           hpx::threads::thread_stacksize::large);
    if (job.nested)
    {
        std::array<Job, 3> children;
        FFTW_HPX_COMM_FN(parallel_loop)(
            work, reinterpret_cast<char *>(children.data()), sizeof(Job),
            static_cast<int>(children.size()), nullptr);
        for (Job const & child : children)
        {
            assert(child.calls == 1);
        }
        assert(children.back().thread == job.thread);
    }
    return nullptr;
}

void checkThreadCallback()
{
    FFTW_HPX_COMM_FN(parallel_loop)(work, nullptr, sizeof(Job), 0, nullptr);
    std::array<Job, 7> jobs;
    jobs[2].nested = true;
    auto const caller = hpx::threads::get_self_id();
    FFTW_HPX_COMM_FN(parallel_loop)(work, reinterpret_cast<char *>(jobs.data()),
                                    sizeof(Job), static_cast<int>(jobs.size()),
                                    nullptr);
    for (Job const & job : jobs)
    {
        assert(job.calls == 1);
    }
    assert(jobs.back().thread == caller);
    for (size_t index = 0; index + 1 < jobs.size(); ++index)
    {
        assert(jobs[index].thread != caller);
    }
    Job single;
    FFTW_HPX_COMM_FN(parallel_loop)(work, reinterpret_cast<char *>(&single),
                                    sizeof(Job), 1, nullptr);
    assert(single.calls == 1 && single.thread == caller);
}

void checkCommunication()
{
    for (int cycle = 0; cycle < 2; ++cycle)
    {
        FFTW_HPX_COMM_FN(init)();
        fftw_hpx_comm const world = FFTW_HPX_COMM_FN(comm_world)();
        int rank = -1;
        int size = -1;
        FFTW_HPX_COMM_FN(comm_rank)(world, &rank);
        FFTW_HPX_COMM_FN(comm_size)(world, &size);
        assert(rank >= 0 && rank < size);
        stage(rank, cycle, "shared duplicate generations");
        checkDuplicates(world, rank, size);
        stage(rank, cycle, "cached splits with reversed keys");
        checkSplits(world, rank, size);
        stage(rank, cycle, "repeated channel tags and empty messages");
        checkMessages(world, rank, size, cycle);
        stage(rank, cycle, "message ownership and overlapping buffers");
        checkMessageLifetime(world, rank, size);
        stage(rank, cycle, "rendezvous mixed standalone, overlap and directional empty messages");
        checkRendezvousMatching(world, rank, size, cycle);
        stage(rank, cycle, "variable all-to-all byte counts");
        checkVariableExchange(world, rank, size);
        stage(rank, cycle, "wide transpose all-to-all, overlap and inactive ranks");
        checkTransposeExchange(world, rank, size);
        stage(rank, cycle, "thread callback and nested large stacks");
        checkThreadCallback();
        assert(FFTW_HPX_COMM_FN(allreduce_int)(1, FFTW_HPX_LAND, world) == 1);
        stage(rank, cycle, "cleanup");
        FFTW_HPX_COMM_FN(cleanup)();
    }
    std::puts("communication check PASS");
}

int hpxMain(int, char **)
{
    hpx::execution::parallel_executor const executor(
        hpx::threads::thread_stacksize::large);
    hpx::async(executor, checkCommunication).get();
    return hpx::finalize();
}
} // namespace

int main(int argc, char ** argv)
{
    hpx::init_params parameters;
    parameters.cfg = {"hpx.run_hpx_main!=1"};
    return hpx::init(hpxMain, argc, argv, parameters);
}
