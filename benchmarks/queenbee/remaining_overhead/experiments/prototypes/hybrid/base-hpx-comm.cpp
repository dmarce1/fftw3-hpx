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

#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <exception>
#include <functional>
#include <limits>
#include <memory>
#include <mutex>
#include <numeric>
#include <stddef.h>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <hpx/collectives/all_gather.hpp>
#include <hpx/collectives/all_reduce.hpp>
#include <hpx/collectives/all_to_all.hpp>
#include <hpx/collectives/broadcast.hpp>
#include <hpx/collectives/channel_communicator.hpp>
#include <hpx/collectives/create_communicator.hpp>
#include <hpx/executors/parallel_executor.hpp>
#include <hpx/hpx_finalize.hpp>
#include <hpx/include/async.hpp>
#include <hpx/include/lcos.hpp>
#include <hpx/include/runtime.hpp>
#include <hpx/include/threads.hpp>
#include <hpx/runtime_local/run_as_hpx_thread.hpp>
#include <hpx/serialization/serialize_buffer.hpp>
#include <hpx/serialization/vector.hpp>

#include "config.h"
#include "hpx-comm.h"

#if defined(FFTW_SINGLE)
namespace fftwf_hpx_pool_transport
#elif defined(FFTW_LDOUBLE)
namespace fftwl_hpx_pool_transport
#else
namespace fftw_hpx_pool_transport
#endif
{
// Experimental receive allocation cache. Each precision owns a separate pool
// and retains at most one idle block, no larger than its largest returned block.
// Blocks still owned by a Message are never available for reuse.
struct ReceivePool
{
    size_t const epoch;

    explicit ReceivePool(size_t const value) : epoch(value)
    {
    }

    ~ReceivePool()
    {
        delete[] cached;
    }

    char * allocate(size_t const bytes)
    {
        if (bytes != 0)
        {
            std::lock_guard<std::mutex> const lock(mutex);
            if (active && cached != nullptr && cachedBytes == bytes)
            {
                char * const result = cached;
                cached = nullptr;
                cachedBytes = 0;
                return result;
            }
        }
        // A miss never waits for an outstanding Message to release a block.
        return new char[bytes];
    }

    void deallocate(char * data, size_t const bytes) noexcept
    {
        if (bytes != 0)
        {
            std::lock_guard<std::mutex> const lock(mutex);
            if (active && (cached == nullptr || bytes > cachedBytes))
            {
                std::swap(data, cached);
                cachedBytes = bytes;
            }
        }
        // Potentially expensive heap release never holds the pool mutex.
        delete[] data;
    }

    void disable() noexcept
    {
        char * discarded = nullptr;
        {
            std::lock_guard<std::mutex> const lock(mutex);
            active = false;
            std::swap(discarded, cached);
            cachedBytes = 0;
        }
        delete[] discarded;
    }

private:
    std::mutex mutex;
    char * cached = nullptr;
    size_t cachedBytes = 0;
    bool active = true;
};

struct ReceivePoolRegistry
{
    std::mutex mutex;
    std::shared_ptr<ReceivePool> current;
};

ReceivePoolRegistry & receivePoolRegistry()
{
    static ReceivePoolRegistry registry;
    return registry;
}

std::shared_ptr<ReceivePool> currentReceivePool()
{
    auto & registry = receivePoolRegistry();
    std::lock_guard<std::mutex> const lock(registry.mutex);
    return registry.current;
}

std::shared_ptr<ReceivePool> receivePoolForEpoch(size_t const epoch)
{
    auto pool = currentReceivePool();
    return pool && pool->epoch == epoch ? pool : nullptr;
}

void startReceivePool(size_t const epoch)
{
    auto pool = std::make_shared<ReceivePool>(epoch);
    auto & registry = receivePoolRegistry();
    std::lock_guard<std::mutex> const lock(registry.mutex);
    assert(!registry.current);
    registry.current = std::move(pool);
}

void stopReceivePool()
{
    std::shared_ptr<ReceivePool> previous;
    {
        auto & registry = receivePoolRegistry();
        std::lock_guard<std::mutex> const lock(registry.mutex);
        previous = std::move(registry.current);
    }
    if (previous)
    {
        // Outstanding allocators retain this disabled epoch. Their late
        // deallocations go to the heap instead of refilling any cache.
        previous->disable();
    }
}

class ReceiveAllocator
{
public:
    using value_type = char;

    ReceiveAllocator() : pool(currentReceivePool()), epoch(pool ? pool->epoch : 0)
    {
    }

    char * allocate(size_t const bytes)
    {
        return pool ? pool->allocate(bytes) : new char[bytes];
    }

    void deallocate(char * const data, size_t const bytes) noexcept
    {
        if (pool)
        {
            pool->deallocate(data, bytes);
        }
        else
        {
            delete[] data;
        }
    }

    bool operator==(ReceiveAllocator const & other) const noexcept
    {
        return pool == other.pool;
    }

    bool operator!=(ReceiveAllocator const & other) const noexcept
    {
        return !(*this == other);
    }

private:
    friend class hpx::serialization::access;

    template <typename Archive>
    void save(Archive & archive, unsigned int const) const
    {
        // Never send a pointer or an allocator's process-local shared state.
        archive << epoch;
    }

    template <typename Archive>
    void load(Archive & archive, unsigned int const)
    {
        archive >> epoch;
        // A delayed old-epoch parcel must not repopulate a newer pool.
        pool = receivePoolForEpoch(epoch);
    }

    HPX_SERIALIZATION_SPLIT_MEMBER()

    std::shared_ptr<ReceivePool> pool;
    size_t epoch;
};

} // namespace: unique transport types for each precision

