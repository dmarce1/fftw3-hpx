#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later

"""Recompute the published comparison from raw logs and commands."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


base = Path(__file__).resolve().parent
repo = base.parents[3]
raw = base / 'raw/1126034'
with tempfile.TemporaryDirectory(prefix='fftw_no_backoff_recompute_') as tmp:
    work = Path(tmp)
    for label in ('mpi_start', 'hpx_cap10', 'hpx_no_backoff',
                  'hpx_cap10repeat', 'mpi_end'):
        for suffix in ('.log', '.command'):
            name = 'benchmark_' + label + suffix
            shutil.copyfile(str(raw / name), str(work / name))
    for name in ('communication_cap10.log', 'communication_no_backoff.log',
                 'inherited_mpi_thread_level.txt'):
        shutil.copyfile(str(raw / name), str(work / name))
    subprocess.check_call([sys.executable, '-I', str(
        base / 'inputs/no_backoff/check_results.py'), str(work), str(repo)],
        stdout=subprocess.DEVNULL)
    rebuilt = (work / 'no_backoff_comparison.json').read_bytes()
    assert rebuilt == (base / 'SUMMARY.json').read_bytes()
    assert rebuilt == (raw / 'no_backoff_comparison.json').read_bytes()
summary = json.loads(rebuilt)
assert summary['status'] == 'PASS' and summary['timed_samples'] == 35
print(json.dumps(dict(status='PASS', median_seconds=summary['median_seconds'],
                      median_ratios=summary['median_ratios']), indent=2))
