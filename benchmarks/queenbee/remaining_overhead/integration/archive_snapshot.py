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
# 
import hashlib
import json
import pathlib
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent
repo = root.parents[2]

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def members(path):
    names = subprocess.check_output(['ar', 't', str(path)], universal_newlines=True).splitlines()
    if len(names) != len(set(names)) or len(names) != 32:
        raise RuntimeError('unexpected archive members: ' + str(path))
    return {name: hashlib.sha256(subprocess.check_output(['ar', 'p', str(path), name])).hexdigest() for name in names}

phase = sys.argv[1]
if phase not in ('before', 'after'):
    raise RuntimeError('expected before or after')
records = {}
for precision, suffix in [('double', ''), ('single', 'f'), ('long_double', 'l')]:
    archive = repo / 'build' / precision / 'hpx' / '.libs' / ('libfftw3' + suffix + '_hpx.a')
    records[precision] = {'archive': str(archive), 'sha256': digest(archive), 'members': members(archive)}
if phase == 'after':
    before = json.loads((root / 'hpx_archives_before.json').read_text())
    for precision, record in records.items():
        old = before[precision]['members']
        if list(old) != list(record['members']):
            raise RuntimeError('archive member ordering changed')
        changed = [name for name in old if old[name] != record['members'][name]]
        if changed != ['hpx-comm.o']:
            raise RuntimeError('unexpected member changes: ' + str(changed))
        record['changed_members'] = changed
(root / ('hpx_archives_' + phase + '.json')).write_text(json.dumps(records, indent=2) + '\n')
if phase == 'before':
    source_names = ['hpx/hpx-comm.cpp', 'hpx/hpx-comm-check.cpp', 'hpx/hpx-message-check.cpp', 'hpx/hpx-message-check.hpp', 'hpx/hpx-comm.h', 'hpx/fftw3-hpx.h', 'hpx/Makefile.am', 'hpx/Makefile.in', 'hpx/hpx-run.sh', 'build/combined_precision_smoke.cpp']
    (root / 'source_inputs.sha256').write_text(''.join(digest(repo / name) + '  ' + str(repo / name) + '\n' for name in source_names))
    protected = []
    for precision in ('double', 'single', 'long_double'):
        base = repo / 'build' / precision
        for path in base.rglob('*.a'):
            if 'hpx' not in path.relative_to(base).parts:
                protected.append(path)
    if not protected:
        raise RuntimeError('no protected archives found')
    (root / 'protected_archives.sha256').write_text(''.join(digest(path) + '  ' + str(path) + '\n' for path in sorted(protected)))
print('Archive snapshot ' + phase + ' PASS')
