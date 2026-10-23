# Bounded parallel receive-copy experiment

Copyright (c) 2026 Dominic C. Marcello

This program and its accompanying notes are free software; you can redistribute
them and/or modify them under the terms of the GNU General Public License as
published by the Free Software Foundation; either version 2 of the License, or
(at your option) any later version. They are distributed in the hope that they
will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public
License for more details. You should have received a copy of the GNU General
Public License along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

The frozen source changes only the final copy from a pooled point-to-point
Message into its caller's receive buffer. It inherits the integrated pool bridge
with SHA-256 `57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c`.
The candidate is
`55b88660b9ca905049b197c7d9437864985877cc497152413c40c3204f1e12a9`.
Production source and benchmark source are unchanged.

Messages smaller than 32 MiB and calls outside an HPX task use the existing
serial memcpy. Larger messages use at most eight existing HPX workers, with at
least 8 MiB per job. The caller copies the last chunk, including any remainder;
other chunks are disjoint HPX tasks with the ordinary stack size. Every launched
future finishes before this function returns, including a submission-failure
path. There are no extra OS threads, changes to FFT task scheduling, or changes
to the Bytes/vector collective receive path.

Remote payload storage belongs to the received Message and remains independent
of its destination. Self sends retain their owned source copy. The existing
sendrecv source-completion wait still precedes receiveBytes, so overlapping user
send/receive buffers retain the same safety boundary. Pool lifetime, channel
tags, wire representation, and source-reference lifetime are unchanged.

This tests whether more of the existing workers can use memory bandwidth during
the final receive copy. It might instead contend with parcel progress or pay
more scheduling overhead. Existing NUMA interleaving is preserved; the code does
not establish affinity or guarantee NUMA-local execution. The 32 MiB threshold
and eight-job cap are deliberately bounded initial choices, not measured optima.

The previous candidate/bg1 diagnostic measured about 0.568 seconds in final
receive copies per rank/sample, nested inside sendrecv. That measurement predates
the final pooled/global1 configuration. It therefore does not establish either
the current pool copy cost or the maximum achievable speedup. The final pooled
1024-cubed run's gap to MPI was about 0.847 seconds; copy removal alone is not a
proven explanation for that gap.

## Local validation

`validate.sh build` compiled one process at a time against the existing local
HPX1.11 installation and matching Boost1.83 headers. Only `hpx-comm.o` was
replaced in an isolated archive: all other 31 members are byte-identical.
`validate.sh test` used at most four workers and passed:

- Full byte/guard checks with 1 and 4 workers for zero, one byte, below/at/above
  32 MiB, odd remainders, a 64 MiB payload, and an owned source overwritten before
  copying. The four-worker test reports `jobs=4` for the parallel cases.
- The same large copy outside an HPX runtime, which reports the serial fallback.
- Assertion-enabled communication checks at 1 locality x2 workers and 2x2.
- The unchanged N256 driver at 2x2, one warmup and three timed samples, with full
  spectrum and initial/final roundtrip checks below the original 1e-10 tolerance.

The candidate/driver were compiled with `-O3 -DNDEBUG`; communication checker
assertions were separately retained by `-UNDEBUG`. Exact commands, logs, input
and output digests, archive comparison, and `SUMMARY.json` are in `validation/`.
Input manifests verified unchanged before and after all tests. These are local
double-precision correctness checks over TCP, not a performance comparison or
cross-node MPI-parcelport result. A controlled cluster comparison should use the
same release flags for both the integrated pool control and this candidate.
