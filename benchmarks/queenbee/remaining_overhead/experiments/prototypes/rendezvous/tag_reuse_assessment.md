<!--
Copyright (c) 2026 Dominic C. Marcello

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

-->

# Readiness metadata retention and tag reuse assessment

This is a read-only design assessment; the measured candidate remains unchanged.

HPX commit `c9b81b401fbe6ba4a0306feff71d18ef01c71b34` uses `std::map<size_t, one_element_channel<unique_any_nonser>>` for each peer in `hpx/collectives/detail/channel_communicator.hpp`. Its get/set methods index `channels_[tag]` and never erase the map entry (installed local header lines 54–101, 115–122). Consequently the original data channel retains metadata for completed unique sequence tags, and the new readiness channel adds another retained entry per message until Group/component destruction. Consuming the token releases its value, not the map node. Cached split Groups retain these entries until cleanup.

Replacing the full sequence/tag by only the caller tag, or by a finite cyclic slot, is not a safe general optimization for this bridge. A legal eager pattern sends several messages before posting matching receives. Each current send installs its readiness get before sending data, and does not wait on readiness. Two such operations using one reused slot therefore create concurrent pending pops. The installed `hpx/lcos_local/channel.hpp` lines 363–381 reject the second pending pop with `invalid_status`; a K-slot ring reaches the same failure after K outstanding eager sends. It could become a lost token or a later misassociated readiness because eager paths intentionally discard the unused future.

The queue is not an unlimited buffer in the opposite direction either. `channel.hpp` lines 315–346 allow one queued value and one deferred push, then reject another busy push. A get after a value is available resets the slot, but that is not a guarantee that peers cannot overtake each other. `channel_communicator_server::set` holds its per-peer mutex while calling synchronous `channel.set`, so blocking a second set on slot capacity can also prevent a matching get from acquiring that same mutex. A serialized all-sendrecv experiment might establish a narrow no-overtaking proof, but the general API still includes mixed, overlapping and standalone operations and must not inherit that assumption.

A later design can eliminate retained metadata for completed readiness messages without changing eager send semantics: send a tiny custom HPX readiness action to the source locality, and match it with a local exact-key promise/value registry. Key it by precision, Group basename including epoch, peer and full sequence/tag. Either arrival order is valid. If a get exists, remove the entry and fulfill its promise outside the lock. If readiness arrived first, store the descriptor until the get removes it. Keep the same one-consumer and byte validation rules; never block an action or parcel decoder. Owning promise state keeps abandoned eager futures safe. Cleanup must distinguish outstanding unmatched records from completed entries and retain old epoch ownership while actions are in flight.

Such a registry uses storage proportional to outstanding unmatched messages, which can be unbounded if the caller deliberately emits an unbounded eager stream. It does not retain one entry for every completed message. Making total storage strictly bounded would require backpressure or a documented maximum outstanding window, which changes the eager contract and can introduce new wait cycles. A permanent per-peer receive pump over reused channels is another possibility, but needs explicit startup/shutdown cancellation and safe demultiplexing; a naive inline continuation can re-enter the channel mutex. Neither alternative is implemented here.

The installed headers are under `/home/dmarce1/local/hpx/Release/include/`. Readiness FIFO reuse should be reconsidered only after the frozen rendezvous experiment establishes whether eliminating early fallback helps enough to justify additional protocol code.
