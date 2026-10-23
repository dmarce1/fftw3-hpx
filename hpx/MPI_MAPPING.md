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

# MPI calls and their HPX replacements

The HPX port replaces the MPI calls made by FFTW's distributed C implementation with the C bridge declared in [hpx-comm.h](hpx-comm.h) and implemented in [hpx-comm.cpp](hpx-comm.cpp). It preserves the distributed FFT algorithms in the corresponding `hpx/` sources. This is the subset needed by FFTW, not a general MPI compatibility layer.

Names below use the double-precision `fftw_hpx_` prefix. The same bridge is compiled with `fftwf_hpx_` and `fftwl_hpx_` prefixes for single and long-double precision. Most bridge functions are internal; applications use the declarations in [fftw3-hpx.h](fftw3-hpx.h), including the opaque communicator handle and `fftw_hpx_comm_world()`.

## Distributed library operations

| Original MPI call | HPX bridge replacement | Implementation and scope |
| --- | --- | --- |
| `MPI_Comm_rank` | `fftw_hpx_comm_rank` | Reads the calling member's rank from the shared `Group`. The world rank is initialized from `hpx::get_locality_id()`; split ranks follow the split's ordering. |
| `MPI_Comm_size` | `fftw_hpx_comm_size` | Reads the group's member count. World size comes from `hpx::get_num_localities(hpx::launch::sync)`. |
| `MPI_Comm_dup` | `fftw_hpx_comm_dup` | Allocates another handle sharing the same `Group`, collective generations and per-peer message sequences. **It does not create an independent communication context as MPI duplication does.** Calls on handles sharing a group must remain sequential. |
| `MPI_Comm_free` | `fftw_hpx_comm_free` | Deletes a non-world handle and sets it to `FFTW_HPX_COMM_NULL`. Shared owners keep the group alive; cached split groups remain until library cleanup. The world handle is library-owned. |
| `MPI_Comm_split` | `fftw_hpx_comm_split` | Uses HPX `all_gather` to collect colors and keys, selects the matching color, and sorts by key with parent rank as the tie-breaker. It creates or reuses a cached group for that ordered membership. This implements the splits used by FFTW, not every MPI split mode. |
| `MPI_Allreduce` on `MPI_INT` with `MPI_LOR` or `MPI_LAND` | `fftw_hpx_allreduce_int` with `FFTW_HPX_LOR` or `FFTW_HPX_LAND` | Calls synchronous HPX `all_reduce` with logical OR or AND and returns a normalized Boolean result. Used for distributed applicability and consistency decisions. |
| `MPI_Allreduce` on `MPI_DOUBLE` with `MPI_SUM` or `MPI_MAX` | `fftw_hpx_allreduce_double` with `FFTW_HPX_SUM` or `FFTW_HPX_MAX` | Calls synchronous HPX `all_reduce` with addition or maximum. Used by planner cost hooks and benchmark timing reductions. |
| `MPI_Bcast` | `fftw_hpx_bcast` | Root packs an owned byte vector and calls HPX `broadcast_to`; other members use `broadcast_from` and copy into the destination. The bridge implements root zero, as used by the ported FFTW calls. |
| `MPI_Alltoall` | `fftw_hpx_alltoall` | Packs one owned byte vector per destination, exchanges the vector of blocks with HPX `all_to_all`, then copies each received block into its destination segment. |
| `MPI_Alltoallv` | `fftw_hpx_alltoallv` | Uses the same owned-vector exchange, with per-peer counts and displacements converted from element units to byte offsets. Empty blocks are supported. |
| `MPI_Send` | `fftw_hpx_send` | Sends a `Message` through HPX channel `set` and waits for completion before returning. Remote source storage remains valid through that completion; self-sends retain an owned copy so the source can be reused after return. |
| `MPI_Recv` | `fftw_hpx_recv` | Receives a `Message` through HPX channel `get<Message>` for the specified source and message sequence/tag. Message ownership keeps any owned receive storage alive while the bridge consumes it. |
| `MPI_Sendrecv` | `fftw_hpx_sendrecv` | Combines outgoing and incoming channel operations, completes the required communication before returning, and preserves source lifetime and overlapping-buffer safety. This is the operation used by the pairwise transpose. |
| `MPI_Abort` | `fftw_hpx_abort` | Calls `hpx::terminate()` for fatal termination. It does not reproduce communicator-scoped MPI abort semantics or propagate the supplied MPI-style integer status. Exceptions at the C bridge boundary also terminate through HPX. |

The replacements can be compared directly in [MPI pairwise transpose](../mpi/transpose-pairwise.c) and [HPX pairwise transpose](transpose-pairwise.c), [MPI all-to-all transpose](../mpi/transpose-alltoall.c) and [HPX all-to-all transpose](transpose-alltoall.c), [recursive transpose](transpose-recurse.c), [planner API](api.c), [consistency checks](any-true.c), and [wisdom exchange](wisdom-api.c). The original MPI files remain available for comparison.

