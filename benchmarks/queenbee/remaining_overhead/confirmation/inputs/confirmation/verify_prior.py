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
import shutil
import subprocess
import sys
import tempfile

prior, bundle, source = map(Path, sys.argv[1:4])
selected = sys.argv[4]
assert selected in ('parallel_copy', 'hybrid', 'rendezvous')
status = dict(line.split('\t', 1) for line in (prior / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['stage'] == 'complete'
assert status['job_id'] == '1125899' and status['exit_status'] == '0'
rows = [line.split('\t') for line in (prior / 'results.tsv').read_text().splitlines()]
assert rows and all(row[1] == 'PASS' for row in rows)
labels = ('pooled_current', 'pool_release', 'parallel_copy', 'hybrid', 'lean_pool', 'rendezvous', 'hybrid_diagnostic', 'rendezvous_diagnostic')
required = ['candidate_checks', 'archive_members', 'lean_dependencies', 'lean_comm_dependencies', 'fixed_inputs_unchanged', 'lean_install_unchanged', 'benchmark_mpi']
required += ['benchmark_' + label for label in labels]
required += ['comparison_' + label for label in labels]
for label in ('pool_release', 'parallel_copy', 'hybrid', 'lean_pool', 'rendezvous', 'hybrid_diagnostic', 'rendezvous_diagnostic'):
    required.append('communication_' + label)
    assert (prior / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS') == 4
for label in required:
    assert sum(row[0] == label for row in rows) == 1, label
# Re-run every numerical/timing/plan parser and both counter audits in a scratch
# directory. This never rewrites the completed job's evidence.
with tempfile.TemporaryDirectory(prefix='confirmation-prior-') as temporary:
    scratch = Path(temporary)
    for label in labels:
        raw = subprocess.check_output([sys.executable, '-I', str(source / 'benchmarks/summarize.py'), str(prior / 'benchmark_mpi.log'), str(prior / ('benchmark_' + label + '.log'))], universal_newlines=True)
        comparison = json.loads(raw)
        assert comparison == json.loads((prior / ('comparison_' + label + '.log')).read_text()), label
        (scratch / ('comparison_' + label + '.log')).write_text(raw)
    for label in ('hybrid_diagnostic', 'rendezvous_diagnostic'):
        shutil.copyfile(str(prior / ('benchmark_' + label + '.log')), str(scratch / ('benchmark_' + label + '.log')))
    subprocess.check_call([sys.executable, '-I', str(bundle / 'check_results.py'), str(scratch)])
    reproduced = json.loads((scratch / 'candidate_comparison.json').read_text())
    assert reproduced == json.loads((prior / 'candidate_comparison.json').read_text())
    assert reproduced['status'] == 'PASS' and selected in reproduced['primary_labels']
print(json.dumps(dict(status='PASS', prior_job='1125899', selected=selected, primary_cases=7, diagnostic_cases=2, diagnostic_rows=616, prior_evidence_unchanged=True), indent=2))
