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

"""Independently reduce six raw progress logs and verify launch/provenance receipts."""
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'raw/1125945'
order = ['mpi_start', 'pool_release', 'lean_baseline1000', 'lean_backoff1', 'lean_baseline1000repeat', 'mpi_end']
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def fields(line):
    return dict(word.split('=', 1) for word in line.split()[1:])

def manifest(path):
    return {line.split(None, 1)[1].lstrip('*'): line.split(None, 1)[0] for line in path.read_text().splitlines()}

def command(label):
    lines = (root / (label + '.command')).read_text().splitlines()
    assert len(lines) == 2 and lines[0].startswith('cd ')
    return shlex.split(lines[1])

status = dict(line.split('\t', 1) for line in (root / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['exit_status'] == '0' and status['stage'] == 'complete'
assert status['job_id'] == '1125945' and status['sendimm'] == '0'
assert (root / 'PROGRESS_FINAL_STATUS').read_bytes() == (root / 'FINAL_STATUS').read_bytes()
stages = [line.split('\t') for line in (root / 'results.tsv').read_text().splitlines()]
assert len(stages) == 20 and all(row[1] == 'PASS' for row in stages)
assert [row[0][10:] for row in stages if row[0].startswith('benchmark_')] == order
cases = {}
plans = {}
for label in order:
    path = root / ('benchmark_' + label + '.log')
    text = path.read_text()
    lines = text.splitlines()
    config, = [fields(line) for line in lines if line.startswith('CONFIG ')]
    result, = [fields(line) for line in lines if line.startswith('RESULT ')]
    backend = 'mpi' if label.startswith('mpi_') else 'hpx'
    assert config['backend'] == result['backend'] == backend and result['status'] == 'PASS'
    assert all(config[key] == value for key, value in expected.items())
    samples = [fields(line) for line in lines if line.startswith('SAMPLE ')]
    checks = [fields(line) for line in lines if line.startswith('CHECK ')]
    assert len(samples) == 7 and [int(row['index']) for row in samples] == list(range(7))
    assert all(row['backend'] == backend for row in samples + checks)
    values = [float(row['max_rank_seconds']) for row in samples]
    assert all(math.isfinite(value) and value > 0 for value in values)
    computed = dict(min_seconds=min(values), mean_seconds=statistics.mean(values), median_seconds=statistics.median(values), max_seconds=max(values))
    for key, value in computed.items():
        assert math.isclose(value, float(result[key]), rel_tol=1e-12), (label, key)
    assert len(checks) == 3 and {row['stage'] for row in checks} == {'forward_spectrum', 'initial_roundtrip', 'final_roundtrip'}
    for row in checks:
        error = float(row['relative_max_error'])
        assert math.isfinite(error) and 0 <= error <= float(row['tolerance']) == 1e-10
    plan = {}
    for direction in ('FORWARD', 'BACKWARD'):
        found = re.findall(r'PLAN_' + direction + r'_BEGIN\n(.*?)\nPLAN_' + direction + r'_END', text, re.S)
        assert len(found) == 1
        plan[direction.lower()] = found[0]
    plans[label] = plan
    cases[label] = dict(samples_seconds=values, checks=checks, raw_log_sha256=digest(path), plans_sha256={key: hashlib.sha256(value.encode()).hexdigest() for key, value in plan.items()}, **computed)
normalized = {tuple(value.replace('hpx-', 'mpi-') for value in plans[label].values()) for label in order}
assert len(normalized) == 1
assert plans['mpi_start'] == plans['mpi_end']
assert all(plans[label] == plans['pool_release'] for label in order if not label.startswith('mpi_'))

# Token comparison proves the cap is the only launch argument changed across
# lean runs. The same on-cluster executable hash is checked separately below.
baseline = command('benchmark_lean_baseline1000')
repeated = command('benchmark_lean_baseline1000repeat')
short = command('benchmark_lean_backoff1')
assert baseline == repeated
assert baseline.count('--hpx:ini=hpx.max_idle_backoff_time=1000') == 1
assert short.count('--hpx:ini=hpx.max_idle_backoff_time=1') == 1
short[short.index('--hpx:ini=hpx.max_idle_backoff_time=1')] = '--hpx:ini=hpx.max_idle_backoff_time=1000'
assert short == baseline
required = ['--hpx:threads=64', '--hpx:ini=hpx.parcel.mpi.sendimm=0', '--hpx:ini=hpx.parcel.mpi.background_threads=1', '--hpx:ini=hpx.max_background_threads=1', '--hpx:ini=hpx.parcel.mpi.multithreaded=1', '--hpx:ini=hpx.parcel.tcp.enable!=0', '--hpx:ini=hpx.parcel.mpi.enable!=1', '--hpx:ini=hpx.parcel.bootstrap!=mpi', '--hpx:bind=none']
assert all(baseline.count(value) == 1 for value in required)
assert not any('max_idle_loop_count=' in value or 'max_busy_loop_count=' in value for value in baseline)
assert command('benchmark_mpi_start') == command('benchmark_mpi_end')
communication = {}
for label in ('lean_baseline1000', 'lean_backoff1'):
    count = (root / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS')
    assert count == 4
    communication[label] = count
    args = command('communication_' + label)
    assert args.count('--hpx:threads=2') == 1 and '--hpx:threads=64' not in args
    assert '--hpx:ini=hpx.parcel.mpi.sendimm=0' in args

reuse = manifest(root / 'reused_binaries.sha256')
prior_artifacts = manifest(root / 'reused_artifacts/1125925_artifacts.sha256')
prior_reused = manifest(root / 'reused_artifacts/1125925_reused_binaries.sha256')
assert len(reuse) == 4
for name, value in reuse.items():
    if '/1125925/' in name:
        assert prior_artifacts[name.split('/1125925/', 1)[1]] == value
    else:
        assert prior_reused[name] == value
assert any(name in baseline and value == '42c8821d64faaf27411e1714fe05ed37d4feb4aa21fe79d4db6ec1b742f66496' for name, value in reuse.items())
preservation = {}
for name in ('fixed_inputs_unchanged.log', 'reused_binaries_unchanged.log', 'prior_artifacts.log', 'prior_artifacts_unchanged.log'):
    rows = (root / name).read_text().splitlines()
    assert rows and all(line.endswith(': OK') for line in rows)
    preservation[name] = len(rows)
for source, receipt in [('fixed_inputs.sha256', 'fixed_inputs_unchanged.log'), ('reused_binaries.sha256', 'reused_binaries_unchanged.log')]:
    names = list(manifest(root / source))
    assert [line[:-4] for line in (root / receipt).read_text().splitlines()] == names
assert (root / 'prior_artifacts.log').read_bytes() == (root / 'prior_artifacts_unchanged.log').read_bytes()
for name in ('lean_dependencies.log', 'lean_comm_dependencies.log'):
    data = json.loads((root / name).read_text())
    assert data['status'] == 'PASS' and data['apex_present'] is False
    assert all('/fftw3_hpx_remaining_20261023/lean_hpx/install/' in path for path in data['hpx_libraries'])
    assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in data['mpi_libraries'])

medians = {label: cases[label]['median_seconds'] for label in order}
ratios = {label + '_over_' + bookend: medians[label] / medians[bookend] for label in order if not label.startswith('mpi_') for bookend in ('mpi_start', 'mpi_end')}
ratios['mpi_end_over_mpi_start'] = medians['mpi_end'] / medians['mpi_start']
ratios['lean_repeat_over_initial_baseline'] = medians['lean_baseline1000repeat'] / medians['lean_baseline1000']
ratios['backoff1_over_initial_baseline'] = medians['lean_backoff1'] / medians['lean_baseline1000']
ratios['backoff1_over_repeated_baseline'] = medians['lean_backoff1'] / medians['lean_baseline1000repeat']
original = json.loads((root / 'progress_comparison.json').read_text())
assert original['status'] == 'PASS' and original['sendimm'] == 0
assert original['median_seconds'] == medians and original['median_ratios'] == ratios
assert original['configuration'] == expected and original['run_order'] == order
assert original['cases'] == cases
summary = dict(license='GPL-2.0-or-later', status='PASS', job_id='1125945', job_status=status, configuration=expected, sendimm=0, run_order=order, cases=cases, median_seconds=medians, median_ratios=ratios, mpi_bookend_change_percent=100 * (ratios['mpi_end_over_mpi_start'] - 1), lean_baseline_repeat_change_percent=100 * (ratios['lean_repeat_over_initial_baseline'] - 1), timed_samples=42, numerical_checks=18, all_normalized_plans_equal=True, all_hpx_plans_byte_equal=True, exact_cap_only_lean_commands=True, exact_mpi_bookend_commands=True, communication_passes=communication, reused_binary_hashes=reuse, preservation_receipt_counts=preservation, job_comparison_reproduced=True, stage_count=len(stages), interpretation='Cap1 median exceeds both surrounding cap1000 medians; no improvement established. Both MPI bookends and both HPX baselines are retained. One fixed-order allocation does not identify sleep causality or remove temporal/node variation. Binary hashes are recorded cluster receipts, not local rehashes of omitted binaries.')
print(json.dumps(summary, indent=2))
