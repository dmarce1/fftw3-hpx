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

# Isolated posted-receive prototype

This directory is ignored. No tracked source or active candidate was changed.
The prototype has not been compiled, linked, run, or benchmarked. It is for
review before any decision to integrate it.

`hpx-comm.cpp` is the complete replacement candidate. `base-hpx-comm.cpp` is
an immutable snapshot of the existing serialize-buffer candidate used as its
base. `direct_receive.patch` is a patch against that snapshot, with repository
paths suitable for a disposable checkout. `provenance.json` records hashes;
the base snapshot includes uncommitted changes beyond its recorded Git HEAD.
Every locality must use the same prototype; its Message wire representation
is different from the base candidate.

## Proposed behavior

A precision-specific namespace (`fftw_hpx_transport`, `fftwf_hpx_transport`,
or `fftwl_hpx_transport`) contains the serialized Message type and a local
posted-receive registry. Distinct named types avoid ambiguous HPX action
registration names when several precision libraries are linked together.

Each key is the exact tuple `(group.basename, source group rank, sequenceTag)`.
The group basename already contains the precision, world initialization epoch,
and split identity. The sequenceTag is computed once from the existing bridge
per-peer sequence and tag; the same value is carried by the channel and its
payload. Neither destination pointers nor ownership pointers cross the wire.

`recv` registers a remote destination before requesting the channel value.
`sendrecv` computes both message identities and registers the incoming
remote destination before launching its outgoing message. A registration
contains the caller pointer, exact byte length, and a one-claim flag.

On remote Message deserialization, `load` reads key and length, performs one
short registry lookup, and either claims a matching posted target or allocates
owned `new char[bytes]` storage. Lookup never waits for a receiver to register;
it only holds a spinlock while inspecting metadata. Size mismatches on a
matching registration and duplicate claims throw before writing data.

`make_array` tells HPX to receive into the selected address. HPX's MPI zero-copy
receive path posts its chunk receive there; HPX's copying fallback instead
copies into that address. In both cases the channel action runs only after
the payload is complete. The existing channel receive future is therefore
the completion event. `receiveBytes` checks the length again and skips memcpy
when the payload already points at the caller's destination.

The registry entry is scoped by RAII and erased on every function exit. The
Message retains shared ownership of the target descriptor, not of caller
storage. Caller storage must remain valid through the blocking bridge call,
as before. Cleanup checks that no posted receives remain. The normal path
waits for receive completion and outgoing send completion before returning;
exceptions still terminate through the existing bridge boundary. There is no
recoverable cancellation protocol in this prototype.

## Safety fallbacks

- Early send or out-of-order future message: no exact posted key exists, so
  receive into owned storage and retain the normal final memcpy. A later
  registration cannot redirect an already deserialized message.
- Separate send and receive calls: `send` can complete without a posted recv,
  preserving buffered channel semantics. There is no readiness handshake.
- Self-send: retain an owned sender copy. Local actions bypass serialization;
  no direct target is registered for self-reception.
- Overlapping sendrecv: do not register a destination if the local send and
  receive byte ranges overlap, including exact aliasing. The range check uses
  unsigned address differences rather than potentially overflowing end
  addresses. The owned fallback is copied only after `sent.get()` completes,
  so writes cannot corrupt the referenced outgoing data. For simplicity,
  direct reception is also disabled whenever either peer is self.
- Empty messages: no registration, allocation, or array serialization; channel
  sequence participation remains unchanged.
- Duplicated communicator handles: the underlying Group and its sequences are
  shared, so the keys follow the existing duplicate-order semantics.
- Reinitialization: old and new world basenames have distinct epochs. An old
  key cannot select a new posted buffer. Cached splits retain their established
  Group identity and per-peer sequence semantics.
- Byte-count mismatch: a posted-target mismatch fails before writing; an early
  fallback mismatch fails at final receive validation. Invalid peer/tag/count
  usage otherwise retains the base bridge's preconditions.

This is opportunistic direct reception: a sender can beat remote registration.
There is no guaranteed direct-hit rate, and no performance claim is made.
The final buffer allocation/copy is avoided only on a matching direct hit.
There are still small Message, key, registry, and shared-state allocations.

## Why a custom payload rather than a custom allocator

HPX 1.11 supports a serialized allocator in serialize_buffer. Its upstream
`examples/quickstart/zerocopy_rdma.cpp` demonstrates a receiver-supplied address
allocator at lines 24-98, 128-139, and 199-206; it handles local fallback at
lines 177-187. That example uses request/response to provide the address.

The bridge must also handle sends arriving before recv, without a rendezvous
or a wire pointer. A custom payload with explicit `save/load` keeps the
ownership choices visible: `owned_` owns fallback storage, `target_` holds
only a target descriptor, and `data_` identifies the transfer address. Copies
share ownership. This avoids state propagation across allocator copies and
avoids constructing/destroying allocator elements in caller-owned storage.

Local HPX source checkout: `/home/dmarce1/work/hpx`, Git HEAD
`c9b81b401fbe6ba4a0306feff71d18ef01c71b34`. Relevant inspected headers match
`/home/dmarce1/local/hpx/Release/include/hpx/` byte for byte. Key paths:

- `libs/core/serialization/include/hpx/serialization/serialize_buffer.hpp`,
  lines 31-59 and 375-402: allocator copies and payload serialization.
- `libs/core/serialization/include/hpx/serialization/array.hpp`, lines 74-100:
  make_array delegates to binary chunks.
- `libs/core/serialization/include/hpx/serialization/input_container.hpp`,
  lines 167-213: a receive-enabled archive publishes the chosen address to the
  networking layer; the non-direct archive copies into it.
- `libs/full/parcelport_mpi/include/hpx/parcelport_mpi/receiver_connection.hpp`,
  lines 276-354 and 395-423: populate chunk addresses, receive, then handle
  actions.
- `libs/full/collectives/include/hpx/collectives/detail/channel_communicator.hpp`,
  lines 51-95 and 130-149: channel payload/result copying and local get versus
  destination set.

The coordinator's `build/qb_optimize/remote_hpx_source_evidence.txt` subsequently
confirmed the same QueenBee `HPX_HAVE_GIT_COMMIT`, matching hashes for the
channel, serialize_buffer, vector, MPI receiver, and scheduling-loop headers,
and enabled global/MPI zero-copy send and receive settings. This establishes
source provenance and the intended runtime path, not a completed prototype
compile or runtime check.

## Required validation before integration

1. Compile/link all three precisions and a program linking multiple precision
   libraries. This new serialized type must register correctly in each.
2. Run the existing focused checks at one and three localities, including both
   init/cleanup cycles, self mutation, remote mutation before recv, empty
   messages, repeated tags, and exact/partial overlap.
3. Add deterministic serializer-level tests for a registered hit, missing-key
   fallback, unrelated source/tag/epoch isolation, length mismatch, duplicate
   claim, Message shared ownership, and registration erasure. Run with chunk
   reception enabled and disabled. Existing functional checks alone do not
   prove that the direct path was taken.
4. Exercise mixed send/recv/sendrecv ordering, uneven byte counts, zero-length
   directions, and delayed receivers on the actual MPI parcelport with TCP
   disabled. There must be no deserializer waiting on application progress.
5. Run the full numerical precision/type/shape matrix, then the same four-node
   1024 cubed case only if the preceding checks pass. Record direct/fallback
   counts and bytes using diagnostic-only instrumentation before attributing
   a change to direct reception. Preserve plans, worker count, and transport.

No chunking or buffer pool is included. Those are separate experiments.
