<!-- Copyright (c) 2026 Dominic C. Marcello. SPDX-License-Identifier: GPL-2.0-or-later -->

# Isolated direct-receive / pooled-fallback experiment

This is an isolated experiment, not an integrated improvement or a measured
performance result. Local correctness validation is recorded below. No
production source, FFTW algorithm, original benchmark driver, original build
artifact, or remote state was changed. All sources and this README are GPL
version 2 or later; see the repository `COPYING`.

## Evidence and hypothesis

The final matched QueenBee comparison (job 1125688) measured pool-only HPX at
4.203216089 seconds, direct receive at 4.524689387 seconds, and MPI at
3.356002875 seconds. Both HPX variants used the same background-worker limits,
normal multithreaded MPI and 1000 ms idle-backoff cap. The earlier 1 ms cohort
also favored pooling. Neither cohort recorded direct-hit frequency. The
timings alone do not show why direct reception lost.

The frozen direct source does reveal a concrete difference: when a parcel
arrives without an exact posted target, `Message::load` always allocates a new
array. Pool-only HPX can reuse an existing array. Direct receive also retains
extra key serialization, registry lookups, map allocations, and target ownership
metadata. Missed direct targets can therefore incur both direct-path metadata
costs and repeated large allocations. The hybrid removes the latter cost while
keeping successful direct hits. That makes a bounded experiment worthwhile;
it does not predict a win or attribute the existing gap to page faults, UCX
registration, or any other unmeasured mechanism.

The local HPX `serialization/input_container.hpp` selects the address supplied
by `make_array` when zero-copy reception is enabled, and otherwise copies into
that address. `serialize_buffer.hpp` serializes its allocator before loading
the array and captures that allocator in its shared-storage deleter. The
hybrid follows those same ordering and lifetime rules. These headers are from
the already-audited HPX 1.11 installation; the prototype adds no transport
implementation or deserializer rendezvous.

## Source files and exact scope

- `base-hpx-comm.cpp`: immutable current production pool snapshot, SHA-256
  `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c`.
- `direct-reference.cpp`: immutable earlier direct prototype, SHA-256
  `477f1243b68a303e370d97913279f9b312ed66c8a54811392083b9b6faec1590`.
- `hpx-comm.cpp`: complete hybrid replacement, with no diagnostic counters.
- `hybrid.patch`: patch from the production pool snapshot to the hybrid.
- `direct-to-hybrid.patch`: smaller review patch showing only pooled ownership
  added to the direct prototype.
- `hpx-comm-diagnostic.cpp`, `diagnostic.patch`, and
  `receive-diagnostics.hpp`: separate temporary counter variant and its private
  API. Its wire payload is the same as the counter-free hybrid, but its timings
  must not substitute for counter-free results.
- `PROVENANCE.json` and `SHA256SUMS`: source identities and patch reconstruction
  checks. `sha256sum -c SHA256SUMS` verifies this directory's source package.

The current pool implementation is copied unchanged into the hybrid's
precision-specific pool namespace. Each custom direct `Message` carries a
`ReceiveAllocator`. Its epoch is serialized after the exact group/source/tag
key and byte count, before the payload. On load, that epoch is resolved before
any owned allocation. No pointer or shared ownership object crosses the wire.

For a direct hit, `data_` points at the registered caller destination, while
`owned_` remains empty. The allocator never deallocates caller storage. For a
fallback or self-copy, an owning shared array uses a deleter capturing the
allocator and byte count by value. Only the last Message copy releases that
block. There is no deleter reference to `this`, the source buffer, or a stack
allocator. Direct Message copies keep the target descriptor alive as before.

The pool retains one idle block per precision, reuses only exact sizes, and
keeps the larger returned block. Its retention bound is the largest returned
message for that epoch, not a fixed byte cap; live messages own separate
storage. No additional pool slots or benchmark-size threshold are introduced.
Cleanup requires no outstanding posted receives, detaches/disables the pool,
and then releases communicators. Late owners can release safely into their
disabled old pool; delayed old-epoch parcels cannot refill the current pool.

