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
import statistics
import subprocess
import sys

root, source = map(Path, sys.argv[1:3])
sendimm = '0'
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
hpx_labels = ('lean_baseline1000', 'lean_backoff10', 'lean_baseline1000repeat', 'hpx_profile10')
cases = {}
mpi_cases = {}
for bookend in ('mpi_start', 'mpi_end'):
    for label in hpx_labels:
        raw = subprocess.check_output([sys.executable, '-I', str(source / 'benchmarks/summarize.py'), str(root / ('benchmark_' + bookend + '.log')), str(root / ('benchmark_' + label + '.log'))], universal_newlines=True)
        comparison = json.loads(raw)
        assert all(comparison['normalized_plans_equal'].values()), (bookend, label)
        for backend in ('mpi', 'hpx'):
            case = comparison[backend]
            assert all(case['configuration'][key] == value for key, value in expected.items())
            assert len(case['samples_seconds']) == 7 and case['result']['status'] == 'PASS'
        if label in cases:
            assert cases[label] == comparison['hpx']
        if bookend in mpi_cases:
            assert mpi_cases[bookend] == comparison['mpi']
        cases[label] = comparison['hpx']
        mpi_cases[bookend] = comparison['mpi']
assert mpi_cases['mpi_start']['plans'] == mpi_cases['mpi_end']['plans']
assert all(case['plans'] == cases['lean_baseline1000']['plans'] for case in cases.values())
cases.update(mpi_cases)
run_order = ['mpi_start', 'lean_baseline1000', 'lean_backoff10', 'lean_baseline1000repeat', 'mpi_end', 'hpx_profile10']
compact = {}
for label in run_order:
    case = cases[label]
    values = case['samples_seconds']
    compact[label] = dict(role=('diagnostic' if label == 'hpx_profile10' else 'primary'), samples_seconds=values, median_seconds=statistics.median(values), min_seconds=min(values), mean_seconds=statistics.mean(values), max_seconds=max(values), checks=case['checks'], plans_sha256={key: hashlib.sha256(value.encode('utf-8')).hexdigest() for key, value in case['plans'].items()}, raw_log_sha256=hashlib.sha256((root / ('benchmark_' + label + '.log')).read_bytes()).hexdigest())
medians = {label: case['median_seconds'] for label, case in compact.items()}
ratios = {label + '_over_' + bookend: medians[label] / medians[bookend] for label in hpx_labels if label != 'hpx_profile10' for bookend in ('mpi_start', 'mpi_end')}
ratios['mpi_end_over_mpi_start'] = medians['mpi_end'] / medians['mpi_start']
ratios['lean_repeat_over_initial_baseline'] = medians['lean_baseline1000repeat'] / medians['lean_baseline1000']
ratios['backoff10_over_initial_baseline'] = medians['lean_backoff10'] / medians['lean_baseline1000']
ratios['backoff10_over_repeated_baseline'] = medians['lean_backoff10'] / medians['lean_baseline1000repeat']
for cap in ('1000', '10'):
    assert (root / ('communication_cap' + cap + '.log')).read_text().splitlines().count('communication check PASS') == 4
analysis = json.loads((root / 'hpx_profile10.json').read_text())
assert analysis['status'] == 'PASS' and analysis['diagnostic_only']
assert len(analysis['runs']) == 1
run = analysis['runs'][0]
assert run['configuration']['backend'] == 'hpx' and run['status'] == 'PASS'
assert run['sha256'] == hashlib.sha256((root / 'analysis_hpx_profile10.log').read_bytes()).hexdigest()
assert len(run['rank_samples']) == 28 and len(run['critical_rank_samples']) == 7
normalized = {key:hashlib.sha256(value.replace('hpx-', 'mpi-').encode('utf-8')).hexdigest() for key,value in cases['lean_backoff10']['plans'].items()}
assert run['normalized_plan_sha256'] == normalized
assert not any(key.startswith('critical_rank_') and key.endswith('hpx_minus_mpi') for key in analysis)
ratios['diagnostic_hpx10_over_clean_hpx10'] = medians['hpx_profile10'] / medians['lean_backoff10']
inherited = dict(line.split('=', 1) for line in (root / 'inherited_mpi_thread_level.txt').read_text().splitlines())

summary = dict(inherited_mpi_thread_level=inherited, diagnostic=dict(scope='HPX only; absolute phases within this new run. No previous-allocation MPI diagnostic is paired.', critical_rank_means=run['critical_rank_means'], critical_rank_medians=run['critical_rank_medians'], sample_maximum_readiness_phase=run['sample_maximum_readiness_phase']), license='GPL-2.0-or-later', status='PASS', sendimm=int(sendimm), configuration=expected, run_order=run_order, cases=compact, median_seconds=medians, median_ratios=ratios, mpi_bookend_change_percent=100 * (ratios['mpi_end_over_mpi_start'] - 1), lean_baseline_repeat_change_percent=100 * (ratios['lean_repeat_over_initial_baseline'] - 1), numerical_checks=18, all_plans_equal=True, all_numerical_checks_pass=True, communication_gates=2, changed_parameter='hpx.max_idle_backoff_time: 1000 to 10 and back to 1000', unchanged_idle_loop_count='Default 200000; no command-line override', interpretation='Same lean binary and fixed sendimm for all lean runs. MPI bookends and repeated lean baseline expose temporal drift; one fixed-order cohort does not remove it or guarantee a stable performance improvement.')
(root / 'readiness_progress_comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
