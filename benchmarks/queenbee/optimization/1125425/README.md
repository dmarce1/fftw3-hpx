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

# Diagnostic profile cohort: job 1125425

The job completed with PASS. Its four instrumented HPX runs retain the primary
1024 cubed case and have a separate MPI control. Each has 196 PROFILE records,
28 PROFILE_TOTAL records and seven samples. Analysis validates exact agreement
between each sample's maximum rank total and its published SAMPLE time.

`analysis/` preserves the independently generated local analysis unchanged.
Its subsequent-tuning paragraph was explicitly provisional when written; the
raw tuning evidence is now published separately in `../1125437/`. Profile
timings include instrumentation. Copy/construction/receive counters are nested
inside sendrecv; the residual is uninstrumented time, not an exclusive transpose
measurement. See `analysis/notes.md` for interpretation and its limits.

`job.sbatch` is the exact executed script. `.command` files preserve individual
commands, and `hpx_metadata/` preserves flags derived from the installed HPX
CMake metadata. Full plans remain in the raw benchmark logs; compact comparison
summaries replace only duplicated plan strings with hashes. The aggregate job
log, binaries, generated config.status files and shell xtrace are excluded.

`SOURCE_MAP.json` records exact input paths and hashes. `SHA256SUMS` verifies all
published files relative to this directory. Original remote checksum records
remain unchanged and may name paths outside this evidence subset. Verify the
publication with `sha256sum -c SHA256SUMS` from this directory.
