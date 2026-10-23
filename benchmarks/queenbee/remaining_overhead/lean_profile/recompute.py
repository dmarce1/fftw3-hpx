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

"""Reduce published raw records; no FFT, compilation, or remote access."""
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import subprocess
import sys
import tempfile

base = Path(__file__).resolve().parent
raw = base / 'raw/1125966'
order = ['mpi', 'lean_control', 'mpi_profile', 'hpx_profile', 'mpi_thread_multiple']
roles = ['primary', 'primary', 'diagnostic', 'diagnostic', 'auxiliary']
configuration = dict(extent='1024', ranks='4', threads='64', precision='double',
                     inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line):
    pairs = [value.split('=', 1) for value in line.split()[1:]]
    assert all(len(value) == 2 for value in pairs)
    assert len(pairs) == len({key for key, value in pairs})
    return dict(pairs)


def manifest(path):
    rows = [row.split(None, 1) for row in path.read_text().splitlines()]
    assert len(rows) == len({name.lstrip('*') for value, name in rows})
    return {name.lstrip('*'): value for value, name in rows}


def command(name):
    lines = (raw / (name + '.command')).read_text().splitlines()
    assert len(lines) == 2 and lines[0].startswith('cd ')
    return shlex.split(lines[1])


def equivalent(left, right):
    """Allow derived floating-point roundoff; preserve integer counters exactly."""
    if isinstance(left, dict):
        assert left.keys() == right.keys()
        for key in left:
            equivalent(left[key], right[key])
    elif isinstance(left, list):
        assert len(left) == len(right)
        for first, second in zip(left, right):
            equivalent(first, second)
    elif isinstance(left, float):
        assert isinstance(right, float) and math.isclose(left, right, rel_tol=0, abs_tol=5e-15)
    else:
        assert left == right