namespace
{
#if defined(FFTW_SINGLE)
namespace pool_transport = fftwf_hpx_pool_transport;
#elif defined(FFTW_LDOUBLE)
namespace pool_transport = fftwl_hpx_pool_transport;
#else
namespace pool_transport = fftw_hpx_pool_transport;
#endif
using Bytes = std::vector<char>;
using Message =
    hpx::serialization::serialize_buffer<char, pool_transport::ReceiveAllocator>;
namespace collectives = hpx::collectives;

#if defined(FFTW_SINGLE)
char const precisionPrefix[] = "fftwf_hpx";
#elif defined(FFTW_LDOUBLE)
char const precisionPrefix[] = "fftwl_hpx";
#else
char const precisionPrefix[] = "fftw_hpx";
#endif

[[noreturn]] void terminateBridge()
{
    try
    {
        throw;
    }
    catch (std::exception const & error)
    {
        std::fprintf(stderr, "%s communication failure: %s\n", precisionPrefix,
                     error.what());
    }
    catch (...)
    {
        std::fprintf(stderr, "%s communication failure\n", precisionPrefix);
    }
    hpx::terminate();
}

struct Group
{
    std::string basename;
    int rank;
    int size;
    std::vector<int> members;
    collectives::communicator collective;
    collectives::channel_communicator channel;
    size_t generation = 0;
    size_t splitCounter = 0;
    std::vector<size_t> sendSequence;
    std::vector<size_t> receiveSequence;

    Group(std::string name, int const localRank, std::vector<int> worldMembers)
        : basename(std::move(name)), rank(localRank),
          size(static_cast<int>(worldMembers.size())),
          members(std::move(worldMembers)),
          sendSequence(static_cast<size_t>(size), 0),
          receiveSequence(static_cast<size_t>(size), 0)
    {
        if (size > 1)
        {
            collective = collectives::create_communicator(
                (basename + "/collective").c_str(),
                collectives::num_sites_arg(size),
                collectives::this_site_arg(rank));
        }
        channel = collectives::create_channel_communicator(
            hpx::launch::sync, (basename + "/channel").c_str(),
            collectives::num_sites_arg(size),
            collectives::this_site_arg(rank));
    }

    collectives::generation_arg nextGeneration()
    {
        assert(generation < std::numeric_limits<size_t>::max());
        return collectives::generation_arg(++generation);
    }
};
} // namespace

struct fftw_hpx_comm_s
{
    std::shared_ptr<void> group;
};

