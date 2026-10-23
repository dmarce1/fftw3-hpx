#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
import hashlib
import json
from pathlib import Path
import sys

baseline, candidate, overlay = map(Path, sys.argv[1:])
def files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
before, after, supplied = map(files, (baseline, candidate, overlay))
expected = dict(before)
expected.update(supplied)
assert after == expected, 'Source tree differs outside explicit overlay'
assert supplied['benchmarks/matched_3d.cpp'] == before['benchmarks/matched_3d.cpp']
changed = sorted(name for name in after if before.get(name) != after[name])
assert set(changed).issubset({'hpx/hpx-comm.cpp', 'hpx/hpx-comm.h', 'hpx/transpose-pairwise.c', 'hpx/hpx-comm-check.cpp', 'benchmarks/summarize.py'}), changed
tree_digest = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
print(json.dumps(dict(status='PASS', changed=changed, overlay=supplied,
                     baseline_tree_sha256=tree_digest,
                     all_other_sources_unchanged=True), indent=2, sort_keys=True))
