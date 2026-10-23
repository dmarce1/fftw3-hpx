# Isolated receive-buffer pool experiment

This is an unintegrated prototype based on the current `serialize_buffer<char>`
candidate. `hpx/hpx-comm.cpp` is the proposed replacement; `base-hpx-comm.cpp` is
its frozen input, and `pooled_receive.patch` is their difference. No tracked
source, build, runtime, or remote installation was changed while preparing it.
The source retains the complete GPL version 2 or later notice.

The experiment changes only the allocator used by point-to-point Message
payloads. It does not change channel operations, matching, acknowledgement,
collectives, FFT plans, thread scheduling, final receive copies, or benchmark
options. Custom allocator metadata adds the communicator initialization epoch
to the Message archive; no addresses or shared ownership state go on the wire.
Every locality in an experimental run must use this same prototype binary.

## Cache policy and memory bound

Each precision has one process-local cache slot. The cache reuses a returned
block only when its byte count exactly matches the allocation request. A cache
miss allocates immediately; there is no condition variable, capacity wait, or
wait for a live Message to release storage. A short standard mutex protects
only the cache slot or current-pool registry. Allocation and deletion occur
outside these locks.

When returning storage, the pool keeps whichever is larger: the returned block
or the currently cached block. Equal-size returns keep the existing cached
block. Zero-length allocations are never cached. This deliberately has no
benchmark-specific size threshold or arbitrary byte cap.

At most one idle allocation is retained per precision, and its size is at most
the largest block previously returned to that precision's current pool. Live
messages still own their own allocations, as in the base implementation;
those allocations are not part of the idle-cache bound. A replaced block is
detached under the mutex and deleted immediately afterward, so it is never
available for reuse by another thread. A long-lived process can retain one
large block until precision cleanup; that is the explicit memory tradeoff.

## Lifetime and cleanup

The allocator carries shared ownership of the pool selected for its epoch.
HPX's `serialize_buffer` copies that allocator into the owning array's deleter.
The array therefore returns to the pool only when the last Message owner
releases it. The channel's by-value Message copies cannot recycle live storage.

`comm_init` creates a pool before constructing the world communicator, using
the same monotonically increasing epoch already used in communicator names.
`comm_cleanup` first detaches and disables that pool and purges its idle block,
then releases the communicator caches. An outstanding allocator keeps the old
pool object alive, but every subsequent deallocation to a disabled pool goes
directly to `delete[]`; it cannot refill the old slot.

The allocator serializes only the epoch and resolves it against the receiver's
current local pool. A delayed old-epoch parcel, or a parcel received while no
pool is current, uses ordinary allocation/deallocation. It cannot populate a
new epoch's cache. Precision-specific transport namespaces keep pool state,
allocator types, and HPX action identities distinct in combined-precision
executables.

An allocation racing with cleanup may finish after the pool is disabled, but
its allocator still owns the disabled pool and frees that allocation normally.
Cleanup does not invalidate storage held by an outstanding Message or wait
for its lifetime. Existing FFTW rules about concurrent initialization/cleanup
and continuing to use a cleaned-up communicator remain unchanged.

## Preserved message behavior

- Remote sends continue to reference the caller's source until the destination
  set action completes. The pool changes only receiver-owned storage.
- Self-sends still copy into independently owned storage before returning.
- Zero-byte messages do not access caller pointers and do not fill the cache.
- `sendrecv` still waits for its referenced send to finish before writing the
  user's receive buffer, preserving exact and partial overlap handling.
- Allocation failure follows the same bridge exception/termination policy as
  the base implementation. Deallocation remains nonthrowing.

## Validation boundary and next checks

Preparation includes source-diff inspection and exact patch reconstruction
only. This prototype has **not been compiled or run** and has no performance
result. Before any timing, compile all three precisions and run the existing
communication checks, including repeated cleanup/init, source overwrite after
send, zero messages, self-send, and exact/partial overlap. A focused allocator
check should also cover exact-size hits, misses while a block is checked out,
larger-block replacement, equal-size concurrent returns, and deallocation
after disable/reinitialization. Then compare the unchanged matched benchmark
and report retained memory alongside any timing difference.

The experimental purpose is to distinguish repeated allocation/page preparation
from the final receive copy and other transport costs. It does not establish
that UCX registration churn or page faults caused the observed slowdown.
