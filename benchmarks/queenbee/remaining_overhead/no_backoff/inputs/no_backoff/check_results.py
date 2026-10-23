#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later

import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys


root, source = map(Path, sys.argv[1:3])
expected = dict(extent='1024', ranks='4', threads='64', precision='double',
                inplace='1', layout='normal', planner='FFTW_ESTIMATE',
                warmups='2', samples='7')
mpi_labels = ('mpi_start', 'mpi_end')
hpx_labels = ('hpx_cap10', 'hpx_no_backoff', 'hpx_cap10repeat')
order = ('mpi_start', 'hpx_cap10', 'hpx_no_backoff',
         'hpx_cap10repeat', 'mpi_end')
cases = {}

for mpi_label in mpi_labels:
    for hpx_label in hpx_labels:
        command = [sys.executable, '-I', str(source / 'benchmarks/summarize.py'),
                   str(root / ('benchmark_' + mpi_label + '.log')),
                   str(root / ('benchmark_' + hpx_label + '.log'))]
        comparison = json.loads(subprocess.check_output(
            command, universal_newlines=True))
        assert all(comparison['normalized_plans_equal'].values())
        for backend, label in (('mpi', mpi_label), ('hpx', hpx_label)):
            case = comparison[backend]
            assert all(case['configuration'][key] == value
                       for key, value in expected.items())
            assert case['result']['status'] == 'PASS'
            assert len(case['samples_seconds']) == 7
            assert len(case['checks']) == 3
            assert {check['stage'] for check in case['checks']} == {
                'forward_spectrum', 'initial_roundtrip', 'final_roundtrip'}
            assert all(float(check['relative_max_error']) <
                       float(check['tolerance']) == 1e-10
                       for check in case['checks'])
            if label in cases:
                assert cases[label] == case
            cases[label] = case

assert cases['mpi_start']['plans'] == cases['mpi_end']['plans']
assert all(cases[label]['plans'] == cases['hpx_cap10']['plans']
           for label in hpx_labels)
assert (root / 'communication_cap10.log').read_text().splitlines().count(
    'communication check PASS') == 4
assert (root / 'communication_no_backoff.log').read_text().splitlines().count(
    'communication check PASS') == 4

for label in order:
    command = (root / ('benchmark_' + label + '.command')).read_text()
    assert '--size=1024' in command and '--threads=64' in command
    assert '--warmups=2' in command and '--samples=7' in command
    assert 'numactl --interleave=all' in command
    if label in hpx_labels:
        assert '--hpx:threads=64' in command
        assert '--hpx:ini=hpx.max_idle_backoff_time=10' in command
        assert '--hpx:ini=hpx.parcel.mpi.sendimm=0' in command
        assert '--hpx:ini=hpx.parcel.tcp.enable\\!=0' in command
        assert '--hpx:ini=hpx.parcel.bootstrap\\!=mpi' in command
        assert ('--hpx:ini=hpx.default_scheduler_mode=1255' in command) == (
            label == 'hpx_no_backoff')

compact = {}
for label in order:
    case = cases[label]
    values = case['samples_seconds']
    compact[label] = dict(samples_seconds=values,
                          median_seconds=statistics.median(values),
                          min_seconds=min(values),
                          mean_seconds=statistics.mean(values),
                          max_seconds=max(values),
                          checks=case['checks'],
                          plans_sha256={key: hashlib.sha256(
                              value.encode('utf-8')).hexdigest()
                              for key, value in case['plans'].items()},
                          raw_log_sha256=hashlib.sha256((root / (
                              'benchmark_' + label + '.log')).read_bytes()
                              ).hexdigest())

medians = {label: case['median_seconds'] for label, case in compact.items()}
ratios = {
    'no_backoff_over_initial_10ms':
        medians['hpx_no_backoff'] / medians['hpx_cap10'],
    'no_backoff_over_repeated_10ms':
        medians['hpx_no_backoff'] / medians['hpx_cap10repeat'],
    'no_backoff_over_mpi_start':
        medians['hpx_no_backoff'] / medians['mpi_start'],
    'no_backoff_over_mpi_end':
        medians['hpx_no_backoff'] / medians['mpi_end'],
    'cap10_repeat_over_initial':
        medians['hpx_cap10repeat'] / medians['hpx_cap10'],
    'mpi_end_over_start': medians['mpi_end'] / medians['mpi_start'],
}
inherited = dict(line.split('=', 1) for line in (
    root / 'inherited_mpi_thread_level.txt').read_text().splitlines())
summary = dict(status='PASS', license='GPL-2.0-or-later',
               configuration=expected, run_order=order, cases=compact,
               median_seconds=medians, median_ratios=ratios,
               inherited_mpi_thread_level=inherited,
               timed_samples=35, numerical_checks=15,
               communication_passes=8,
               all_normalized_plans_equal=True,
               source_mode_default=3303,
               source_mode_no_backoff=1255,
               changed_parameter='hpx.default_scheduler_mode clears only enable_idle_backoff',
               interpretation='One fixed-order allocation with MPI bookends and repeated 10 ms control; CPU and temporal variation are not isolated.')
(root / 'no_backoff_comparison.json').write_text(json.dumps(
    summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
