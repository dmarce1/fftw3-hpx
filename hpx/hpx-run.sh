#!/bin/sh
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#

# Usage: hpx-run.sh HPXRUN LOCALITIES THREADS PROGRAM [ARGUMENTS...]
# check.pl appends benchmark arguments to this command.  The delimiter keeps
# hpxrun.py from interpreting the benchmark's own command-line options.
set -eu
if [ "$#" -lt 4 ]; then
    echo "usage: $0 HPXRUN LOCALITIES THREADS PROGRAM [ARGUMENTS...]" >&2
    exit 2
fi
hpxrun=$1
localities=$2
threads=$3
program=$4
shift 4

# A test in this project always launches processes on this local machine.
unset HPXRUN_NODES HPXRUN_ARGS
# hpxrun selects a parcelport only for multiple localities.  Select TCP
# explicitly for the one-locality checks too, and require successful exits.
# Let the local scheduler place workers instead of pinning every process
# to the same first CPUs.
exec "$hpxrun" -l "$localities" -t "$threads" -p tcp -r none -e 0 -- \
    "$program" --hpx:ini=hpx.parcel.mpi.enable=0 \
    --hpx:ini=hpx.parcel.tcp.enable=1 --hpx:ini=hpx.parcel.bootstrap=tcp \
    --hpx:bind=none "$@"