Exact key/length validation, duplicate-claim rejection, zero-length handling,
and the direct prototype's self/overlap exclusions are unchanged. Separate
send calls still complete without a posted receive. The parcel deserializer
does one lookup and falls back immediately when there is no posted target;
it does not wait for receiver readiness, an owner to release storage, or
another HPX task to run. Existing short registry/pool mutex sections can
contend; allocation and deletion remain outside the pool lock. This is not a
claim that heap allocation itself has bounded latency.

The outgoing source remains referenced until the destination channel-set
action completes. `sendrecv` still waits for that outgoing completion before
performing any fallback copy into a potentially overlapping receive array.
Direct reception is disabled for overlap and self peers exactly as before.
All localities must use the same hybrid wire format; do not mix this binary
with pool-only or the older direct prototype in one run.

## Diagnostic counters

The diagnostic variant exports precision-qualified C functions through
`receive-diagnostics.hpp`:

```cpp
FFTW_HPX_COMM_FN(receive_diagnostics_reset)();
FFTW_HPX_COMM_FN(receive_diagnostics_report)(rank, sample);
```

Each report writes eleven lines to standard error:

```text
RECEIVE_DIAGNOSTIC rank=0 sample=0 metric=direct_hit calls=3 bytes=3221225472
```

That line is an example format, not an observed result. Counts and bytes use
relaxed atomics, are process/precision-local, and are absent from the timing
source. The metrics are:

| Metric | Meaning |
| --- | --- |
| `posted` | Successful nonempty destination registrations |
| `disabled_registration` | Nonempty registrations disabled by self/overlap policy |
| `remote_load` | Nonempty Message deserialization operations |
| `direct_hit` | Deserialization claimed the exact posted destination |
| `fallback_unposted` | No exact posted target; owned reception used |
| `pool_hit` | Owned allocation reused the exact-size cached block |
| `pool_miss` | Owned allocation with a pool needed fresh heap storage |
| `unpooled_allocation` | Owned allocation had no matching current epoch pool |
| `self_copy` | An outgoing owning Message copy, used for self-send |
| `final_copy` | Point-to-point Message bytes copied into the caller destination |
| `direct_copy_elided` | Point-to-point Message already used that destination |

`fallback_unposted` includes both early arrival and intentionally unposted
exchanges; it is not an early-arrival-only counter. `final_copy` and
`direct_copy_elided` exclude collective vector payloads. No deallocation or
timing scopes are added. A failed allocation/invalid-message run can contain
partial counters and must not be accepted as diagnostic evidence.

Reset only at a globally quiescent boundary and ensure every rank has reset
before any rank starts the next transform. Resetting independently after the
existing pre-transform barrier would lose an early parcel on a slower rank.
A diagnostic-only driver can add a barrier before reset, then use its existing
pre-transform barrier after reset. Capture/report after forward elapsed time
has been recorded and before the existing maximum-time reduction permits
any rank to start the inverse. All counter/reset/report work stays outside the
forward timer, but the atomic events still perturb execution, so compare
timings only with the untouched driver and counter-free library.

At a quiescent successful forward boundary, test these identities for both
calls and bytes:

- `remote_load = direct_hit + fallback_unposted`.
- `pool_hit + pool_miss + unpooled_allocation = fallback_unposted + self_copy`.
- `direct_copy_elided = direct_hit` and
  `final_copy = fallback_unposted + self_copy`, when every counted message is
  consumed within the same interval.

Compute the direct byte hit fraction from `direct_hit / remote_load`; report
both byte and message fractions. Report cache hit/miss counts separately so
a high fallback rate is not mistaken for repeated heap allocation. Counters
must be interpreted alongside the interval boundaries and actual plan.

## Local validation

