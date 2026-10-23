#!/usr/bin/env python3
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


import json
from pathlib import Path
import re
import sys

log, hpx, mpi = sys.argv[1:]
text = Path(log).read_text()
assert 'not found' not in text
assert 'apex' not in text.lower()
hpx_seen = []
mpi_seen = []
for name, path in re.findall(r'^\s*(\S+)\s+=>\s+(\S+)', text, re.M):
    if name.startswith('libhpx'):
        assert path.startswith(hpx.rstrip('/') + '/'), (name, path)
        hpx_seen.append(path)
    if name.startswith('libmpi') or name.startswith('libopen-pal'):
        assert path.startswith(mpi.rstrip('/') + '/'), (name, path)
        mpi_seen.append(path)
assert hpx_seen and mpi_seen, (hpx_seen, mpi_seen)
print(json.dumps(dict(status='PASS', hpx_libraries=hpx_seen, mpi_libraries=mpi_seen, apex_present=False), indent=2))