namespace
{
std::unique_ptr<fftw_hpx_comm_s> world;
std::unordered_map<std::string, std::shared_ptr<Group>> splitGroups;
size_t worldEpoch = 0;

Group & groupOf(fftw_hpx_comm const comm)
{
    assert(comm != nullptr && comm->group);
    return *static_cast<Group *>(comm->group.get());
}

size_t byteCount(size_t const count, size_t const elementSize)
{
    assert(elementSize == 0 ||
           count <= std::numeric_limits<size_t>::max() / elementSize);
    return count * elementSize;
}

Bytes copyBytes(void const * const data, size_t const bytes)
{
    Bytes result(bytes);
    if (bytes != 0)
    {
        assert(data != nullptr);
        std::memcpy(result.data(), data, bytes);
    }
    return result;
}

Message messageBytes(Group const & group, int const destination,
                     void const * const data, size_t const bytes)
{
    if (bytes == 0)
    {
        return Message();
    }
    assert(data != nullptr);
    // channel_communicator::set completes after the destination action stores
    // its payload. Remote serialization has then finished reading the source;
    // a local action instead retains the object, so self-sends need ownership.
    return Message(static_cast<char const *>(data), bytes,
                   destination == group.rank ? Message::copy
                                             : Message::reference);
}

template <typename Payload>
void receiveBytes(void * const data, size_t const bytes, Payload const & payload)
{
    assert(payload.size() == bytes);
    if (bytes != 0)
    {
        assert(data != nullptr);
        std::memcpy(data, payload.data(), bytes);
    }
}

void const * offsetBytes(void const * const data, size_t const bytes)
{
    return bytes == 0 ? data : static_cast<char const *>(data) + bytes;
}

void * offsetBytes(void * const data, size_t const bytes)
{
    return bytes == 0 ? data : static_cast<char *>(data) + bytes;
}

size_t messageTag(Group & group, int const peer, int const tag,
                  bool const sending)
{
    assert(peer >= 0 && peer < group.size);
    assert(tag >= 0 && tag <= 0x7fff);
    size_t & sequence =
        sending ? group.sendSequence[peer] : group.receiveSequence[peer];
    assert(sequence <= (std::numeric_limits<size_t>::max() >> 15));
    return (sequence++ << 15) | static_cast<size_t>(tag);
}

template <typename T> std::vector<T> gatherAll(Group & group, T value)
{
    if (group.size == 1)
    {
        return {std::move(value)};
    }
    return collectives::all_gather(
        hpx::launch::sync, group.collective, std::move(value),
        collectives::this_site_arg(group.rank), group.nextGeneration());
}

std::vector<Bytes> exchangeAll(Group & group, std::vector<Bytes> blocks)
{
    if (group.size == 1)
    {
        return blocks;
    }
    return collectives::all_to_all(
        hpx::launch::sync, group.collective, std::move(blocks),
        collectives::this_site_arg(group.rank), group.nextGeneration());
}

void runJobs(void * (*work)(char *), char * const jobData,
             size_t const elementSize, int const jobCount)
{
    hpx::execution::parallel_executor const executor(
        hpx::threads::thread_stacksize::large);
    std::vector<hpx::future<void>> futures;
    futures.reserve(static_cast<size_t>(jobCount - 1));
    for (int job = 0; job < jobCount - 1; ++job)
    {
        char * const data = jobData + static_cast<size_t>(job) * elementSize;
        futures.push_back(hpx::async(executor, [work, data] { work(data); }));
    }
    work(jobData + static_cast<size_t>(jobCount - 1) * elementSize);
    hpx::wait_all(futures);
}
} // namespace

