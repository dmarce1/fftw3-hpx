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

# Failed standalone communication-check launch: job 1125426

Compilation succeeded, but HPX initialization rejected the command-line entry
`hpx.parcel.tcp.enable=0` as unknown in this installation, which has no TCP
parcelport. The launcher exited 255 before the communication assertions ran.
This job is not evidence that those assertions passed or that the message
algorithm failed. The later corrected runner must not be substituted for this
executed script.

`comm_check.sbatch`, the launch command, build log, communication-check log and
aggregate failure log are preserved byte-for-byte, together with configuration,
source/binary hash records and final status. Binaries and shell xtrace are
excluded. `SOURCE_MAP.json` maps every copied file to its verified local input;
`SHA256SUMS` verifies the published subset from this directory. Original hash
records retain their original remote paths.
