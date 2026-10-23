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
import subprocess
import sys
import tempfile

prior, bundle, source = map(Path, sys.argv[1:])
status = dict(line.split('\t', 1) for line in (prior / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['stage'] == 'complete'
assert status['job_id'] == '1125966' and status['exit_status'] == '0' and status['sendimm'] == '0'
rows = [line.split('\t') for line in (prior / 'results.tsv').read_text().splitlines()]
assert rows and all(row[1] == 'PASS' for row in rows)
for label in ('benchmark_mpi', 'benchmark_lean_control', 'benchmark_mpi_profile', 'benchmark_hpx_profile', 'benchmark_mpi_thread_multiple', 'communication_lean_control', 'communication_hpx_profile', 'archive_members', 'diagnostic_analysis', 'profile_checks', 'fixed_inputs_unchanged', 'reused_binaries_unchanged', 'prior_artifacts_unchanged', 'transformed_sources_unchanged'):
    assert sum(row[0] == label for row in rows) == 1, label
with tempfile.TemporaryDirectory(prefix='readiness-prior-') as temporary:
    scratch = Path(temporary)
    for path in prior.glob('*.log'):
        (scratch / path.name).symlink_to(path.resolve())
    (scratch / 'inherited_mpi_thread_level.txt').symlink_to((prior / 'inherited_mpi_thread_level.txt').resolve())
    subprocess.check_output([sys.executable, '-I', str(bundle / 'profile/analyze.py'), str(prior / 'analysis_mpi_profile.log'), str(prior / 'analysis_hpx_profile.log'), '--json', str(scratch / 'profile_analysis.json')])
    subprocess.check_output([sys.executable, '-I', str(bundle / 'check_results.py'), str(scratch), str(source)])
    reproduced = json.loads((scratch / 'lean_profile_comparison.json').read_text())
    assert reproduced == json.loads((prior / 'lean_profile_comparison.json').read_text())
print(json.dumps(dict(status='PASS', prior_job='1125966', numerical_checks=15, profile_checks='complete schema and phase validation rerun', communication_gates=2, original_evidence_unchanged=True), indent=2))