extern "C" void FFTW_HPX_COMM_FN(comm_init)(void)
try
{
    if (!world)
    {
        int const rank = static_cast<int>(hpx::get_locality_id());
        int const size =
            static_cast<int>(hpx::get_num_localities(hpx::launch::sync));
        std::vector<int> members(static_cast<size_t>(size));
        std::iota(members.begin(), members.end(), 0);
        // A locality may finish cleanup and initialize again before another
        // locality releases its old registered communicator. Give each SPMD
        // initialization a fresh name so lookup cannot attach to the old group.
        assert(worldEpoch < std::numeric_limits<size_t>::max());
        std::string const basename = std::string(precisionPrefix) + "/world/e" +
            std::to_string(++worldEpoch);
        pool_transport::startReceivePool(worldEpoch);
        world = std::make_unique<fftw_hpx_comm_s>();
        world->group = std::make_shared<Group>(basename, rank, std::move(members));
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_cleanup)(void)
try
{
    pool_transport::stopReceivePool();
    splitGroups.clear();
    world.reset();
}
catch (...)
{
    terminateBridge();
}

extern "C" fftw_hpx_comm FFTW_HPX_COMM_FN(comm_world)(void)
try
{
    assert(world);
    return world.get();
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_rank)(fftw_hpx_comm const comm,
                                            int * const rank)
try
{
    *rank = groupOf(comm).rank;
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_size)(fftw_hpx_comm const comm,
                                            int * const size)
try
{
    *size = groupOf(comm).size;
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_dup)(fftw_hpx_comm const comm,
                                           fftw_hpx_comm * const duplicate)
try
{
    *duplicate = new fftw_hpx_comm_s{comm->group};
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_free)(fftw_hpx_comm * const comm)
try
{
    assert(*comm != world.get());
    delete *comm;
    *comm = FFTW_HPX_COMM_NULL;
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(comm_split)(fftw_hpx_comm const comm,
                                             int const color, int const key,
                                             fftw_hpx_comm * const result)
try
{
    Group & parent = groupOf(comm);
    auto const all = gatherAll(parent, std::vector<int>{color, key});
    ++parent.splitCounter;
    std::vector<int> selected;
    for (int rank = 0; rank < parent.size; ++rank)
    {
        if (all[rank][0] == color)
        {
            selected.push_back(rank);
        }
    }
    std::sort(selected.begin(), selected.end(),
              [&all](int const left, int const right)
              {
                  return all[left][1] < all[right][1] ||
                         (all[left][1] == all[right][1] && left < right);
              });
    std::vector<int> members;
    int newRank = -1;
    std::string cacheKey = parent.basename + "/c" + std::to_string(color) + "/";
    std::uint64_t hash = UINT64_C(14695981039346656037);
    for (size_t rank = 0; rank < selected.size(); ++rank)
    {
        int const worldRank = parent.members[selected[rank]];
        members.push_back(worldRank);
        cacheKey += std::to_string(worldRank) + ",";
        for (unsigned int byte = 0; byte < 4; ++byte)
        {
            hash ^=
                (static_cast<std::uint32_t>(worldRank) >> (8 * byte)) & 0xff;
            hash *= UINT64_C(1099511628211);
        }
        if (selected[rank] == parent.rank)
        {
            newRank = static_cast<int>(rank);
        }
    }
    assert(newRank >= 0);
    auto found = splitGroups.find(cacheKey);
    if (found == splitGroups.end())
    {
        std::string const basename = parent.basename + "/c" +
                                     std::to_string(color) + "/" +
                                     std::to_string(hash);
        found =
            splitGroups
                .emplace(cacheKey, std::make_shared<Group>(basename, newRank,
                                                           std::move(members)))
                .first;
    }
    *result = new fftw_hpx_comm_s{found->second};
}
catch (...)
{
    terminateBridge();
}

extern "C" int FFTW_HPX_COMM_FN(allreduce_int)(int const value,
                                               int const operation,
                                               fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    assert(operation == FFTW_HPX_LOR || operation == FFTW_HPX_LAND);
    if (group.size == 1)
    {
        return value != 0;
    }
    if (operation == FFTW_HPX_LOR)
    {
        return collectives::all_reduce(hpx::launch::sync, group.collective,
                                       value, std::logical_or<>{},
                                       collectives::this_site_arg(group.rank),
                                       group.nextGeneration()) != 0;
    }
    return collectives::all_reduce(hpx::launch::sync, group.collective, value,
                                   std::logical_and<>{},
                                   collectives::this_site_arg(group.rank),
                                   group.nextGeneration()) != 0;
}
catch (...)
{
    terminateBridge();
}

extern "C" double FFTW_HPX_COMM_FN(allreduce_double)(double const value,
                                                     int const operation,
                                                     fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    assert(operation == FFTW_HPX_SUM || operation == FFTW_HPX_MAX);
    if (group.size == 1)
    {
        return value;
    }
    if (operation == FFTW_HPX_SUM)
    {
        return collectives::all_reduce(
            hpx::launch::sync, group.collective, value, std::plus<>{},
            collectives::this_site_arg(group.rank), group.nextGeneration());
    }
    return collectives::all_reduce(
        hpx::launch::sync, group.collective, value,
        [](double const left, double const right)
        { return std::max(left, right); },
        collectives::this_site_arg(group.rank), group.nextGeneration());
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(bcast)(void * const data, size_t const count,
                                        size_t const elementSize,
                                        int const root,
                                        fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    assert(root == 0);
    if (group.size == 1)
    {
        return;
    }
    size_t const bytes = byteCount(count, elementSize);
    auto const generation = group.nextGeneration();
    if (group.rank == root)
    {
        collectives::broadcast_to(
            hpx::launch::sync, group.collective, copyBytes(data, bytes),
            collectives::this_site_arg(group.rank), generation);
    }
    else
    {
        receiveBytes(data, bytes,
                     collectives::broadcast_from<Bytes>(
                         hpx::launch::sync, group.collective,
                         collectives::this_site_arg(group.rank), generation));
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void
FFTW_HPX_COMM_FN(alltoall)(void const * const sendData, size_t const sendCount,
                           size_t const sendSize, void * const receiveData,
                           size_t const receiveCount, size_t const receiveSize,
                           fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    size_t const sendBytes = byteCount(sendCount, sendSize);
    size_t const receiveBytesCount = byteCount(receiveCount, receiveSize);
    std::vector<Bytes> blocks;
    blocks.reserve(static_cast<size_t>(group.size));
    for (int peer = 0; peer < group.size; ++peer)
    {
        blocks.push_back(copyBytes(
            offsetBytes(sendData, byteCount(peer, sendBytes)), sendBytes));
    }
    blocks = exchangeAll(group, std::move(blocks));
    for (int peer = 0; peer < group.size; ++peer)
    {
        receiveBytes(
            offsetBytes(receiveData, byteCount(peer, receiveBytesCount)),
            receiveBytesCount, blocks[peer]);
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(alltoallv)(
    void const * const sendData, int const * const sendCounts,
    int const * const sendOffsets, size_t const sendSize,
    void * const receiveData, int const * const receiveCounts,
    int const * const receiveOffsets, size_t const receiveSize,
    fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    std::vector<Bytes> blocks;
    blocks.reserve(static_cast<size_t>(group.size));
    for (int peer = 0; peer < group.size; ++peer)
    {
        assert(sendCounts[peer] >= 0 && sendOffsets[peer] >= 0);
        blocks.push_back(copyBytes(
            offsetBytes(sendData, byteCount(sendOffsets[peer], sendSize)),
            byteCount(sendCounts[peer], sendSize)));
    }
    blocks = exchangeAll(group, std::move(blocks));
    for (int peer = 0; peer < group.size; ++peer)
    {
        assert(receiveCounts[peer] >= 0 && receiveOffsets[peer] >= 0);
        receiveBytes(offsetBytes(receiveData,
                                 byteCount(receiveOffsets[peer], receiveSize)),
                     byteCount(receiveCounts[peer], receiveSize), blocks[peer]);
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(send)(void const * const data,
                                       size_t const count,
                                       size_t const elementSize,
                                       int const destination, int const tag,
                                       fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    collectives::set(
        group.channel, collectives::that_site_arg(destination),
        messageBytes(group, destination, data, byteCount(count, elementSize)),
        collectives::tag_arg(messageTag(group, destination, tag, true)))
        .get();
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(recv)(void * const data, size_t const count,
                                       size_t const elementSize,
                                       int const source, int const tag,
                                       fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    receiveBytes(
        data, byteCount(count, elementSize),
        collectives::get<Message>(
            group.channel, collectives::that_site_arg(source),
            collectives::tag_arg(messageTag(group, source, tag, false)))
            .get());
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(sendrecv)(
    void const * const sendData, size_t const sendCount, size_t const sendSize,
    int const destination, int const sendTag, void * const receiveData,
    size_t const receiveCount, size_t const receiveSize, int const source,
    int const receiveTag, fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    auto sent = collectives::set(
        group.channel, collectives::that_site_arg(destination),
        messageBytes(group, destination, sendData,
                     byteCount(sendCount, sendSize)),
        collectives::tag_arg(messageTag(group, destination, sendTag, true)));
    auto const incoming = collectives::get<Message>(
        group.channel, collectives::that_site_arg(source),
        collectives::tag_arg(messageTag(group, source, receiveTag, false)))
                              .get();
    // The channel returns serialize_buffer with shared ownership, avoiding
    // its by-value get<T> deep copy of vector payloads. Finish the referenced
    // send before writing a receive buffer that may overlap the source.
    sent.get();
    receiveBytes(receiveData, byteCount(receiveCount, receiveSize), incoming);
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(abort)(fftw_hpx_comm, int)
try
{
    hpx::terminate();
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(parallel_loop)(void * (*work)(char *),
                                                char * const jobData,
                                                size_t const elementSize,
                                                int const jobCount, void *)
try
{
    if (jobCount <= 0)
    {
        return;
    }
    if (hpx::threads::get_self_ptr() == nullptr)
    {
        hpx::run_as_hpx_thread(
            [&]
            {
                hpx::execution::parallel_executor const executor(
                    hpx::threads::thread_stacksize::large);
                hpx::async(executor, [&]
                           { runJobs(work, jobData, elementSize, jobCount); })
                    .get();
            });
        return;
    }
    runJobs(work, jobData, elementSize, jobCount);
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(bench_gather)(
    void const * const sendData, size_t const sendCount, size_t const sendSize,
    void * const receiveData, size_t const receiveCount,
    size_t const receiveSize, int const root, fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    auto const blocks =
        gatherAll(group, copyBytes(sendData, byteCount(sendCount, sendSize)));
    if (group.rank == root)
    {
        size_t const bytes = byteCount(receiveCount, receiveSize);
        for (int peer = 0; peer < group.size; ++peer)
        {
            receiveBytes(offsetBytes(receiveData, byteCount(peer, bytes)),
                         bytes, blocks[peer]);
        }
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(bench_gatherv)(
    void const * const sendData, size_t const sendCount, size_t const sendSize,
    void * const receiveData, int const * const receiveCounts,
    int const * const receiveOffsets, size_t const receiveSize, int const root,
    fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    auto const blocks =
        gatherAll(group, copyBytes(sendData, byteCount(sendCount, sendSize)));
    if (group.rank == root)
    {
        for (int peer = 0; peer < group.size; ++peer)
        {
            assert(receiveCounts[peer] >= 0 && receiveOffsets[peer] >= 0);
            receiveBytes(
                offsetBytes(receiveData,
                            byteCount(receiveOffsets[peer], receiveSize)),
                byteCount(receiveCounts[peer], receiveSize), blocks[peer]);
        }
    }
}
catch (...)
{
    terminateBridge();
}

extern "C" void FFTW_HPX_COMM_FN(bench_scatterv)(
    void const * const sendData, int const * const sendCounts,
    int const * const sendOffsets, size_t const sendSize,
    void * const receiveData, size_t const receiveCount,
    size_t const receiveSize, int const root, fftw_hpx_comm const comm)
try
{
    Group & group = groupOf(comm);
    std::vector<Bytes> outgoing;
    if (group.rank == root)
    {
        outgoing.reserve(static_cast<size_t>(group.size));
        for (int peer = 0; peer < group.size; ++peer)
        {
            assert(sendCounts[peer] >= 0 && sendOffsets[peer] >= 0);
            outgoing.push_back(copyBytes(
                offsetBytes(sendData, byteCount(sendOffsets[peer], sendSize)),
                byteCount(sendCounts[peer], sendSize)));
        }
    }
    auto const blocks = gatherAll(group, std::move(outgoing));
    receiveBytes(receiveData, byteCount(receiveCount, receiveSize),
                 blocks[root][group.rank]);
}
catch (...)
{
    terminateBridge();
}
