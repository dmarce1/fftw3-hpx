#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
"""Reproduce a published successful all-to-all comparison without changing it."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

base = Path(__file__).resolve().parent
package = json.loads((base / 'PACKAGE.json').read_text())
job = package['job_id']
assert str(job).isdigit()
raw = base / 'raw' / job
with tempfile.TemporaryDirectory(prefix='fftw_alltoall_recompute_') as temporary:
    work = Path(temporary)
    for path in raw.iterdir():
        if path.is_file():
            assert not path.is_symlink()
            shutil.copyfile(str(path), str(work / path.name))
    subprocess.check_call([sys.executable, '-I', str(base / 'inputs/alltoall/check_results.py'), str(work)],
                          stdout=subprocess.DEVNULL)
    rebuilt = (work / 'alltoall_comparison.json').read_bytes()
    assert rebuilt == (base / 'SUMMARY.json').read_bytes(), 'Published summary does not reproduce byte-for-byte'
    assert rebuilt == (raw / 'alltoall_comparison.json').read_bytes(), 'Remote summary does not reproduce byte-for-byte'
summary = json.loads(rebuilt)
assert summary['status'] == 'PASS'
assert summary['timed_samples'] == 42 and summary['numerical_checks'] == 18
print(json.dumps(dict(status='PASS', job_id=job, summary_byte_identical=True,
                     median_seconds=summary['median_seconds'],
                     median_ratios=summary['median_ratios']), indent=2))
