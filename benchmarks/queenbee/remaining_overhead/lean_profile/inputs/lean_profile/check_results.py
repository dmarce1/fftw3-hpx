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
import re
from pathlib import Path
import statistics
import subprocess
import sys

root, source = map(Path, sys.argv[1:])
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
cases = {}
for mpi, hpx in (('mpi', 'lean_control'), ('mpi_profile', 'hpx_profile'), ('mpi', 'hpx_profile'), ('mpi_profile', 'lean_control'), ('mpi_thread_multiple', 'lean_control')):
    raw = subprocess.check_output([sys.executable, '-I', str(source / 'benchmarks/summarize.py'), str(root / ('benchmark_' + mpi + '.log')), str(root / ('benchmark_' + hpx + '.log'))], universal_newlines=True)
    comparison = json.loads(raw)
    assert all(comparison['normalized_plans_equal'].values())
    for label, backend in ((mpi, 'mpi'), (hpx, 'hpx')):
        case = comparison[backend]
        assert all(case['configuration'][key] == value for key, value in expected.items())
        assert len(case['samples_seconds']) == 7 and case['result']['status'] == 'PASS'
        if label in cases:
            assert cases[label] == case
        cases[label] = case
assert cases['mpi']['plans'] == cases['mpi_profile']['plans'] == cases['mpi_thread_multiple']['plans']
assert cases['lean_control']['plans'] == cases['hpx_profile']['plans']
order = ['mpi', 'lean_control', 'mpi_profile', 'hpx_profile', 'mpi_thread_multiple']
compact = {}
for label in order:
    case = cases[label]
    values = case['samples_seconds']
    compact[label] = dict(role=('diagnostic' if label.endswith('_profile') else ('auxiliary' if label == 'mpi_thread_multiple' else 'primary')), samples_seconds=values, median_seconds=statistics.median(values), min_seconds=min(values), mean_seconds=statistics.mean(values), max_seconds=max(values), checks=case['checks'], plans_sha256={key:hashlib.sha256(value.encode('utf-8')).hexdigest() for key,value in case['plans'].items()}, raw_log_sha256=hashlib.sha256((root / ('benchmark_' + label + '.log')).read_bytes()).hexdigest())
medians = {label: value['median_seconds'] for label, value in compact.items()}
for label in ('lean_control','hpx_profile'):
    assert (root / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS') == 4
analysis = json.loads((root / 'profile_analysis.json').read_text())
assert analysis['status'] == 'PASS' and analysis['diagnostic_only'] and analysis['all_normalized_plans_equal']
assert len(analysis['runs']) == 2
for run, label in zip(analysis['runs'], ('mpi_profile','hpx_profile')):
    assert run['status'] == 'PASS'
    assert run['sha256'] == hashlib.sha256((root / ('analysis_' + label + '.log')).read_bytes()).hexdigest()
    assert len(run['rank_samples']) == 28 and len(run['critical_rank_samples']) == 7
probes = {}
pattern = re.compile(r'MPI_THREAD_PROBE rank=(\d+) requested=(\d+) provided=(\d+) query=(\d+) env_is_set=(\d+) env=(\S+) forced=(\d+) status=(\w+)')
for label in ('normal', 'multiple'):
    rows = pattern.findall((root / ('mpi_thread_probe_' + label + '.log')).read_text())
    assert len(rows) == 4 and {int(row[0]) for row in rows} == set(range(4))
    records = []
    for rank, required, provided, query, is_set, env, forced, status in rows:
        assert status == 'PASS' and int(required) == 1 and provided == query
        assert int(forced) == (1 if label == 'multiple' else 0)
        if label == 'multiple':
            assert int(provided) == 3 and int(is_set) == 1 and env == '3'
        records.append(dict(rank=int(rank), requested=int(required), provided=int(provided), query=int(query), env_is_set=int(is_set), env=env))
    probes[label] = records
normal_levels = sorted({row['provided'] for row in probes['normal']})
assert len(normal_levels) == 1
assert len({(row['env_is_set'], row['env']) for row in probes['normal']}) == 1
inherited = dict(line.split('=', 1) for line in (root / 'inherited_mpi_thread_level.txt').read_text().splitlines())
expected_set = 1 if inherited['is_set'] == 'x' else 0
expected_env = (inherited['value'] if inherited['value'] else '<empty>') if expected_set else '<unset>'
assert all(row['env_is_set'] == expected_set and row['env'] == expected_env for row in probes['normal'])
thread_note = 'The separate normal probe observed the levels recorded here; the unchanged benchmark requested FUNNELED. This does not prove the provided level of historical runs.'
if normal_levels == [3]:
    thread_note += ' The normal probe already provided MULTIPLE, so the auxiliary run does not establish a new thread-level setting.'
summary = dict(license='GPL-2.0-or-later', status='PASS', run_order=order, configuration=expected, cases=compact, median_ratios=dict(primary_lean_over_mpi=medians['lean_control']/medians['mpi'], diagnostic_hpx_over_diagnostic_mpi=medians['hpx_profile']/medians['mpi_profile'], mpi_instrumented_over_control=medians['mpi_profile']/medians['mpi'], hpx_instrumented_over_control=medians['hpx_profile']/medians['lean_control'], auxiliary_mpi_multiple_over_original_mpi=medians['mpi_thread_multiple']/medians['mpi']), numerical_checks=15, mpi_thread_probe=probes, normal_probe_provided_levels=normal_levels, mpi_thread_interpretation=thread_note, all_plans_equal=True, profile_validation='PASS: separate analyzer checks metric identities, complete rank/sample matrices, scope validity and critical-rank decompositions', interpretation='Diagnostic phase times contain instrumentation overhead; compare each diagnostic against its own clean control. The auxiliary thread-level MPI run does not replace the original primary baseline. One fixed-order cohort cannot by itself separate temporal variability from perturbation.')
(root / 'lean_profile_comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
