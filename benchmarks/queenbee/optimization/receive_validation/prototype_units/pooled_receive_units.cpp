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

#include <cstdio>
#include <exception>
#include <memory>
#include <vector>

#include "archive_helpers.hpp"
#include "../pooled_receive/hpx-comm.cpp"

namespace
{
using namespace prototype_units;

std::vector<char> wireFor(std::vector<char> const & source)
{
    return encode(Message(source.data(), source.size(), Message::reference));
}

void checkLastOwnerAndExactReuse()
{
    pool_transport::startReceivePool(101);
    {
        auto const expected = payload(257, 1);
        auto const wire = wireFor(expected);
        auto first = decode<Message>(wire);
        auto held = first;
        auto const firstAddress = first.data();
        first = Message();
        auto competing = decode<Message>(wire);
        require(competing.data() != firstAddress,
                "pool recycled storage while a shared Message still owned it");
        requirePayload(held, expected);
        held = Message();
        auto recycled = decode<Message>(wire);
        require(recycled.data() == firstAddress,
                "exact-size allocation did not reuse the last-owner-released block");
        requirePayload(recycled, expected);
        requirePayload(competing, expected);
        auto const competingAddress = competing.data();
        competing = Message();
        recycled = Message();
        auto const equalSize = decode<Message>(wire);
        require(equalSize.data() == competingAddress,
                "equal-size return replaced the already cached block");
        requirePayload(equalSize, expected);
    }
    pool_transport::stopReceivePool();
    pass("last_shared_owner_controls_recycling_exact_hit_live_miss_equal_size_return");
}

void checkRetainedLargest()
{
    pool_transport::startReceivePool(102);
    {
        auto const smallPayload = payload(127, 2);
        auto const largePayload = payload(509, 3);
        auto const smallWire = wireFor(smallPayload);
        auto const largeWire = wireFor(largePayload);
        auto large = decode<Message>(largeWire);
        auto const largeAddress = large.data();
        large = Message();
        auto small = decode<Message>(smallWire);
        require(small.data() != largeAddress,
                "different-sized allocation consumed the cached large block");
        requirePayload(small, smallPayload);
        small = Message();
        auto againLarge = decode<Message>(largeWire);
        require(againLarge.data() == largeAddress,
                "smaller return evicted the larger idle block");
        requirePayload(againLarge, largePayload);
        auto anotherSmall = decode<Message>(smallWire);
        anotherSmall = Message();
        againLarge = Message();
        auto const largestReturned = decode<Message>(largeWire);
        require(largestReturned.data() == largeAddress,
                "larger return did not replace the smaller cached block");
        requirePayload(largestReturned, largePayload);
    }
    pool_transport::stopReceivePool();
    pass("exact_size_only_and_larger_block_retention_replacement");
}

void checkCleanupWithLateOwners()
{
    pool_transport::startReceivePool(103);
    auto const oldPayload = payload(4093, 4);
    auto const oldWire = wireFor(oldPayload);
    auto lateOwner = decode<Message>(oldWire);
    std::weak_ptr<pool_transport::ReceivePool> oldPool =
        pool_transport::currentReceivePool();
    pool_transport::stopReceivePool();
    require(!pool_transport::currentReceivePool(), "cleanup left an active pool");
    require(!oldPool.expired(), "cleanup destroyed pool still owned by a Message");
    requirePayload(lateOwner, oldPayload);

    pool_transport::startReceivePool(104);
    {
        auto const newPayload = payload(251, 5);
        auto const newWire = wireFor(newPayload);
        auto seed = decode<Message>(newWire);
        auto const newAddress = seed.data();
        seed = Message();
        lateOwner = Message();
        require(oldPool.expired(), "old pool remained alive after its last owner left");
        auto newHit = decode<Message>(newWire);
        require(newHit.data() == newAddress,
                "late old-epoch release replaced the new epoch's cache");
        requirePayload(newHit, newPayload);
        newHit = Message();
        {
            auto const delayedOldParcel = decode<Message>(oldWire);
            requirePayload(delayedOldParcel, oldPayload);
            require(delayedOldParcel.data() != newAddress,
                    "old-epoch parcel took the new epoch's idle block");
        }
        auto const preserved = decode<Message>(newWire);
        require(preserved.data() == newAddress,
                "late old-epoch parcel release replaced the new epoch's cache");
        requirePayload(preserved, newPayload);
    }
    pool_transport::stopReceivePool();
    pass("cleanup_preserves_live_storage_and_late_owners_parcels_cannot_refill_new_pool");
}

void checkEmptyAndSelfCopy()
{
    pool_transport::startReceivePool(105);
    {
        auto source = payload(67, 6);
        auto const expected = source;
        Message self(source.data(), source.size(), Message::copy);
        std::fill(source.begin(), source.end(), 0);
        requirePayload(self, expected);
        auto const emptyWire = encode(Message());
        auto const empty = decode<Message>(emptyWire);
        require(empty.size() == 0, "empty roundtrip gained a payload");
        requirePayload(self, expected);
        auto const selfAddress = self.data();
        self = Message();
        auto const reused = decode<Message>(wireFor(expected));
        require(reused.data() == selfAddress,
                "zero-byte Message interfered with nonempty cache reuse");
        requirePayload(reused, expected);
    }
    pool_transport::stopReceivePool();
    pass("self_copy_independence_and_zero_size_cache_exclusion");
}
} // namespace

int main()
try
{
    checkLastOwnerAndExactReuse();
    checkRetainedLargest();
    checkCleanupWithLateOwners();
    checkEmptyAndSelfCopy();
    std::puts("POOLED_RECEIVE_UNITS PASS");
    return 0;
}
catch (std::exception const & error)
{
    std::fprintf(stderr, "POOLED_RECEIVE_UNITS FAIL: %s\n", error.what());
    return 1;
}
