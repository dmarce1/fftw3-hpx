#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
import hashlib
import json
from pathlib import Path
import subprocess
import sys

def members(path):
    names = subprocess.check_output(['ar', 't', str(path)], universal_newlines=True).splitlines()
    assert len(names) == len(set(names)), 'Duplicate archive member'
    return names, {name: hashlib.sha256(subprocess.check_output(['ar', 'p', str(path), name])).hexdigest() for name in names}

before_path, after_path, objects = map(Path, sys.argv[1:])
names, before = members(before_path)
after_names, after = members(after_path)
assert names == after_names, 'Archive member order/set changed'
expected = {}
for logical in ('hpx-comm.o', 'transpose-pairwise.o'):
    found = [name for name in names if name == logical or name.endswith('_la-' + logical)]
    assert len(found) == 1, (logical, found)
    actual = found[0]
    expected[logical] = actual
    assert hashlib.sha256((objects / actual).read_bytes()).hexdigest() == after[actual]
changed = {name for name in names if before[name] != after[name]}
assert changed == set(expected.values()), (changed, expected)
print(json.dumps(dict(status='PASS', changed=sorted(changed), unchanged=len(names)-len(changed), resolved=expected, before=before, after=after), indent=2))
