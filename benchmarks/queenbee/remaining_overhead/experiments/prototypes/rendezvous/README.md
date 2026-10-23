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

# Isolated readiness rendezvous over the hybrid transport

This prototype is based on the frozen clean hybrid bridge `5a2446f92d48d69d25f16f2b19202e7e03159aab57397c415c3e31f8592ae0cd`. It does not change tracked files, FFTW algorithms, transform plans or the matched benchmark driver. `PROVENANCE.json` records both clean/diagnostic inputs and generated hashes; each source has an adjacent patch. `prepare.py` reproduces those bridge files; the expanded tests are separate authored files and should not be overwritten by regenerating their initial templates.

Every Group creates a separate channel communicator under `basename + "/readiness"` after its existing data channel. The Group basename already includes precision and world-init epoch; split-group names include membership identity. Duplicated communicator handles share the same Group, channels and per-peer send/receive sequence counters. Readiness uses the exact data-message tag `(sequence << 15) | caller_tag` rather than incrementing another sequence. Data and readiness occupy different channel namespaces and never compete for a typed value.

For every receive operation:

1. Compute its existing receive sequence/tag and register the destination if the hybrid permits direct writes.
2. Initiate a nonblocking channel set containing the expected byte count and whether a nonempty direct target is actually posted. Send it to this receive's source under that exact sequence/tag.
3. Receive the data as before. Observe readiness-send completion before returning; channel set completes after storing/delivering the token, without waiting for a peer consumer.

For every outgoing operation, install exactly one readiness get from its destination with its existing send sequence/tag. An eligible disjoint remote sendrecv waits for that descriptor, checks byte count, and only then sends the large payload. Every other sender initiates its payload immediately and destroys the unused readiness future without waiting. HPX futures are nonblocking on destruction, and channel get has already installed a continuation to consume the peer's eventual token. Thus standalone send still supports send-before-recv and immediate source reuse after completion.

Every receive, including an overlapping, self, empty, or standalone receive, must announce. Announcing only from direct-capable sendrecv would deadlock a direct sender matched by a standalone/fallback receiver. Every sender must consume once, including eager senders, so no selective stream of unconsumed readiness values accumulates. As in the original HPX channel implementation, per-tag channel map entries themselves persist for the Group lifetime. Operations require matching send/receive calls and the same per-peer order; this prototype does not add concurrent access to the existing non-atomic sequence counters.

## Matching and lifetime cases

| Case | Behavior |
| --- | --- |
| Both remote sendrecv calls disjoint | Both register and announce before either waits. Each outgoing payload follows the destination's announcement, so it sees the posted destination. |
| Ring with source different from destination | Each rank announces to its receive source, then waits on its send destination. All announcements are already initiated, so the ring contains no wait-before-announcement cycle. |
| Eligible sendrecv matched by standalone recv | The standalone recv registers and announces before waiting for data; the sender can proceed. |
| Standalone send followed by recv matched by sendrecv | Standalone send does not wait for readiness; its data action can finish even while the sendrecv waits for its own destination. The subsequent recv announces and releases that wait. |
| Standalone recv followed by send matched by sendrecv | Recv announces first, enabling its peer's payload; after it returns, its subsequent send supplies the reverse payload. |
| Overlap or either self endpoint in sendrecv | The receive is not registered; it advertises fallback. Outgoing data remains eager, and receive copy still occurs only after outgoing completion. Exact and partial overlap remain safe. |
| Self send before self recv | Self payload is copied into owned storage before send returns. The unresolved readiness future is discarded without waiting; later recv consumes the data and supplies its token. |
| Empty or unequal directional sizes | Every zero-byte operation still consumes the existing sequence and exchanges readiness. Each direction validates its own sender byte count against the corresponding receiver, so different sizes in opposite directions are valid. |
| Early standalone message | It may still arrive before registration, retaining the hybrid's owned pooled fallback. The parcel decoder never waits for a future receive call. |
| Cached split, dup/free, cleanup/re-init | Shared Groups preserve order; new init epochs give all three communicators fresh names. Outstanding control actions hold HPX component references; no control payload contains a user pointer. Data registrations remain live until incoming completion, then are removed. |

The wire Message adds a `requirePosted` boolean. A sender sets it only after a positive direct-ready descriptor. The receiver performs its existing exact-key lookup and byte check before any write; if that promised target is absent, it throws instead of silently allocating fallback storage. This makes the rendezvous guarantee observable even in the release bridge. Byte mismatch in the readiness descriptor is rejected before initiating the large send. Missing-target or duplicate-target exceptions remain fatal at the existing bridge boundary.

The descriptor's `direct=false` permits a direct-capable sender to communicate with a fallback receiver; it does not force a direct write. The source buffer still survives until the outgoing channel set future completes. The target registration survives until channel get completes, which follows HPX zero-copy receive chunk filling and action delivery. Incoming owned Messages still return to the epoch-scoped pool only after the last shared owner releases them. The protocol adds one small control message per data message and can therefore increase latency; no performance gain is assumed.

## Validation plan and artifacts

`validate.sh bridge` compiles the clean bridge with `-O3 -DNDEBUG`, replaces only `hpx-comm.o` in a copied 32-member archive, and records all unchanged member hashes. `validate.sh units` compiles the diagnostic source in an isolated ordinary-main executable and runs ten inherited direct/pool ownership groups plus a readiness roundtrip/required-target group. `validate.sh link` builds the expanded assertion-enabled communication test and the unchanged production matched driver. `validate.sh runtime` runs 1×2 and 3×2 communication tests followed by the unchanged 128³ matched driver at 3×2, with two warmups, seven samples and three numerical checks. No local runtime exceeds six HPX workers; these are local TCP tests only, not permission to use TCP on QueenBee.

The expanded communication test repeats two init/cleanup cycles and preserves the existing self-send mutation, ring/repeated-tag, overlapping-buffer, empty-message, collective, split and callback checks. Added cases combine sendrecv with standalone send-first and recv-first peers; one-sided and two-sided overlap; exact/partial overlap; directional empty messages; and actual point-to-point messages through repeated cached/reordered splits. These catch readiness sequencing or cycle bugs that purely symmetric sendrecv would miss.

A QueenBee experiment must retain the MPI-only parcelport, TCP force-disabled setting and all established launch/worker/backoff controls. Compile the clean source for timing and the diagnostic source only for direct/fallback/pool counters, using the same unchanged driver workload. Required-target enforcement proves that positively advertised direct receives did not silently fall back. Counters and performance results are separate evidence; local correctness does not establish cluster performance or transport registration cost.

## Completed local validation

All initial focused checks passed: the release bridge, eleven deterministic archive/ownership groups, expanded 1×2/3×2 communication tests, and the unchanged 128³ driver at 3×2. All three precision builds then passed the expanded communication checks and the five standard NUMCHECK10 configurations each (1×1, 2×1, 3×1, 4×1, 3×2), totaling fifteen matrix configurations. The unchanged double 256³ driver at 2×2 passed its three numerical checks and seven samples. One executable linking double, single and long-double libraries passed at 3×2.

`validation_summary.json` records these results and frozen source hashes. Commands, logs, status files, member-by-member archive checks and input/output hash manifests are under `validation/`. At most three compiler processes or six runtime workers were active; distributed runtime checks ran serially to avoid local launcher port conflicts. No cluster access was used for this validation. The repository status in the summary can include concurrently prepared publication files owned by the parent/evidence agent; source/archive preservation checks are the authoritative isolation evidence.
