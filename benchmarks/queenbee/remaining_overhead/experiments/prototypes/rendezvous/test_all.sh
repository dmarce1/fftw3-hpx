#!/usr/bin/env bash
# Copyright (c) 2026 Dominic C. Marcello
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

set -Eeuo pipefail
root=$(cd "$(dirname "$0")" && pwd)
for precision in double single long_double; do
    bash "$root/validate_precision.sh" test "$precision" > "$root/validation/$precision/test.console.log" 2>&1
    printf '%s standard matrix PASS\n' "$precision"
done
bash "$root/validate_combined.sh" test > "$root/validation/combined/test.console.log" 2>&1
printf 'combined precision PASS\n'
