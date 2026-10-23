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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Independent validation of downloaded receive-job logs and binary artifacts."""

import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import sys


root, primary, published_prototypes, output = map(Path, sys.argv[1:])
labels = ('mpi', 'hpx_baseline', 'candidate_selected',
          'candidate_selected_backoff1', 'pooled_selected', 'direct_selected')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    return dict(part.split('=', 1) for part in line.split()[1:])


def manifest(path):
    pairs = [line.split('  ', 1) for line in path.read_text().splitlines()]
    assert len(pairs) == len({pair[1] for pair in pairs})
    return {name: digest for digest, name in pairs}


def match_remote_ok(manifest_name, log_name):
    expected = list(manifest(root / manifest_name))
    actual = [line[:-4] for line in (root / log_name).read_text().splitlines()
              if line.endswith(': OK')]
    assert actual == expected, (manifest_name, log_name)
    assert len(actual) == len((root / log_name).read_text().splitlines())
    return len(actual)


def verify_records(path, mapper):
    values = []
    for name, digest in manifest(path).items():
        local = mapper(name)
        assert sha(local) == digest, (local, digest)
        values.append({'recorded_path': name, 'local_file': str(local),
                       'sha256': digest})
    return values


def parse_benchmark(label):
    path = root / ('benchmark_' + label + '.log')
    text = path.read_text()
    lines = text.splitlines()
    config, = [fields(line) for line in lines if line.startswith('CONFIG ')]
    result, = [fields(line) for line in lines if line.startswith('RESULT ')]
    backend = 'mpi' if label == 'mpi' else 'hpx'
    assert config['backend'] == result['backend'] == backend
    expected = {'extent': '1024', 'ranks': '4', 'threads': '64',
                'precision': 'double', 'inplace': '1', 'layout': 'normal',
                'planner': 'FFTW_ESTIMATE', 'warmups': '2', 'samples': '7',
                'global_data_bytes': '17179869184',
                'max_local_allocation_bytes': '4294967296'}
    for key, value in expected.items():
        assert config[key] == value, (label, key, config[key])
    for key in ('extent', 'ranks', 'threads', 'samples'):
        assert result[key] == expected[key]
    assert result['status'] == 'PASS'
    checks = [fields(line) for line in lines if line.startswith('CHECK ')]
    assert [row['stage'] for row in checks] == ['forward_spectrum',
                                              'initial_roundtrip', 'final_roundtrip']
    for row in checks:
        assert row['backend'] == backend
        error, tolerance = float(row['relative_max_error']), float(row['tolerance'])
        assert math.isfinite(error) and 0 <= error <= tolerance == 1e-10
    records = [fields(line) for line in lines if line.startswith('SAMPLE ')]
    assert [int(row['index']) for row in records] == list(range(7))
    assert all(row['backend'] == backend for row in records)
    times = [float(row['max_rank_seconds']) for row in records]
    assert all(math.isfinite(value) and value > 0 for value in times)
    computed = dict(min_seconds=min(times), median_seconds=statistics.median(times),
                    mean_seconds=statistics.mean(times), max_seconds=max(times))
    for key, value in computed.items():
        assert math.isclose(value, float(result[key]), rel_tol=1e-13), (label, key)
    plans = {}
    for direction in ('FORWARD', 'BACKWARD'):
        matches = re.findall(r'PLAN_' + direction + r'_BEGIN\n(.*?)\nPLAN_' +
                             direction + r'_END', text, re.S)
        assert len(matches) == 1
        plans[direction.lower()] = matches[0]
    command = (root / ('benchmark_' + label + '.command')).read_text().splitlines()
    assert len(command) == 2 and command[0].startswith('cd ')
    argv = shlex.split(command[1])
    for arg in ('--size=1024', '--threads=64', '--warmups=2', '--samples=7',
                '--interleave=all', 'ppr:1:node', 'none'):
        assert arg in argv, (label, arg)
    if backend == 'hpx':
        for arg in ('--hpx:localities=4', '--hpx:threads=64', '--hpx:bind=none',
                    '--hpx:ini=hpx.parcel.mpi.enable=1',
                    '--hpx:ini=hpx.parcel.tcp.enable!=0',
                    '--hpx:ini=hpx.parcel.bootstrap=mpi'):
            assert arg in argv
    return {'configuration': config, 'checks': checks, 'result': result,
            'samples_seconds': times, 'recomputed_statistics': computed,
            'source_sha256': sha(path), 'plans': plans, 'argv': argv}


status = dict(line.split('\t', 1) for line in (root / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['exit_status'] == '0'
assert status['stage'] == 'complete' and status['job_id'] == '1125605'
accounting = (root / 'accounting.txt').read_text().splitlines()[1:]
assert all(line.split('|')[1:3] == ['COMPLETED', '0:0'] for line in accounting)
runs = {label: parse_benchmark(label) for label in labels}
mpi_plans = runs['mpi']['plans']
for label, run in runs.items():
    assert {direction: text.replace('hpx-', 'mpi-')
            for direction, text in run['plans'].items()} == mpi_plans
    if label != 'mpi':
        saved = json.loads((root / ('comparison_' + label + '.log')).read_text())
        for backend, selected in (('mpi', runs['mpi']), ('hpx', run)):
            for key in ('configuration', 'checks', 'result', 'samples_seconds', 'plans'):
                assert saved[backend][key] == selected[key]
        assert all(saved['normalized_plans_equal'].values())
        assert saved['hpx_over_mpi_median_ratio'] == (
            run['recomputed_statistics']['median_seconds'] /
            runs['mpi']['recomputed_statistics']['median_seconds'])
for run in runs.values():
    run['normalized_plan_sha256'] = {
        direction: hashlib.sha256(text.replace('hpx-', 'mpi-').encode()).hexdigest()
        for direction, text in run.pop('plans').items()}

selected = json.loads((root / 'runtime_selection.json').read_text())
assert selected['argv'] == (root / 'runtime_selection.argv').read_text().splitlines()
assert '--hpx:ini=hpx.parcel.mpi.multithreaded=1' in selected['argv']
backoff = '--hpx:ini=hpx.max_idle_backoff_time=1'
for label in labels[2:]:
    assert all(arg in runs[label]['argv'] for arg in selected['argv'])
    assert (backoff in runs[label]['argv']) == (label != 'candidate_selected')
job_text = (root / 'job.log').read_text()
gate_results = {}
for label in ('candidate', 'pooled_receive', 'direct_receive'):
    lines = (root / ('comm_check_' + label + '.log')).read_text().splitlines()
    assert lines.count('communication check PASS') == 4
    cycle_lines = [line for line in lines if line.startswith('communication check, cycle ')]
    assert len(cycle_lines) == 14
    for cycle in ('0', '1'):
        assert len([line for line in cycle_lines if 'cycle ' + cycle + ':' in line]) == 7
    compile_command = (root / ('compile_comm_check_' + label + '.command')).read_text()
    assert '-UNDEBUG' in compile_command and 'assert_enabled.h' in compile_command
    launch = (root / ('comm_check_' + label + '.command')).read_text()
    assert '--hpx:threads=2' in launch and r'hpx.parcel.tcp.enable\!=0' in launch
    marker = 'PASS comm_check_' + label + ' '
    assert marker in job_text and job_text.index(marker) < job_text.index('START benchmark_mpi ')
    gate_results[label] = {'rank_pass_records': 4, 'cycles': 2,
                           'checks_per_cycle': 7, 'assertions_forced': True,
                           'completed_before_benchmarks': True}

original_binary_checks = verify_records(root / 'binaries.sha256',
                                       lambda remote: primary / 'bin' / Path(remote).name)
candidate_check = verify_records(root / 'candidate_comm_check.sha256',
                                lambda remote: root / 'bin' / Path(remote).name)
frozen = {'direct_receive': '477f1243b68a303e370d97913279f9b312ed66c8a54811392083b9b6faec1590',
          'pooled_receive': '57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c'}
prototypes = {}
for name, expected in frozen.items():
    directory = root / 'prototypes' / name
    source = directory / 'source-hpx-comm.cpp'
    assert sha(source) == sha(published_prototypes / name / 'hpx-comm.cpp') == expected
    recorded = json.loads((directory / 'archive_members.json').read_text())
    archive = directory / 'libfftw3_hpx.a'
    members = subprocess.check_output(['ar', 't', str(archive)]).decode().splitlines()
    assert len(members) == len(set(members)) == len(recorded['before']) == 32
    actual = {member: hashlib.sha256(subprocess.check_output(
        ['ar', 'p', str(archive), member])).hexdigest() for member in members}
    assert actual == recorded['after']
    assert set(actual) == set(recorded['before'])
    changed = [member for member in members if actual[member] != recorded['before'][member]]
    assert changed == recorded['changed_members'] == ['hpx-comm.o']
    assert recorded['unchanged_members'] == 31
    assert sha(directory / 'hpx-comm.o') == actual['hpx-comm.o']
    def map_artifact(remote):
        path = Path(remote)
        if path.name == 'hpx-comm.cpp':
            return source
        if path.name == 'libfftw3_hpx.a':
            return archive
        return root / 'bin' / path.name
    artifacts = verify_records(directory / 'artifacts.sha256', map_artifact)
    prototypes[name] = {'source_sha256': expected, 'members': 32,
                        'changed_members': changed, 'unchanged_members': 31,
                        'downloaded_artifacts_verified': artifacts,
                        'before': recorded['before']}
assert prototypes['direct_receive']['before'] == prototypes['pooled_receive']['before']
for value in prototypes.values():
    value.pop('before')

unchanged = {}
for manifest_name, log_name in (
        ('baseline_inputs.sha256', 'baseline_unchanged.log'),
        ('binaries.sha256', 'binaries_unchanged.log'),
        ('candidate_source.sha256', 'candidate_source_unchanged.log'),
        ('prototype_inputs.sha256', 'prototypes_unchanged.log'),
        ('primary_candidate_archive.sha256', 'candidate_unchanged.log')):
    unchanged[manifest_name] = {'recorded_postrun_ok_count':
                               match_remote_ok(manifest_name, log_name)}
assert (root / 'baseline_inputs.sha256').read_bytes() == (primary / 'baseline_inputs.sha256').read_bytes()
assert (root / 'candidate_source.sha256').read_bytes() == (primary / 'candidate_source.sha256').read_bytes()
assert (root / 'primary_candidate_archive.sha256').read_bytes() == (primary / 'candidate.sha256').read_bytes()

summary = {
    'copyright': 'Copyright (c) 2026 Dominic C. Marcello', 'license': 'GPL-2.0-or-later',
    'status': 'PASS', 'job_id': 1125605, 'final_status': status,
    'benchmark_count': 6, 'sample_count': 42, 'numerical_check_count': 18,
    'plans_equal': True, 'runs': runs, 'communication_gates': gate_results,
    'prototype_archives': prototypes, 'original_binaries_rehashed': original_binary_checks,
    'candidate_check_rehashed': candidate_check, 'unchanged_remote_records': unchanged,
    'runtime_selection': selected,
    'validation_boundaries': [
        'Six raw benchmark logs parsed independently of the original summarizer; saved comparison records cross-checked.',
        'Downloaded prototype archives, bridge objects, executables and source snapshots were rehashed locally.',
        'Each downloaded archive has 32 members; actual member hashes match recorded after hashes and differ from recorded before only in hpx-comm.o.',
        'Original candidate archive is not downloaded; its before-member hashes and unchanged whole-archive digest are authenticated remote job records, not a fresh local hash.',
        'The three original executables were rehashed from the downloaded primary evidence.',
        'Complete original source and baseline-library preservation is supported by identical pre-run manifests and complete remote post-run OK records; those remote paths were not accessed.'
    ]}
output.write_text(json.dumps(summary, indent=2) + '\n')
print('RECEIVE_EVIDENCE_PASS six cases; 42 samples; 18 numerical checks; three communication gates; two 32-member archives')
for label, run in runs.items():
    print(label, 'median_seconds', run['recomputed_statistics']['median_seconds'])
