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

prior, confirmation, source = map(Path, sys.argv[1:])
status = dict(line.split('\t', 1) for line in (prior / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['stage'] == 'complete'
assert status['job_id'] == '1125925' and status['exit_status'] == '0' and status['candidate'] == 'rendezvous'
rows = [line.split('\t') for line in (prior / 'results.tsv').read_text().splitlines()]
assert rows and all(row[1] == 'PASS' for row in rows)
labels = ('pool_release', 'selected_original', 'selected_lean', 'selected_lean_sendimm')
required = ['prior_artifacts', 'prior_all_checks', 'archive_members', 'lean_dependencies', 'lean_comm_dependencies', 'confirmation_checks', 'fixed_inputs_unchanged', 'reused_binaries_unchanged', 'prior_artifacts_unchanged', 'benchmark_mpi']
required += ['benchmark_' + label for label in labels]
required += ['comparison_' + label for label in labels]
for label in ('selected_lean', 'selected_lean_sendimm'):
    required.append('communication_' + label)
    assert (prior / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS') == 4
for label in required:
    assert sum(row[0] == label for row in rows) == 1, label
members = json.loads((prior / 'archive_members.log').read_text())
assert members['status'] == 'PASS' and members['changed'] == ['hpx-comm.o'] and members['unchanged'] == 31
assert len(members['before']) == len(members['after']) == 32
assert list(members['before']) == list(members['after'])
assert [key for key in members['before'] if members['before'][key] != members['after'][key]] == ['hpx-comm.o']
with tempfile.TemporaryDirectory(prefix='progress-prior-') as temporary:
    scratch = Path(temporary)
    for label in labels:
        raw = subprocess.check_output([sys.executable, '-I', str(source / 'benchmarks/summarize.py'), str(prior / 'benchmark_mpi.log'), str(prior / ('benchmark_' + label + '.log'))], universal_newlines=True)
        assert json.loads(raw) == json.loads((prior / ('comparison_' + label + '.log')).read_text()), label
        (scratch / ('comparison_' + label + '.log')).write_text(raw)
    subprocess.check_output([sys.executable, '-I', str(confirmation / 'check_results.py'), str(scratch), 'rendezvous'])
    reproduced = json.loads((scratch / 'confirmation_comparison.json').read_text())
    assert reproduced == json.loads((prior / 'confirmation_comparison.json').read_text())
print(json.dumps(dict(status='PASS', prior_job='1125925', candidate='rendezvous', primary_cases=5, numerical_checks=15, all_plans_equal=True, unchanged_archive_members=31, median_seconds=reproduced['median_seconds'], median_ratios=reproduced['median_ratios'], original_evidence_unchanged=True), indent=2))
