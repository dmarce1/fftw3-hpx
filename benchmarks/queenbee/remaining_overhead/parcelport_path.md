<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# MPI parcel reception and remaining overhead

This note is free software/documentation under the GNU General Public License,
version 2 or any later version, without warranty; see [COPYING](../../../COPYING).
The linked HPX sources retain their upstream Boost Software License.

For an eligible remote exchange, HPX passes the posted FFTW destination to
`MPI_Irecv`. It does not first receive the large chunk into a separate HPX array
and merely omit the bridge's final copy. This conclusion depends on enabled
array/chunk and zero-copy receive optimizations, as described below. It says
nothing about internal MPI/UCX or hardware staging.

## Source identity

This audit inspected `/home/dmarce1/work/hpx` at commit
`c9b81b401fbe6ba4a0306feff71d18ef01c71b34`. The inspected serialization,
parcelport, MPI, collective and scheduler source paths had no local changes.
This is the same commit recorded in the QueenBee
[build metadata](lean_hpx/1125886/metadata.txt), the
[original installed defines](lean_hpx/original_config/include/hpx/config/defines.hpp)
and the [lean installed defines](lean_hpx/1125886/lean-defines.hpp).
The upstream links below are pinned to that commit. The local workstation's
installed HPX configuration differs from QueenBee's; the audit uses QueenBee's
captured configuration, not local installed defaults, for build claims.

The FFTW bridge audited here is the selected rendezvous source with SHA256
`cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c`.
Its preserved [validated source](integration/validated_inputs/hpx/hpx-comm.cpp)
provides stable line numbers for this note.

## How the destination reaches MPI

1. Bridge `sendrecv` lines 1078–1101 register the caller's exact destination
   before advertising readiness, then wait for the outgoing peer's readiness.
   Direct registration requires remote peers and disjoint source/destination
   spans. The receiver's `Message::load`, lines 451–473, decodes the match key
   and byte count, claims the target once, sets `data_ = target_->data`, and
   loads `make_array(data_, bytes_)`. A promised but missing target is an error.