`validation/` contains exact commands, complete logs, status files, source and
binary hashes, and before/after archive-member hashes. The build helpers reuse
the original serial/thread/libbench2 libraries and original bench objects;
only the copied HPX archive's `hpx-comm.o` is replaced. All 31 other archive
members must be byte-identical in each precision. Production bridge objects
are compiled with `-DNDEBUG`; unit, communication and combined-precision checks
are explicitly compiled with `-UNDEBUG` after HPX flags. The unchanged matched
benchmark driver supplies its own numerical checks.

The ten deterministic unit groups have passed. They cover exact posted-target
addresses and guards, duplicate claims, unmatched fallback ownership, size
mismatch before any target write, group/epoch/source/tag isolation, zero-length
and self-copy behavior, and overlap boundaries. The archive chunk test uses
actual HPX destination selection followed by simulated transport fill; it is
not an MPI transport test. New hybrid groups prove no retroactive redirection
of an early fallback, last-owner-only pool return, successful exact-size reuse,
correct counter identities, a direct hit leaving the cached block untouched,
old-epoch decoding/release isolation, and largest-block retention.

The clean double bridge has also passed assertion-enabled communication checks
at 1×2 and 3×2 and all five standard numerical configurations. The untouched
256³ matched driver passed spectrum and both roundtrip checks at 2 localities
× 2 workers with two warmups and seven samples; its final relative roundtrip
error was 7.4990760765808042e-15. Those timings are retained only as raw local
correctness output and must not be compared with QueenBee performance.

Single and long-double builds and all five numerical configurations per
precision have passed, as have singleton and 3×2 communication checks for each.
The unchanged combined-precision lifecycle program passed at 3×2. In total,
all 15 standard matrix calls, six standalone communication launches (12
locality PASS markers), ten deterministic groups, one matched numerical run
and one combined-precision run passed. `validation/SUMMARY.json` records the
final status and exact checks. All original input hashes were reverified after
testing, and the tracked worktree remained clean. No compile or test repair
was required for this hybrid package.

The diagnostic source was compiled as part of the deterministic unit program;
its counters and ownership paths were exercised there. It has not yet been
linked into a distributed diagnostic benchmark. No hybrid MPI parcelport run
or controlled hybrid performance comparison has been performed.

Reproduction from the repository root uses these helpers in order. Distributed
runtime commands must have access to local TCP and must run sequentially so
the local launcher ports and the six-worker per-agent limit are respected:

```sh
bash build/qb_remaining/hybrid/validate_units.sh build
bash build/qb_remaining/hybrid/validate_units.sh test
for precision in double single long_double; do
    bash build/qb_remaining/hybrid/validate_precision.sh build "$precision"
done
bash build/qb_remaining/hybrid/validate_combined.sh build
for precision in double single long_double; do
    bash build/qb_remaining/hybrid/validate_precision.sh test "$precision"
done
bash build/qb_remaining/hybrid/validate_combined.sh test
```

The standard matrix is the repository's `check.pl --verbose --random
--maxsize=10000 -c=10 --mpi` at 1×1, 2×1, 3×1, 4×1 and 3×2 (the last also
uses `--nthreads=2`). Each precision also runs standalone communication checks
at 1×2 and 3×2. The combined program uses all three precision libraries together,
advances their communicator generations by different amounts, and cleans up
and reinitializes one while using the others.

TCP is used only between processes on this workstation. No cross-server TCP
or QueenBee access was performed. All local builds/tests share the user's
aggregate twelve-core limit; this agent used at most six runtime workers and
two concurrent compiler processes, with those phases kept separate. Root may
subsequently test matched MPI, pool-only and hybrid runs on QueenBee under the
existing login budget and identical 1024³/64-worker/2-warmup/7-sample settings,
plans, placement, MPI parcelport and `UCX_TLS=rc,sm,self`, with TCP disabled.
A separate diagnostic run can measure hit and reuse rates. Local correctness
is a gate for that experiment; it does not establish a performance improvement.
