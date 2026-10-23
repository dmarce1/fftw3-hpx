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
import sys

source, diagnostic, profile, rendezvous = map(Path, sys.argv[1:])
manifest = json.loads((diagnostic / 'remaining_profile_manifest.json').read_text())
assert manifest['diagnostic_only'] and manifest['threads'] and manifest['pairwise']
expected = {'hpx/hpx-comm.cpp', 'benchmarks/matched_3d.cpp', 'threads/threads.c', 'hpx/transpose-pairwise.c', 'mpi/transpose-pairwise.c', 'benchmarks/remaining_profile.h', 'benchmarks/remaining_profile.cpp', 'benchmarks/remaining_mpi_profile.cpp'}
assert set(manifest['files']) == expected
proof = {}
for name, record in manifest['files'].items():
    actual = diagnostic / name
    assert actual.is_file() and not actual.is_symlink()
    digest = hashlib.sha256(actual.read_bytes()).hexdigest()
    assert digest == record.get('after_sha256', record.get('generated_sha256')), name
    if 'before_sha256' in record:
        original = rendezvous if name == 'hpx/hpx-comm.cpp' else source / name
        assert hashlib.sha256(original.read_bytes()).hexdigest() == record['before_sha256'], name
    else:
        assert hashlib.sha256((profile / Path(name).name).read_bytes()).hexdigest() == digest, name
    proof[name] = record
assert manifest['files']['hpx/hpx-comm.cpp']['before_sha256'] == 'cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c'
print(json.dumps(dict(status='PASS', diagnostic_only=True, files=proof), indent=2))
