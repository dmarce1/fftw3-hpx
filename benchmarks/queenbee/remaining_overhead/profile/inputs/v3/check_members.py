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


def require(value, message):
    if not value:
        raise RuntimeError(message)


def members(path):
    # universal_newlines is supported on Python 3.6; text was added in 3.7.
    names = subprocess.check_output(['ar', 't', str(path)], universal_newlines=True).splitlines()
    require(len(names) == len(set(names)), 'Duplicate archive member: ' + str(path))
    return names, {name: hashlib.sha256(subprocess.check_output(
        ['ar', 'p', str(path), name])).hexdigest() for name in names}


def original_name(names, logical):
    found = [name for name in names if name == logical or name.endswith('_la-' + logical)]
    require(len(found) == 1, 'Expected one original member for {}: {}'.format(logical, found))
    return found[0]


def main():
    hpx, mpi, threads, root = map(Path, sys.argv[1:])
    result = {}
    specifications = [
        ('pool_release', hpx, 'libfftw3_hpx.a', ['hpx-comm.o']),
        ('hpx_profile', hpx, 'libfftw3_hpx.a', ['hpx-comm.o', 'transpose-pairwise.o']),
        ('mpi_profile', mpi, 'libfftw3_mpi.a', ['transpose-pairwise.o']),
        ('threads_profile', threads, 'libfftw3_threads.a', ['threads.o']),
    ]
    for label, base, archive, logicals in specifications:
        path = root / label / archive
        before_names, before = members(base)
        after_names, after = members(path)
        resolved = {logical: original_name(before_names, logical) for logical in logicals}
        require(before_names == after_names, 'Original ordered member set changed: ' + label)
        changed = {name for name in before if before[name] != after[name]}
        require(changed == set(resolved.values()),
                'Wrong replacements {}: actual={} expected={}'.format(label, sorted(changed), sorted(resolved.values())))
        replacement_objects = {}
        for logical, actual in resolved.items():
            loose = root / label / actual
            if not loose.exists():
                loose = root / label / logical
            require(loose.is_file() and not loose.is_symlink(), 'Missing replacement object: ' + str(loose))
            digest = hashlib.sha256(loose.read_bytes()).hexdigest()
            require(digest == after[actual], 'Replacement does not equal archive member: ' + str(loose))
            replacement_objects[actual] = {'path': str(loose), 'sha256': digest}
        result[label] = {'changed': sorted(changed), 'unchanged': len(before) - len(changed),
                         'resolved_original_names': resolved, 'ordered_members': before_names,
                         'replacement_objects': replacement_objects, 'before': before, 'after': after}
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
