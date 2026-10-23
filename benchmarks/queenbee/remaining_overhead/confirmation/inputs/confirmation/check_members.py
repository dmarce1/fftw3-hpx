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


import hashlib
import json
from pathlib import Path
import subprocess
import sys


def members(path):
    names = subprocess.check_output(['ar', 't', str(path)], universal_newlines=True).splitlines()
    assert len(names) == len(set(names)) == 32
    return names, {name: hashlib.sha256(subprocess.check_output(['ar', 'p', str(path), name])).hexdigest() for name in names}

base, candidate = map(Path, sys.argv[1:])
names, before = members(base)
after_names, after = members(candidate)
assert names == after_names
changed = [name for name in names if before[name] != after[name]]
assert changed == ['hpx-comm.o'], changed
print(json.dumps(dict(status='PASS', changed=changed, unchanged=31, before=before, after=after), indent=2))