status = dict(row.split('\t', 1) for row in (raw / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['exit_status'] == '0'
assert status['job_id'] == '1125966' and status['stage'] == 'complete' and status['sendimm'] == '0'
assert (raw / 'FINAL_STATUS').read_bytes() == (raw / 'LEAN_PROFILE_FINAL_STATUS').read_bytes()
stages = [row.split('\t') for row in (raw / 'results.tsv').read_text().splitlines()]
assert len(stages) == 45 and all(row[1] == 'PASS' for row in stages)
assert [row[0][10:] for row in stages if row[0].startswith('benchmark_')] == order
cases, plans = {}, {}
for label, role in zip(order, roles):
    path = raw / ('benchmark_' + label + '.log')
    text = path.read_text()
    lines = text.splitlines()
    config, = [fields(line) for line in lines if line.startswith('CONFIG ')]
    result, = [fields(line) for line in lines if line.startswith('RESULT ')]
    backend = 'mpi' if label.startswith('mpi') else 'hpx'
    assert config['backend'] == result['backend'] == backend and result['status'] == 'PASS'
    assert all(config[key] == value for key, value in configuration.items())
    samples = [fields(line) for line in lines if line.startswith('SAMPLE ')]
    checks = [fields(line) for line in lines if line.startswith('CHECK ')]
    assert len(samples) == 7 and [int(row['index']) for row in samples] == list(range(7))
    assert all(row['backend'] == backend for row in samples + checks)
    values = [float(row['max_rank_seconds']) for row in samples]
    assert all(math.isfinite(value) and value > 0 for value in values)
    stats = dict(min_seconds=min(values), mean_seconds=statistics.mean(values),
                 median_seconds=statistics.median(values), max_seconds=max(values))
    for key, value in stats.items():
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
    cases[label] = dict(role=role, samples_seconds=values, checks=checks,
                       raw_log_sha256=digest(path), plans_sha256={key: hashlib.sha256(value.encode()).hexdigest() for key, value in plan.items()}, **stats)
assert len({tuple(value.replace('hpx-', 'mpi-') for value in plans[label].values()) for label in order}) == 1
assert plans['mpi'] == plans['mpi_profile'] == plans['mpi_thread_multiple']
assert plans['lean_control'] == plans['hpx_profile']

mpi = command('benchmark_mpi')
auxiliary = command('benchmark_mpi_thread_multiple')
index = auxiliary.index('env')
assert auxiliary[index + 1] == 'OMPI_MPI_THREAD_LEVEL=3'
assert auxiliary[:index] + auxiliary[index + 2:] == mpi
assert all('OMPI_MPI_THREAD_LEVEL' not in token for token in mpi)
hpx = command('benchmark_lean_control')
for token in ['--hpx:threads=64', '--hpx:ini=hpx.max_idle_backoff_time=1000',
              '--hpx:ini=hpx.parcel.mpi.sendimm=0', '--hpx:ini=hpx.parcel.tcp.enable!=0',
              '--hpx:ini=hpx.parcel.mpi.enable!=1', '--hpx:ini=hpx.parcel.bootstrap!=mpi',
              '--hpx:ini=hpx.parcel.mpi.background_threads=1', '--hpx:ini=hpx.max_background_threads=1',
              '--hpx:ini=hpx.parcel.mpi.multithreaded=1']:
    assert hpx.count(token) == 1
for label, clean in [('mpi_profile', mpi), ('hpx_profile', hpx)]:
    args = command('benchmark_' + label)
    index = args.index('env')
    assert args[index + 1].startswith('FFTW_REMAINING_PROFILE_DIR=')
    args = args[:index] + args[index + 2:]
    executable_index = next(i for i, token in enumerate(args) if token.endswith('/bin/' + label))
    args[executable_index] = clean[executable_index]
    assert args == clean, label
for label in ('lean_control', 'hpx_profile'):
    assert (raw / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS') == 4
    assert command('communication_' + label).count('--hpx:threads=2') == 1

probes = {}
pattern = re.compile(r'MPI_THREAD_PROBE rank=(\d+) requested=(\d+) provided=(\d+) query=(\d+) env_is_set=(\d+) env=(\S+) forced=(\d+) status=(\w+)')
for label in ('normal', 'multiple'):
    rows = pattern.findall((raw / ('mpi_thread_probe_' + label + '.log')).read_text())
    assert len(rows) == 4 and {int(row[0]) for row in rows} == set(range(4))
    for rank, requested, provided, query, is_set, env, forced, result in rows:
        assert requested == '1' and provided == query and result == 'PASS'
        assert (provided, is_set, env, forced) == (('1', '0', '<unset>', '0') if label == 'normal' else ('3', '1', '3', '1'))
    probes[label] = [dict(rank=int(row[0]), requested=int(row[1]), provided=int(row[2]), query=int(row[3]), env_is_set=int(row[4]), env=row[5]) for row in rows]
assert (raw / 'inherited_mpi_thread_level.txt').read_text() == 'is_set=\nvalue=\n'

for label in ('mpi_control', 'mpi_profile'):
    info = json.loads((raw / (label + '_dependencies.log')).read_text())
    assert info['status'] == 'PASS' and not info['hpx_present'] and not info['apex_present']
    assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in info['mpi_libraries'])
for label in ('lean_control', 'hpx_profile', 'hpx_profile_comm_check'):
    info = json.loads((raw / ('dependencies_' + label + '.log')).read_text())
    assert info['status'] == 'PASS' and not info['apex_present']
    assert all('/lean_hpx/install/' in path for path in info['hpx_libraries'])
    assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in info['mpi_libraries'])

members = json.loads((raw / 'archive_members.log').read_text())
artifacts = manifest(raw / 'artifacts.sha256')
member_summary = {}
for label, expected in [('hpx_profile', {'hpx-comm.o', 'transpose-pairwise.o'}),
                        ('mpi_profile', {'transpose-pairwise.o'}),
                        ('threads_profile', {'libfftw3_threads_la-threads.o'})]:
    value = members[label]
    before, after = value['before'], value['after']
    assert set(before) == set(after) == set(value['ordered_members'])
    changed = {key for key in before if before[key] != after[key]}
    assert changed == set(value['changed']) == expected
    assert value['unchanged'] == len(before) - len(expected)
    for name, record in value['replacement_objects'].items():
        assert after[name] == record['sha256'] == artifacts['objects/' + label + '/' + name]
    member_summary[label] = dict(members=len(before), changed=sorted(changed), unchanged=value['unchanged'])
prior = raw / 'reused_artifacts'
old_members = json.loads((prior / '1125925_archive_members.log').read_text())
assert members['hpx_profile']['before'] == old_members['after']
reuse = manifest(raw / 'reused_binaries.sha256')
old_artifacts = manifest(prior / '1125925_artifacts.sha256')
old_reuse = manifest(prior / '1125925_reused_binaries.sha256')
for path, value in reuse.items():
    assert value == (old_artifacts[path.split('/1125925/', 1)[1]] if '/1125925/' in path else old_reuse[path])
receipts = {}
for name in ('fixed_inputs_unchanged.log', 'reused_binaries_unchanged.log', 'artifacts_recheck.log', 'prior_artifacts.log', 'prior_artifacts_unchanged.log'):
    lines = (raw / name).read_text().splitlines()
    assert lines and all(line.endswith(': OK') for line in lines)
    receipts[name] = len(lines)
assert (raw / 'prior_artifacts.log').read_bytes() == (raw / 'prior_artifacts_unchanged.log').read_bytes()
assert (raw / 'transformed_sources.log').read_bytes() == (raw / 'transformed_sources_unchanged.log').read_bytes()
for name, receipt in [('fixed_inputs.sha256', 'fixed_inputs_unchanged.log'), ('reused_binaries.sha256', 'reused_binaries_unchanged.log'), ('artifacts.sha256', 'artifacts_recheck.log')]:
    assert list(manifest(raw / name)) == [line[:-4] for line in (raw / receipt).read_text().splitlines()]
for label in ('compile_mpi_profile', 'compile_hpx_profile'):
    assert sum(token.endswith('/objects/diagnostic/remaining_profile.o') for token in command(label)) == 1

original_analysis = json.loads((raw / 'profile_analysis.json').read_text())
with tempfile.TemporaryDirectory(prefix='fftw-lean-profile-') as temporary:
    temp = Path(temporary)
    logs = []
    for backend in ('mpi', 'hpx'):
        path = temp / ('analysis_' + backend + '_profile.log')
        data = (raw / ('benchmark_' + backend + '_profile.log')).read_bytes()
        for rank in range(4):
            data += (raw / ('profile_' + backend) / (backend + '-' + str(rank) + '.log')).read_bytes()
        path.write_bytes(data)
        assert len(list((raw / ('profile_' + backend)).iterdir())) == 4
        logs.append(path)
    output = temp / 'analysis.json'
    subprocess.check_output([sys.executable, '-I', str(base / 'inputs/lean_profile/profile/analyze.py')] + [str(path) for path in logs] + ['--json', str(output)])
    reproduced = json.loads(output.read_text())
    for actual, original in zip(reproduced['runs'], original_analysis['runs']):
        actual['path'] = original['path']
    equivalent(reproduced, original_analysis)

diagnostics = {}
for run in original_analysis['runs']:
    backend = run['configuration']['backend']
    assert len(run['rank_samples']) == 28 and len(run['critical_rank_samples']) == 7
    assert all(len(row['metrics']) == 38 for row in run['rank_samples'])
    counters = {}
    for metric in ('message_load', 'direct_message_load', 'owned_message_load', 'empty_message_load', 'required_posted_message_load', 'receive_memcpy_wall', 'pool_hit', 'pool_miss'):
        counters[metric] = {key: sum(row['metrics'][metric][key] for row in run['rank_samples']) for key in ('calls', 'bytes')}
    diagnostics[backend] = dict(critical_rank_means=run['critical_rank_means'], critical_rank_medians=run['critical_rank_medians'],
        critical_rank_by_sample=[row['rank'] for row in run['critical_rank_samples']], counters_all_ranks=counters,
        sample_maximum_readiness_phase=run['sample_maximum_readiness_phase'])
assert diagnostics['hpx']['counters_all_ranks']['direct_message_load']['calls'] == 168
assert diagnostics['hpx']['counters_all_ranks']['required_posted_message_load']['calls'] == 168
assert diagnostics['hpx']['counters_all_ranks']['receive_memcpy_wall']['bytes'] == 0
comparison = json.loads((raw / 'lean_profile_comparison.json').read_text())
assert comparison['cases'] == cases and comparison['run_order'] == order
assert comparison['mpi_thread_probe'] == probes
medians = {key: cases[key]['median_seconds'] for key in order}
ratios = dict(primary_lean_over_mpi=medians['lean_control'] / medians['mpi'],
    diagnostic_hpx_over_diagnostic_mpi=medians['hpx_profile'] / medians['mpi_profile'],
    mpi_instrumented_over_control=medians['mpi_profile'] / medians['mpi'],
    hpx_instrumented_over_control=medians['hpx_profile'] / medians['lean_control'],
    auxiliary_mpi_multiple_over_original_mpi=medians['mpi_thread_multiple'] / medians['mpi'])
assert ratios == comparison['median_ratios']
summary = dict(license='GPL-2.0-or-later', status='PASS', job_id='1125966', job_status=status, run_order=order,
    configuration=configuration, cases=cases, median_ratios=ratios, timed_samples=35, numerical_checks=15,
    diagnostic_rank_sample_totals=56, diagnostic_metric_rows=2128, all_normalized_plans_equal=True,
    profile_analysis_reproduced=True, derived_float_comparison_absolute_tolerance_seconds=5e-15,
    raw_integer_counters_compared_exactly=True, archive_member_summary=member_summary, preservation_receipts=receipts,
    mpi_thread_probe=probes, reused_binary_hashes=reuse, diagnostics=diagnostics,
    critical_rank_mean_delta_hpx_minus_mpi=original_analysis['critical_rank_mean_delta_hpx_minus_mpi'],
    interpretation='Primary, diagnostic and auxiliary roles remain distinct. Diagnostic phases are inclusive elapsed scopes with substantial HPX perturbation/temporal uncertainty; readiness does not isolate network latency. The current probe does not establish historical MPI thread levels. Omitted binaries are represented by cluster hash receipts.')
print(json.dumps(summary, indent=2))
