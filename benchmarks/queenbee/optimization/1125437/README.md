<!--
Copyright (c) 2026 Dominic C. Marcello

This report is free software/documentation; you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or (at your
option) any later version.

This report is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this report; if not, write to the Free Software Foundation, Inc., 51 Franklin
Street, Fifth Floor, Boston, MA 02110-1301 USA.
-->

# Partially completed tuning cohort: job 1125437

The whole job FAILED (exit 137, Slurm OUT_OF_MEMORY) during the serialized-MPI
variant's shutdown. Only the MPI control, candidate with one MPI background
worker, and candidate with both MPI and global background-worker limits of one
completed cleanly. Those runs have PASS numerical checks, launcher completion
and matching forward/backward plans. Their medians are 3.333576320, 8.388130506
and 5.559548005 seconds, respectively. The latter is 1.66774 times this cohort's
MPI control. The job reused the primary executables byte-for-byte.

The serialized-MPI variant (`hpx.parcel.mpi.multithreaded=0`) printed a numerical
PASS RESULT, then segfaulted in HCOLL context cleanup. Slurm recorded an OOM kill.
Its timing is invalid as a completed benchmark and is excluded from performance
claims. The final combined serialized/global-limit variant did not run. The
logs establish the shutdown fault and OOM event, but do not identify their
causal relationship. No accepted result requires disabling MPI multithreading.

All four raw benchmark logs and launch commands, the actual executed job script,
aggregate failure log, Slurm error/accounting, binary verification records,
configuration and provenance are retained. Compact comparison summaries omit
only repeated plan strings, retained in full in the raw benchmark logs. Binary
files and shell xtrace are excluded. `SOURCE_MAP.json` records original paths
and hashes. Run `sha256sum -c SHA256SUMS` here to verify this published subset.
The accounting snapshot also lists later job IDs; they are not results of this
cohort. These valid partial results do not make the entire job successful.
