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
"""Reduce validated raw profiles to additive critical-rank means and controls."""
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

root = Path(__file__).resolve().parent.parent
analysis = json.loads(Path(sys.argv[1]).read_text())
assert analysis['status'] == 'PASS' and analysis['all_normalized_plans_equal']

def fields(line):
    return dict(word.split('=', 1) for word in line.split()[1:])

controls = {}
plan_digests = set()
for path in sorted((root / '1125891').glob('benchmark_*.log')):
    lines = path.read_text().splitlines()
    result, = [fields(line) for line in lines if line.startswith('RESULT ')]
    config, = [fields(line) for line in lines if line.startswith('CONFIG ')]
    samples = [fields(line) for line in lines if line.startswith('SAMPLE ')]
    checks = [fields(line) for line in lines if line.startswith('CHECK ')]
    assert result['status'] == 'PASS' and len(samples) == 7 and len(checks) == 3
    assert [int(row['index']) for row in samples] == list(range(7))
    values = [float(row['max_rank_seconds']) for row in samples]
    for key, value in [('min_seconds', min(values)), ('median_seconds', statistics.median(values)),
                       ('mean_seconds', statistics.mean(values)), ('max_seconds', max(values))]:
        assert math.isclose(value, float(result[key]), rel_tol=1e-12)
    assert all(float(row['relative_max_error']) < float(row['tolerance']) == 1e-10 for row in checks)
    text = path.read_text()
    plans = tuple(hashlib.sha256(re.search(r'PLAN_' + direction + r'_BEGIN\n(.*?)\nPLAN_' + direction + r'_END', text, re.S).group(1).replace('hpx-', 'mpi-').encode()).hexdigest() for direction in ('FORWARD', 'BACKWARD'))
    plan_digests.add(plans)
    controls[path.stem.replace('benchmark_', '')] = {'configuration': config, 'result': result,
        'samples_seconds': values, 'checks': checks, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
assert len(controls) == 5 and len(plan_digests) == 1
runs = {}
for run in analysis['runs']:
    backend = run['configuration']['backend']
    assert run['sha256'] == controls[backend + '_profile']['sha256']
    rows = run['rank_samples']
    critical = [max((row for row in rows if row['sample'] == sample), key=lambda row: row['seconds']) for sample in range(7)]
    assert critical == run['critical_rank_samples']
    components = []
    for row in critical:
        m = lambda key: row['metrics'][key]['seconds']
        data = {'fft_worker_phases': m('run_jobs_wall'),
                'pairwise_staging_and_allocation': m('pairwise_copy_wall') + m('pairwise_allocate_wall') + m('pairwise_free_wall'),
                'exchange_without_receive_copy': m('exchange_wall') - m('receive_memcpy_wall'),
                'receive_copy': m('receive_memcpy_wall'),
                'residual': row['residual_seconds']}
        assert all(value >= 0 for value in data.values())
        assert math.isclose(sum(data.values()), row['seconds'], rel_tol=1e-12)
        components.append({'sample': row['sample'], 'rank': row['rank'], 'total_seconds': row['seconds'], 'components': data})
    means = {key: statistics.mean(row['components'][key] for row in components) for key in components[0]['components']}
    total = statistics.mean(row['seconds'] for row in critical)
    assert math.isclose(sum(means.values()), total, rel_tol=1e-12)
    metric_summary = {key: {'critical_mean_seconds': statistics.mean(row['metrics'][key]['seconds'] for row in critical),
                            'critical_median_seconds': statistics.median(row['metrics'][key]['seconds'] for row in critical),
                            'all_rank_median_seconds': statistics.median(row['metrics'][key]['seconds'] for row in rows),
                            'all_rank_calls': sum(row['metrics'][key]['calls'] for row in rows),
                            'all_rank_bytes': sum(row['metrics'][key]['bytes'] for row in rows)} for key in critical[0]['metrics']}
    misses = [{'rank': row['rank'], 'sample': row['sample'], 'calls': row['metrics']['pool_miss']['calls'],
               'heap_allocate_seconds': row['metrics']['heap_allocate_wall']['seconds']} for row in rows if row['metrics']['pool_miss']['calls']]
    runs[backend] = {'critical_samples': components, 'mean_components_seconds': means, 'mean_total_seconds': total,
                     'median_total_seconds': statistics.median(row['seconds'] for row in critical),
                     'metrics': metric_summary, 'pool_misses': misses,
                     'mean_process_cpu_seconds': statistics.mean(row['process_cpu_seconds'] for row in critical),
                     'mean_observed_task_cpu_seconds': statistics.mean(row['metrics']['task_thread_cpu_observed']['seconds'] for row in critical),
                     'mean_process_cpu_cores': statistics.mean(row['average_process_cpu_cores'] for row in critical),
                     'all_task_cpu_migration_calls': metric_summary['task_cpu_migration']['all_rank_calls'],
                     'all_nested_job_calls': metric_summary['nested_jobs']['all_rank_calls']}
gap = runs['hpx']['mean_total_seconds'] - runs['mpi']['mean_total_seconds']
exchange_gap = runs['hpx']['metrics']['exchange_wall']['critical_mean_seconds'] - runs['mpi']['metrics']['exchange_wall']['critical_mean_seconds']
def median(label):
    return float(controls[label]['result']['median_seconds'])
summary = {'copyright': 'Copyright (c) 2026 Dominic C. Marcello', 'license': 'GPL-2.0-or-later',
           'job': '1125891', 'status': 'PASS', 'all_plans_equal': True,
           'analysis_input_sha256': hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),
           'controls': controls, 'runs': runs,
           'mean_gap_seconds': gap, 'exchange_mean_gap_seconds': exchange_gap,
           'exchange_fraction_of_mean_gap': exchange_gap / gap,
           'control_median_ratios': {'hpx_profile_over_pool_release': median('hpx_profile') / median('pool_release'),
                                    'mpi_profile_over_mpi': median('mpi_profile') / median('mpi'),
                                    'pool_release_over_pooled_control': median('pool_release') / median('pooled_control')},
           'interpretation': 'Components use each sample actual critical rank, then means; sums equal mean total. Independent component medians are descriptive and are never summed. Nested counters are not additional wall time. Diagnostic CPU timing does not attribute runtime CPU to a particular subsystem.'}
(root / 'analysis_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps({'status': 'PASS', 'mean_gap_seconds': gap, 'exchange_mean_gap_seconds': exchange_gap, 'exchange_fraction_of_mean_gap': exchange_gap / gap, 'control_median_ratios': summary['control_median_ratios']}, indent=2))
