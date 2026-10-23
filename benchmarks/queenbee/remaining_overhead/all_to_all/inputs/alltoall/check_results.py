#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate same-workload modes while preserving the intentional exchange change."""
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


def fields(line):
    return dict(token.split('=', 1) for token in line.split()[1:] if '=' in token)


def read(path, backend, extent, warmups, samples, mode=None):
    text = path.read_text()
    lines = text.splitlines()
    config, = [fields(line) for line in lines if line.startswith('CONFIG ')]
    result, = [fields(line) for line in lines if line.startswith('RESULT ')]
    expected = dict(backend=backend, extent=str(extent), ranks='4', threads='64',
                    precision='double', inplace='1', layout='normal',
                    planner='FFTW_ESTIMATE', warmups=str(warmups), samples=str(samples))
    assert all(config[key] == value for key, value in expected.items()), (path, config)
    assert result['backend'] == backend and result['status'] == 'PASS', path
    checks = [fields(line) for line in lines if line.startswith('CHECK ')]
    assert len(checks) == 3
    assert {check['stage'] for check in checks} == {'forward_spectrum', 'initial_roundtrip', 'final_roundtrip'}
    for check in checks:
        error = float(check['relative_max_error'])
        assert math.isfinite(error) and error <= float(check['tolerance']) == 1e-10
    timings = [fields(line) for line in lines if line.startswith('SAMPLE ')]
    assert [int(item['index']) for item in timings] == list(range(samples))
    values = [float(item['max_rank_seconds']) for item in timings]
    assert all(math.isfinite(value) and value > 0 for value in values)
    stats = dict(min_seconds=min(values), median_seconds=statistics.median(values),
                 mean_seconds=statistics.mean(values), max_seconds=max(values))
    for key, value in stats.items():
        assert math.isclose(float(result[key]), value, rel_tol=1e-13), (path, key)
    plans = {}
    for direction in ('FORWARD', 'BACKWARD'):
        match = re.search('PLAN_' + direction + '_BEGIN\n(.*?)\nPLAN_' + direction + '_END', text, re.S)
        assert match
        plan = match.group(1)
        if mode is not None:
            assert ('/all_to_all' in plan) == (mode == 'all_to_all'), (path, direction)
            assert 'hpx-transpose-pairwise' in plan
        plans[direction.lower()] = plan
    reports = [fields(line) for line in lines if line.startswith('FFTW_HPX_TRANSPOSE ')]
    if mode is not None:
        assert len(reports) == 4, (path, reports)
        assert sorted(int(item['rank']) for item in reports) == list(range(4))
        assert all(item['mode'] == mode for item in reports)
        counts = [int(item['exchange_calls']) for item in reports]
        assert all((count > 0) if mode == 'all_to_all' else (count == 0) for count in counts), counts
        assert len(set(counts)) == 1, counts
    return dict(configuration=config, result=result, checks=checks,
                samples_seconds=values, plans=plans, mode_reports=reports,
                raw_log_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), **stats)


def normalize(plan):
    # No local transform, planning, or schedule differences may be normalized.
    return plan.replace('/all_to_all', '').replace('hpx-', 'mpi-')


def compare_plans(cases):
    first = next(iter(cases.values()))
    for case in cases.values():
        for direction in first['plans']:
            assert normalize(case['plans'][direction]) == normalize(first['plans'][direction]), direction


root = Path(sys.argv[1])
gates = {}
for mode in ('pairwise', 'all_to_all'):
    assert (root / ('communication_' + mode + '.log')).read_text().splitlines().count('communication check PASS') == 4
for size in (32, 64):
    cases = {}
    for mode in ('pairwise', 'all_to_all'):
        label = 'small_{}_{}'.format(size, mode)
        cases[mode] = read(root / (label + '.log'), 'hpx', size, 1, 2, mode)
        gates[label] = dict(status='PASS', numerical_checks=3,
                            mode_reports=cases[mode]['mode_reports'])
    compare_plans(cases)
if '--gates-only' in sys.argv[2:]:
    print(json.dumps(dict(status='PASS', communication_passes=8, correctness_gates=gates), indent=2))
    sys.exit(0)

order = ('mpi_start', 'hpx_pairwise', 'hpx_all_to_all',
         'hpx_all_to_allrepeat', 'hpx_pairwiserepeat', 'mpi_end')
cases = {}
for label in order:
    mode = None if label.startswith('mpi_') else ('all_to_all' if 'all_to_all' in label else 'pairwise')
    backend = 'mpi' if mode is None else 'hpx'
    cases[label] = read(root / ('benchmark_' + label + '.log'), backend, 1024, 2, 7, mode)
    command = (root / ('benchmark_' + label + '.command')).read_text()
    for token in ('--size=1024', '--threads=64', '--warmups=2', '--samples=7',
                  'numactl --interleave=all', '--map-by ppr:1:node'):
        assert token in command, (label, token)
    if mode:
        for token in ('FFTW_HPX_TRANSPOSE_EXCHANGE=' + mode, '--hpx:threads=64',
                      '--hpx:ini=hpx.max_idle_backoff_time=10',
                      '--hpx:ini=hpx.parcel.mpi.sendimm=0',
                      '--hpx:ini=hpx.parcel.tcp.enable\\!=0',
                      '--hpx:ini=hpx.parcel.bootstrap\\!=mpi'):
            assert token in command, (label, token)
        assert 'default_scheduler_mode' not in command
compare_plans(cases)
metadata = (root / 'metadata.txt').read_text()
assert 'UCX_TLS=rc,sm,self' in metadata and 'OMPI_MCA_pml=ucx' in metadata
assert len(set((root / 'nodes.txt').read_text().splitlines())) == 4
assert (root / 'inherited_mpi_thread_level.txt').read_text() == 'is_set=\nvalue=\n'
compact = {}
for label, case in cases.items():
    entry = {key: value for key, value in case.items() if key != 'plans'}
    entry['plans_sha256'] = {direction: hashlib.sha256(plan.encode()).hexdigest() for direction, plan in case['plans'].items()}
    compact[label] = entry
medians = {label: case['median_seconds'] for label, case in compact.items()}
ratios = {}
for numerator in ('hpx_all_to_all', 'hpx_all_to_allrepeat'):
    for denominator in ('hpx_pairwise', 'hpx_pairwiserepeat', 'mpi_start', 'mpi_end'):
        ratios[numerator + '_over_' + denominator] = medians[numerator] / medians[denominator]
ratios['alltoall_repeat_over_initial'] = medians['hpx_all_to_allrepeat'] / medians['hpx_all_to_all']
ratios['pairwise_repeat_over_initial'] = medians['hpx_pairwiserepeat'] / medians['hpx_pairwise']
ratios['mpi_end_over_start'] = medians['mpi_end'] / medians['mpi_start']
summary = dict(status='PASS', license='GPL-2.0-or-later', run_order=order,
               cases=compact, median_seconds=medians, median_ratios=ratios,
               timed_samples=42, numerical_checks=18, communication_passes=8,
               preliminary_correctness_checks=12, correctness_gates=gates,
               normalized_local_plans_equal=True,
               plan_normalization='Remove literal /all_to_all exchange suffix and normalize hpx- to mpi- only',
               changed_parameter='FFTW_HPX_TRANSPOSE_EXCHANGE changes global exchange using one HPX executable',
               interpretation='Single fixed-order allocation; repeated cases and MPI bookends expose temporal drift but do not isolate all system variation.')
(root / 'alltoall_comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
