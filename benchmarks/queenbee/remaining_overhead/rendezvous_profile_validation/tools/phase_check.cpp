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

#include <cassert>
#include <cstdio>
#include <stdexcept>

#include "remaining_profile.cpp"

#ifdef NDEBUG
#error "Diagnostic recorder checks require active assertions"
#endif

namespace
{
unsigned long long count(int const metric)
{
    return counters[static_cast<size_t>(metric)].calls.load();
}
unsigned long long duration(int const metric)
{
    return counters[static_cast<size_t>(metric)].ns.load();
}
void checkCoverage()
{
    unsigned long long sum = 0;
    for (int const metric : {FRP_POST_ANNOUNCE, FRP_READY_WAIT, FRP_SEND_INIT,
             FRP_RECV_WAIT, FRP_SEND_WAIT, FRP_RECEIVE_FINISH,
             FRP_ANNOUNCE_WAIT, FRP_EXCHANGE_REST})
    {
        sum += duration(metric);
    }
    assert(sum == duration(FRP_EXCHANGE));
    assert(scopes.load() == 0);
}
struct DestroyMarker
{
    bool & destroyed;
    ~DestroyMarker() noexcept
    {
        assert(scopes.load() == 1);
        destroyed = true;
    }
};
}

int main()
{
    {
        FrpPhases inactive(FRP_EXCHANGE, FRP_EXCHANGE_REST, 3);
        inactive.next(FRP_RECV_WAIT);
    }
    assert(count(FRP_EXCHANGE) == 0);
    assert(scopes.load() == 0);
    frp_reset();
    bool destroyed = false;
    {
        FrpPhases phases(FRP_EXCHANGE, FRP_EXCHANGE_REST, 17);
        DestroyMarker marker{destroyed};
        for (int const metric : {FRP_POST_ANNOUNCE, FRP_READY_WAIT, FRP_SEND_INIT,
                 FRP_RECV_WAIT, FRP_SEND_WAIT, FRP_RECEIVE_FINISH,
                 FRP_ANNOUNCE_WAIT, FRP_EXCHANGE_REST})
        {
            phases.next(metric);
        }
    }
    assert(destroyed);
    assert(count(FRP_EXCHANGE) == 1);
    assert(count(FRP_EXCHANGE_REST) == 2);
    assert(counters[FRP_EXCHANGE].bytes.load() == 17);
    checkCoverage();
    frp_reset();
    destroyed = false;
    try
    {
        FrpPhases phases(FRP_EXCHANGE, FRP_EXCHANGE_REST);
        DestroyMarker marker{destroyed};
        phases.next(FRP_READY_WAIT);
        throw std::runtime_error("expected unit-test unwind");
    }
    catch (std::runtime_error const &)
    {
    }
    assert(destroyed);
    assert(count(FRP_EXCHANGE) == 1);
    checkCoverage();
    active.store(false);
    {
        FrpPhases inactive(FRP_EXCHANGE, FRP_EXCHANGE_REST);
    }
    assert(count(FRP_EXCHANGE) == 1);
    std::puts("PHASE_RECORDER_CHECK PASS inactive exact_coverage destructor_order exception_unwind");
}