Multi-member collectives use an explicit, increasing generation owned by the group. Point-to-point operations combine the original caller tag with a per-peer send/receive sequence, so repeated tags select distinct messages. The bridge uses separate names for its collective and channel communicators. See [Communication and threading](README.md#communication-and-threading) for the current `Message` representation, receive storage policy, final-copy behavior and any readiness protocol. That section is the implementation-specific description; the mapping above does not imply that every receive goes directly into an FFTW array.

## Verification and benchmark helpers

The copied distributed verification program [hpx-bench.c](hpx-bench.c) also needs data-distribution helpers. These are not additional operations used by the FFT algorithms.

| Original call in the verification program | Replacement | Important difference |
| --- | --- | --- |
| `MPI_Gather` | `fftw_hpx_bench_gather` | Packs each member's bytes and uses HPX `all_gather`. Every member receives all blocks; only the selected root unpacks the complete result. |
| `MPI_Gatherv` | `fftw_hpx_bench_gatherv` | Also uses `all_gather`; the root unpacks using per-member counts and displacements. The gathered payload is replicated on all members. |
| `MPI_Scatterv` | `fftw_hpx_bench_scatterv` | The root packs one block per destination. HPX `all_gather` distributes that collection, and each member selects its block. The root's full packed collection is replicated. |
| `MPI_Allreduce` for maximum time or wisdom-import success | `fftw_hpx_allreduce_double` or `fftw_hpx_allreduce_int` | Uses the library bridge reductions described above. Wisdom broadcast/gather itself uses the ported [wisdom API](wisdom-api.c). |

These simple gather/scatter helpers support the upstream verification workflow and have different memory and communication costs from MPI's root-only operations. They are **not used by the standalone matched 1024³ benchmark**, [matched_3d.cpp](../benchmarks/matched_3d.cpp), which validates local slabs using reductions without gathering the global FFT arrays.

That standalone driver has its own two backend operations: its MPI `MPI_Barrier` is replaced by an HPX `all_reduce` synchronization, and its MPI maximum `MPI_Allreduce` is replaced by HPX `all_reduce`. The HPX operations use a separate statistics communicator and explicit generations, independent of FFTW's bridge communicator; the MPI operations use `MPI_COMM_WORLD`. Both backends measure elapsed time with `std::chrono::steady_clock`; there is no `MPI_Wtime` replacement.

## Runtime and library lifecycle

| MPI-side operation | HPX-side operation | Ownership |
| --- | --- | --- |
| Application or benchmark `MPI_Init` / `MPI_Init_thread` | Application `hpx::init` with its entry point enabled on every locality | Starts the runtime before FFTW initialization. [hpx-bench-main.cpp](hpx-bench-main.cpp) dispatches the benchmark on an HPX large-stack executor. `fftw_hpx_init()` does not start HPX. |
| `MPI_COMM_WORLD` passed to distributed FFTW routines | `fftw_hpx_comm_world()` | Returns the precision library's world handle after `fftw_hpx_init()` and before `fftw_hpx_cleanup()`. There is no conversion from an existing MPI communicator. |
| FFTW's `fftw_mpi_init()` | `fftw_hpx_init()` | Initializes FFTW threads, installs the HPX threaded-loop callback, creates the bridge world group, and registers the distributed solvers. This is library initialization, separate from runtime initialization. |
| FFTW's `fftw_mpi_cleanup()` | `fftw_hpx_cleanup()` | Removes library state and the callback and releases communicator/cache state. Plans and FFTW allocations must already have been released. |
| Application or benchmark `MPI_Finalize` | `hpx::finalize()` after per-locality library cleanup | Finalizes the HPX application. An MPI parcelport manages its own MPI lifecycle within HPX. |
| `MPI_Comm_f2c` in the upstream distributed Fortran wrappers | No replacement | The distributed Fortran interface is not ported. |

`MPI_Comm` becomes the opaque `fftw_hpx_comm`; `MPI_COMM_NULL` becomes `FFTW_HPX_COMM_NULL`. MPI datatype arguments become explicit element sizes, and MPI status parameters disappear. The bridge transports the contiguous buffers used by these FFTW routines; it does not provide MPI derived datatypes, wildcard receives or a general MPI error-code interface. The threaded-loop callback is a separate change: HPX tasks and a large-stack executor replace FFTW's pthread worker dispatch, as documented in the [application contract](README.md#application-contract).

## Where MPI remains

Replacing MPI calls in the FFTW layer does not mean that the cluster transport stops using MPI. QueenBee runs HPX through its **MPI parcelport**, with TCP disabled between servers. HPX implements parcel transport using MPI internally. The stock MPI control and the HPX runs both use **Open MPI 5.0.11** on QueenBee; the runtime above that transport differs. See the [QueenBee environment and commands](../benchmarks/queenbee/README.md) and [optimization evidence](../benchmarks/queenbee/optimization/README.md), and the current [transport instructions](README.md#local-and-cluster-transports).