2. HPX's [array serializer, lines 75–89](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/serialization/include/hpx/serialization/array.hpp#L75)
   forwards the archive's zero-copy receive marker to `load_binary_chunk`.
   The [input container, lines 167–211](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/serialization/include/hpx/serialization/input_container.hpp#L167)
   stores that address in the chunk descriptor when zero-copy reception is
   enabled; the copying branch is separate.
3. The MPI receiver first
   [decodes the parcel, lines 297–312](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/receiver_connection.hpp#L297).
   That decoding explicitly
   [marks the archive for zero-copy reception, lines 465–475](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelset/include/hpx/parcelset/decode_parcels.hpp#L465).
   It then issues `irecv(c.data(), chunk_size, ...)` at
   [lines 331–352](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/receiver_connection.hpp#L331).
   The MPI helper ultimately calls
   [`MPI_Irecv(address, ...), lines 533–559`](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/mpi_base/src/mpi_environment.cpp#L533).
4. The channel action runs only after chunk reception. The bridge waits for
   incoming data and outgoing send completion before releasing registrations
   or returning. Its final `receiveBytes`, lines 621–636, copies only when the
   delivered pointer differs from the caller's destination.

The [deterministic archive check](integration/validated_inputs/hpx/hpx-message-check.cpp),
lines 190–204, verifies that actual HPX archive decoding selects the exact
posted pointer and leaves the destination untouched before the simulated
transport write. It tests the serialization contract, not a live UCX transfer.
The separate cluster correctness and receive-counter evidence checks the
distributed implementation. A direct-hit/final-copy-elided counter alone would
not establish the absence of a copy inside archive loading; the source path
above is what distinguishes those cases.

## Enabling conditions and limits

The effective `hpx.parcel.mpi.array_optimization`,
`hpx.parcel.mpi.zero_copy_optimization` and
`hpx.parcel.mpi.zero_copy_receive_optimization` entries must be nonzero.
The parcelport [reads those entries in order, lines 61–77](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelset_base/src/parcelport.cpp#L61):
disabling array optimization also disables both zero-copy modes; disabling
zero-copy serialization also disables zero-copy reception. Archive data
chunking and receive chunking must remain enabled, with no serialization filter
that forces the copying path. The payload must be at least the configured
zero-copy threshold. QueenBee's captured threshold is 8192 bytes, far below the
1 GiB chunks in this benchmark. The existing diagnostic logs record all four
global/per-MPI zero-copy entries as `1`; see the earlier
[runtime diagnostics](../optimization/1125425/README.md).

Small messages, disabled optimization, or a filtering archive can still copy
inside HPX deserialization even when the bridge's final pointer comparison
avoids another copy. These paths retain the same completion semantics.
Self/overlapping exchanges and unmatched early arrivals retain owned storage
and fallback copying. The claim is therefore specific to the eligible large
remote path and its runtime settings, not every supported message.

## What remains above direct MPI

The unchanged [MPI pairwise transpose](../../../mpi/transpose-pairwise.c),
lines 71–77, makes its staging copy and calls `MPI_Sendrecv` with the final
FFTW receive address. HPX preserves the same FFTW staging work, but adds:

- A readiness channel action before the payload action, plus their completion
  futures. [Channel `set`, lines 141–148](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/collectives/include/hpx/collectives/detail/channel_communicator.hpp#L141)
  uses `hpx::async`. These action completions are distinct from MPI parcelport
  acknowledgement handshakes. No exact network-packet count is inferred here.
- A parcel header and serialization/chunk metadata before the large MPI chunk.
  The sender [sends the header and conditionally additional metadata](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/sender_connection.hpp#L172).
  Metadata can [piggyback in the header](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/header.hpp#L106),
  so it is incorrect to count each metadata section as another message.
- Header acceptance, archive decoding, target lookup, channel/future handling,
  and scheduler-driven MPI progress. The sender and receiver use `MPI_Test`
  in their progress state machines; see
  [sender completion, lines 332–383](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/sender_connection.hpp#L332)
  and [receiver completion, lines 428–450](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/receiver_connection.hpp#L428).

These are source-established operations, not measurements assigning the
remaining elapsed gap to one of them. MPI/UCX itself may also use rendezvous
and registration protocols. At 1 GiB the HPX MPI helper uses `MPI_BYTE` with an
ordinary integer count; its oversized-message datatype construction does not
apply. HPX requests `MPI_THREAD_MULTIPLE`, while the unchanged MPI benchmark
requests `MPI_THREAD_FUNNELED`. This is an implementation difference, not a
measured explanation of the residual gap. HPX's own global MPI mutex wrappers
do not lock in multithreaded mode; MPI's internal synchronization is separate.

## Bounded next step

No additional compile-time switch in this audit has evidence that it will close
the remaining gap. Parcelport/action counters were already off, and the lean
build removes the selected profiling facilities. The 8192-byte threshold already
selects chunking for 1 GiB. Compiled parcel-coalescing support does not by itself
mean these channel actions use a buffering handler: the default
[action handler trait returns null](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelset_base/include/hpx/parcelset_base/traits/action_message_handler.hpp#L19),
and the channel actions do not specialize it. The `async_serialization` entry
is stored, but the inspected HPX source has no caller of its accessor in this
path; it is not an established tuning mechanism here.

`hpx.parcel.mpi.ack_handshake` already
[defaults to zero](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/src/parcelport_mpi.cpp#L141).
Turning it on adds conditional acknowledgement steps; turning it off is not a
new optimization for the recorded configuration. MPI serialized mode previously
failed its runtime/shutdown checks and is not a validated substitute.

The `sendimm=1` option bypasses the normal pending-parcel/connection-cache
submission path, while retaining the required header, payload and progress
protocol. The [executed confirmation](confirmation/README.md) measured it at
8.298 seconds versus 3.870 seconds for the same lean binary with `sendimm=0`.
It is rejected. Readiness, payload wait and action completion require separate
diagnostic measurements on the new bridge; the older pooled-bridge profile
cannot apportion these stages. An MPI control requesting `MPI_THREAD_MULTIPLE`
is likewise an attribution experiment, not a replacement for the original
primary baseline.

## Readiness waits and idle backoff

A source-supported possibility is that readiness adds a period with no accepted
payload connection, during which the sole MPI progress worker can enter idle
backoff. This is a hypothesis about a reachable path, not an attribution of
observed sample variation to sleep.

The exact defaults in this HPX source are:

| Setting | Default | Meaning |
| --- | ---: | --- |
| `hpx.max_idle_loop_count` | 200000 | Empty scheduler-loop iterations before the outer idle callback |
| `hpx.max_busy_loop_count` | 2000 | Busy scheduler-loop iterations before maintenance/background work |
| `hpx.max_idle_backoff_time` | 1000 | Maximum exponential-backoff sleep, in milliseconds |

These values come from
[`config.hpp`, lines 327–336 and 399–400](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/config/include/hpx/config.hpp#L327),
and are exposed as runtime entries by
[`runtime_configuration.cpp`, lines 164–173](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/runtime_configuration/src/runtime_configuration.cpp#L164).
Earlier QueenBee diagnostic logs independently recorded 200000, 2000 and 1000;
the idle-loop default is not two million. Iteration counts are not elapsed-time
thresholds, and the 1000 ms cap does not mean every idle wait sleeps one second.

The relevant path is:

1. With `hpx.max_background_threads=1`, the scheduler permits its network
   background callback only on worker zero;
   [`scheduling_loop.hpp`, lines 120–132](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/thread_pools/include/hpx/thread_pools/scheduling_loop.hpp#L120).
   `hpx.parcel.mpi.background_threads=1` independently applies the same worker
   cutoff in
   [`parcelport_mpi.cpp`, lines 241–257](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/src/parcelport_mpi.cpp#L241).
   The separate MPI I/O-service progress loop runs only during HPX startup,
   [lines 317–337](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/src/parcelport_mpi.cpp#L317).
2. The MPI receiver's
   [`background_work`, lines 50–73](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/receiver.hpp#L50)
   returns false when it neither accepts a completed header nor finds an
   existing receive connection. Its posted wildcard header receive alone does
   not count as work. An accepted connection returns true even when its payload
   is incomplete and is put back on the queue. The
   [sender, lines 80–98](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/full/parcelport_mpi/include/hpx/parcelport_mpi/sender.hpp#L80)
   similarly returns true while it has an active connection.
3. The background task resets `idle_loop_count` only when its callback reports
   work;
   [`background_thread.cpp`, lines 39–53](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/thread_pools/src/detail/background_thread.cpp#L39).
   The scheduler polls this callback while idle, but after enough empty loops
   can invoke its outer idle callback;
   [`scheduling_loop.hpp`, lines 508–560](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/thread_pools/include/hpx/thread_pools/scheduling_loop.hpp#L508).
4. That outer callback is bound to `scheduler_base::idle_callback` by
   [`scheduled_thread_pool_impl.hpp`, lines 538–543](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/thread_pools/include/hpx/thread_pools/scheduled_thread_pool_impl.hpp#L538).
   It waits on a condition variable for `min(cap, 2^wait_count)` milliseconds
   and increases the backoff counter for each wait. A notification can interrupt the wait
   and reset that counter. Scheduling HPX work calls `notify_all`;
   [`scheduler_base.cpp`, lines 74–118](https://github.com/TheHPXProject/hpx/blob/c9b81b401fbe6ba4a0306feff71d18ef01c71b34/libs/core/threading_base/src/scheduler_base.cpp#L74).
5. An arriving MPI header is observed through `MPI_Test` in the MPI receiver,
   not an HPX condition-variable notification issued by the network arrival
   itself. A sleeping progress worker can therefore delay observing it until
   another HPX wakeup or its timeout. Once a payload connection exists, its
   positive work result helps prevent this idle path.

After a small outgoing readiness token finishes, a rank waiting for peer
readiness may have no active payload connection. Eager pooled exchange can
instead already have an in-flight payload. This makes the new readiness path
worth testing independently of an earlier pooled-bridge backoff experiment.
It does not establish that the tested application reached the sleep threshold,
how long it slept, or how much of any measured gap it explains. Lowering the
cap also affects other idle workers and their CPU activity, so even a timing
improvement would establish sensitivity to the setting rather than this single
mechanism's causality.

The [executed runtime-only comparison](progress/README.md) used six runs:
unchanged MPI, unchanged release pool, the selected lean rendezvous binary
with cap 1000, that same binary with cap 1, cap 1000 again, then MPI again.
It fixed `sendimm=0`, the 200000/2000 loop thresholds, both background-worker
limits of one, MPI multithreading, placement, NUMA policy and the complete
benchmark workload. Only the idle-backoff cap changed between the lean cases.
Cap 1 was 2.29% and 1.16% slower by median than its surrounding controls and
is not selected. The repeated controls expose temporal drift; they do not
remove fixed-order or node effects. This test does not establish scheduler
sleep as the remaining bottleneck.
