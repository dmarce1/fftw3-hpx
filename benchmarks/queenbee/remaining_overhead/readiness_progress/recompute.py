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

"""Reduce six readiness-cap logs and one HPX-only profile; no execution or build."""
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import sys
import subprocess
import tempfile

base = Path(__file__).resolve().parent
root = Path(sys.argv[1]) if len(sys.argv) > 1 else base / 'raw/1125974'
order = ['mpi_start', 'lean_baseline1000', 'lean_backoff10', 'lean_baseline1000repeat', 'mpi_end', 'hpx_profile10']
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

for name in ('job.sbatch','common.sh','PROVENANCE.json'):
    assert (root/name).read_bytes() == (base/'inputs/readiness_progress'/name).read_bytes()
for job, sibling in [('1125925','confirmation'),('1125966','lean_profile')]:
    for name in ('FINAL_STATUS','artifacts.sha256','fixed_inputs.sha256','reused_binaries.sha256','archive_members.log'):
        assert (root/'reused_artifacts'/(job+'_'+name)).read_bytes() == (base.parent/sibling/'raw'/job/name).read_bytes()

status = dict(line.split('\t', 1) for line in (root / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['exit_status'] == '0' and status['stage'] == 'complete'
assert status['job_id'] == '1125974' and status['sendimm'] == '0'
assert (root / 'READINESS_PROGRESS_FINAL_STATUS').read_bytes() == (root / 'FINAL_STATUS').read_bytes()
stages = [line.split('\t') for line in (root / 'results.tsv').read_text().splitlines()]
assert stages and all(row[1] == 'PASS' for row in stages)
assert not any(row[0].startswith(('compile_', 'replace_')) for row in stages)
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
    cases[label] = dict(role=('diagnostic' if label == 'hpx_profile10' else 'primary'), samples_seconds=values, checks=checks, raw_log_sha256=digest(path), plans_sha256={key: hashlib.sha256(value.encode()).hexdigest() for key, value in plan.items()}, **computed)
normalized = {tuple(value.replace('hpx-', 'mpi-') for value in plans[label].values()) for label in order}
assert len(normalized) == 1
assert plans['mpi_start'] == plans['mpi_end']
assert all(plans[label] == plans['lean_baseline1000'] for label in order if not label.startswith('mpi_'))

# Token comparison proves the cap is the only launch argument changed across
# lean runs. The same on-cluster executable hash is checked separately below.
baseline = command('benchmark_lean_baseline1000')
repeated = command('benchmark_lean_baseline1000repeat')
short = command('benchmark_lean_backoff10')
assert baseline == repeated
assert baseline.count('--hpx:ini=hpx.max_idle_backoff_time=1000') == 1
assert short.count('--hpx:ini=hpx.max_idle_backoff_time=10') == 1
short[short.index('--hpx:ini=hpx.max_idle_backoff_time=10')] = '--hpx:ini=hpx.max_idle_backoff_time=1000'
assert short == baseline
required = ['--hpx:threads=64', '--hpx:ini=hpx.parcel.mpi.sendimm=0', '--hpx:ini=hpx.parcel.mpi.background_threads=1', '--hpx:ini=hpx.max_background_threads=1', '--hpx:ini=hpx.parcel.mpi.multithreaded=1', '--hpx:ini=hpx.parcel.tcp.enable!=0', '--hpx:ini=hpx.parcel.mpi.enable!=1', '--hpx:ini=hpx.parcel.bootstrap!=mpi', '--hpx:bind=none']
assert all(baseline.count(value) == 1 for value in required)
assert not any('max_idle_loop_count=' in value or 'max_busy_loop_count=' in value for value in baseline)
assert command('benchmark_mpi_start') == command('benchmark_mpi_end')
diagnostic = command('benchmark_hpx_profile10')
index = diagnostic.index('env')
assert diagnostic[index + 1].startswith('FFTW_REMAINING_PROFILE_DIR=')
diagnostic = diagnostic[:index] + diagnostic[index + 2:]
index = next(i for i, value in enumerate(diagnostic) if value.endswith('/1125966/bin/hpx_profile'))
diagnostic[index] = baseline[index]
short_actual = command('benchmark_lean_backoff10')
assert diagnostic == short_actual
communication = {}
for cap in ('1000', '10'):
    label = 'cap' + cap
    count = (root / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS')
    assert count == 4
    communication[label] = count
    args = command('communication_' + label)
    assert args.count('--hpx:threads=2') == 1 and '--hpx:threads=64' not in args
    assert '--hpx:ini=hpx.parcel.mpi.sendimm=0' in args
    assert args.count('--hpx:ini=hpx.max_idle_backoff_time=' + cap) == 1
first_comm = command('communication_cap1000')
second_comm = command('communication_cap10')
second_comm[second_comm.index('--hpx:ini=hpx.max_idle_backoff_time=10')] = '--hpx:ini=hpx.max_idle_backoff_time=1000'
assert first_comm == second_comm

reuse = manifest(root / 'reused_binaries.sha256')
expected_binaries = manifest(base / 'inputs/readiness_progress/EXPECTED_BINARIES.sha256')
assert reuse == expected_binaries and len(reuse) == 4
prior_artifacts = manifest(root / 'reused_artifacts/1125925_artifacts.sha256')
profile_artifacts = manifest(root / 'reused_artifacts/1125966_artifacts.sha256')
prior_reused = manifest(root / 'reused_artifacts/1125925_reused_binaries.sha256')
for name, value in reuse.items():
    if '/1125925/' in name:
        assert prior_artifacts[name.split('/1125925/', 1)[1]] == value
    elif '/1125966/' in name:
        assert profile_artifacts[name.split('/1125966/', 1)[1]] == value
    else:
        assert prior_reused[name] == value
assert any(name in baseline and value == '42c8821d64faaf27411e1714fe05ed37d4feb4aa21fe79d4db6ec1b742f66496' for name, value in reuse.items())
members = json.loads((root / 'reused_artifacts/1125925_archive_members.log').read_text())
assert members['status'] == 'PASS' and members['changed'] == ['hpx-comm.o'] and members['unchanged'] == 31
assert list(members['before']) == list(members['after'])
assert [name for name in members['before'] if members['before'][name] != members['after'][name]] == ['hpx-comm.o']
profile_members = json.loads((root / 'reused_artifacts/1125966_archive_members.log').read_text())
assert profile_members['hpx_profile']['before'] == members['after']
for label, expected_changes in [('hpx_profile', {'hpx-comm.o','transpose-pairwise.o'}), ('mpi_profile', {'transpose-pairwise.o'}), ('threads_profile', {'libfftw3_threads_la-threads.o'})]:
    info = profile_members[label]
    assert set(info['before']) == set(info['after']) == set(info['ordered_members'])
    assert {name for name in info['before'] if info['before'][name] != info['after'][name]} == set(info['changed']) == expected_changes
    for name, record in info['replacement_objects'].items():
        assert record['sha256'] == info['after'][name] == profile_artifacts['objects/' + label + '/' + name]
preservation = {}
for name in ('fixed_inputs_unchanged.log', 'reused_binaries_unchanged.log', 'expected_binaries.log'):
    rows = (root / name).read_text().splitlines()
    assert rows and all(line.endswith(': OK') for line in rows)
    preservation[name] = len(rows)
for source, receipt in [('fixed_inputs.sha256', 'fixed_inputs_unchanged.log'), ('reused_binaries.sha256', 'reused_binaries_unchanged.log')]:
    assert [line[:-4] for line in (root / receipt).read_text().splitlines()] == list(manifest(root / source))
assert (root / 'prior_artifacts.log').read_bytes() == (root / 'prior_artifacts_unchanged.log').read_bytes()
# Prior-artifact logs also contain the JSON transformed-source proof.
rows = (root / 'prior_artifacts.log').read_text().splitlines()
json_start = rows.index('{')
assert json_start > 0 and all(line.endswith(': OK') for line in rows[:json_start])
preservation['prior_artifacts.log'] = json_start
assert json.loads('\n'.join(rows[json_start:]))['status'] == 'PASS'
for name in ('prior_clean_checks.log', 'prior_profile_checks.log'):
    assert json.loads((root / name).read_text())['status'] == 'PASS'
for label in ('lean', 'comm', 'profile'):
    data = json.loads((root / ('dependencies_' + label + '.log')).read_text())
    assert data['status'] == 'PASS' and data['apex_present'] is False
    assert all('/fftw3_hpx_remaining_20261023/lean_hpx/install/' in path for path in data['hpx_libraries'])
    assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in data['mpi_libraries'])
data = json.loads((root / 'mpi_dependencies.log').read_text())
assert data['status'] == 'PASS' and not data['hpx_present'] and not data['apex_present']
assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in data['mpi_libraries'])
inherited = dict(line.split('=',1) for line in (root / 'inherited_mpi_thread_level.txt').read_text().splitlines())
assert not any('OMPI_MPI_THREAD_LEVEL=' in value for label in order for value in command('benchmark_' + label))

# Retain the full analyzer JSON once; reconstruct its input from raw benchmark
# plus four per-rank files instead of storing another duplicate combined log.
def equivalent(left, right):
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

analysis = json.loads((root / 'hpx_profile10.json').read_text())
assert analysis['status'] == 'PASS' and analysis['diagnostic_only'] and len(analysis['runs']) == 1
assert not any(key.endswith('hpx_minus_mpi') for key in analysis)
with tempfile.TemporaryDirectory(prefix='readiness-recompute-') as temporary:
    temporary = Path(temporary)
    path = temporary / 'analysis_hpx_profile10.log'
    data = (root / 'benchmark_hpx_profile10.log').read_bytes()
    assert len(list((root / 'profile_hpx').iterdir())) == 4
    for rank in range(4):
        data += (root / 'profile_hpx' / ('hpx-' + str(rank) + '.log')).read_bytes()
    path.write_bytes(data)
    output = temporary / 'profile.json'
    analyzer = base.parent / 'lean_profile/inputs/lean_profile/profile/analyze.py'
    subprocess.check_output([sys.executable, '-I', str(analyzer), str(path), '--json', str(output)])
    reproduced = json.loads(output.read_text())
    reproduced['runs'][0]['path'] = analysis['runs'][0]['path']
    equivalent(reproduced, analysis)
run = analysis['runs'][0]
assert len(run['rank_samples']) == 28 and len(run['critical_rank_samples']) == 7
assert all(len(row['metrics']) == 38 for row in run['rank_samples'])
assert run['normalized_plan_sha256'] == {key: hashlib.sha256(value.replace('hpx-', 'mpi-').encode()).hexdigest() for key,value in plans['lean_backoff10'].items()}
counters = {}
for metric in ('message_load', 'direct_message_load', 'owned_message_load', 'required_posted_message_load', 'receive_memcpy_wall', 'pool_hit', 'pool_miss'):
    counters[metric] = {key:sum(row['metrics'][metric][key] for row in run['rank_samples']) for key in ('calls','bytes')}
assert counters['direct_message_load']['calls'] == counters['required_posted_message_load']['calls'] == 168
assert counters['owned_message_load']['calls'] == counters['receive_memcpy_wall']['bytes'] == 0

medians = {label: cases[label]['median_seconds'] for label in order}
ratios = {label + '_over_' + bookend: medians[label] / medians[bookend] for label in order if not label.startswith('mpi_') and label != 'hpx_profile10' for bookend in ('mpi_start', 'mpi_end')}
ratios['mpi_end_over_mpi_start'] = medians['mpi_end'] / medians['mpi_start']
ratios['lean_repeat_over_initial_baseline'] = medians['lean_baseline1000repeat'] / medians['lean_baseline1000']
ratios['backoff10_over_initial_baseline'] = medians['lean_backoff10'] / medians['lean_baseline1000']
ratios['backoff10_over_repeated_baseline'] = medians['lean_backoff10'] / medians['lean_baseline1000repeat']
ratios['diagnostic_hpx10_over_clean_hpx10'] = medians['hpx_profile10'] / medians['lean_backoff10']
original = json.loads((root / 'readiness_progress_comparison.json').read_text())
assert original['status'] == 'PASS' and original['sendimm'] == 0
assert original['median_seconds'] == medians and original['median_ratios'] == ratios
assert original['configuration'] == expected and original['run_order'] == order
assert original['cases'] == cases
assert original['inherited_mpi_thread_level'] == inherited
equivalent(original['diagnostic']['critical_rank_means'], run['critical_rank_means'])
equivalent(original['diagnostic']['critical_rank_medians'], run['critical_rank_medians'])
previous = json.loads((base.parent/'lean_profile/raw/1125966/profile_analysis.json').read_text())
prior_hpx, = [value for value in previous['runs'] if value['configuration']['backend'] == 'hpx']
prior_means = prior_hpx['critical_rank_means']
current_means = run['critical_rank_means']
context = dict(scope='Cross-allocation context only; not paired MPI phases and not isolated causality', prior_job='1125966', prior_readiness_mean_seconds=prior_means['readiness_phase_wall'], prior_maximum_accumulated_readiness_seconds=max(row['readiness_phase_seconds'] for row in prior_hpx['sample_maximum_readiness_phase']), current_maximum_accumulated_readiness_seconds=max(row['readiness_phase_seconds'] for row in run['sample_maximum_readiness_phase']), prior_process_cpu_seconds=prior_means['process_cpu_seconds'], prior_callback_cpu_seconds=prior_means['task_thread_cpu_observed'], process_cpu_relative_percent=100*(current_means['process_cpu_seconds']/prior_means['process_cpu_seconds']-1))
summary = dict(cross_allocation_context=context, diagnostic=dict(critical_rank_means=run['critical_rank_means'], critical_rank_medians=run['critical_rank_medians'], counters_all_ranks=counters, sample_maximum_readiness_phase=run['sample_maximum_readiness_phase'], scope='One HPX-only diagnostic in this allocation; no prior MPI phase comparison'), profile_analysis_reproduced=True, diagnostic_rank_samples=28, diagnostic_metric_rows=1064, inherited_mpi_thread_level=inherited, license='GPL-2.0-or-later', status='PASS', job_id='1125974', job_status=status, configuration=expected, sendimm=0, run_order=order, cases=cases, median_seconds=medians, median_ratios=ratios, mpi_bookend_change_percent=100 * (ratios['mpi_end_over_mpi_start'] - 1), lean_baseline_repeat_change_percent=100 * (ratios['lean_repeat_over_initial_baseline'] - 1), timed_samples=42, numerical_checks=18, all_normalized_plans_equal=True, all_hpx_plans_byte_equal=True, exact_cap_only_lean_commands=True, exact_mpi_bookend_commands=True, communication_passes=communication, reused_binary_hashes=reuse, preservation_receipt_counts=preservation, job_comparison_reproduced=True, stage_count=len(stages), interpretation='Both MPI bookends and both HPX baselines remain separate. Only the idle backoff cap changes across three clean lean runs. The diagnostic is instrumented and unpaired with any previous MPI profile. One fixed-order allocation does not identify sleep causality or remove temporal/node variation. Binary hashes are cluster receipts, not local rehashes of omitted binaries.')
print(json.dumps(summary, indent=2))
