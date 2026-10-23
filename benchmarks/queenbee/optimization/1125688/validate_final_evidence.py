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

"""Validate final-run raw logs and reused provenance without building or networking."""

import csv
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import statistics
import sys

root, previous, prototypes, archive, output = map(Path, sys.argv[1:])
labels = ('mpi', 'candidate', 'pooled_receive', 'direct_receive')

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
assert status['stage'] == 'complete' and status['job_id'] == '1125688'
accounting = list(csv.DictReader((root / 'accounting.txt').read_text().splitlines(), delimiter='|'))
assert accounting and all(row['State'] == 'COMPLETED' and row['ExitCode'] == '0:0' for row in accounting)
assert (root / 'slurm.err').read_bytes() == b''
assert sha(archive) == '9e7ac02bac1ae45081e067bd73ef46f4a1dd618be79708dff6163f1d546f92b3'
runs = {label: parse_benchmark(label) for label in labels}
expected_runtime = ['--hpx:ignore-batch-env', '--hpx:localities=4', '--hpx:threads=64',
                    '--hpx:bind=none', '--hpx:ini=hpx.parcel.mpi.enable=1',
                    '--hpx:ini=hpx.parcel.mpi.priority=1000', '--hpx:ini=hpx.parcel.tcp.enable!=0',
                    '--hpx:ini=hpx.parcel.bootstrap=mpi', '--hpx:ini=hpx.parcel.mpi.background_threads=1',
                    '--hpx:ini=hpx.max_background_threads=1', '--hpx:ini=hpx.parcel.mpi.multithreaded=1',
                    '--hpx:ini=hpx.max_idle_backoff_time=1000']
assert (root / 'runtime.argv').read_text().splitlines() == expected_runtime
benchmark_argv = ['--size=1024', '--threads=64', '--warmups=2', '--samples=7']
assert (root / 'benchmark.argv').read_text().splitlines() == benchmark_argv
final = json.loads((root / 'final_comparison.json').read_text())
assert final['status'] == 'PASS' and final['rebuilt'] is False and final['instrumented'] is False
assert final['runtime_argv'] == expected_runtime and final['benchmark_argv'] == benchmark_argv
assert final['prototype_comparison_control'] == 'candidate'
for key in ('configuration', 'checks', 'result', 'samples_seconds', 'plans'):
    assert final['mpi'][key] == runs['mpi'][key]
mpi_median = runs['mpi']['recomputed_statistics']['median_seconds']
control = runs['candidate']['recomputed_statistics']['median_seconds']
for label, run in runs.items():
    assert {key: value.replace('hpx-', 'mpi-') for key, value in run['plans'].items()} == runs['mpi']['plans']
    assert [arg for arg in run['argv'] if arg.startswith('--hpx:')] == ([] if label == 'mpi' else expected_runtime)
    if label != 'mpi':
        saved = json.loads((root / ('comparison_' + label + '.log')).read_text())
        for backend, selected in (('mpi', runs['mpi']), ('hpx', run)):
            for key in ('configuration', 'checks', 'result', 'samples_seconds', 'plans'):
                assert saved[backend][key] == selected[key]
        assert all(saved['normalized_plans_equal'].values())
        ratio = run['recomputed_statistics']['median_seconds'] / mpi_median
        assert saved['hpx_over_mpi_median_ratio'] == ratio
        record = final['runs'][label]
        assert record['samples_seconds'] == run['samples_seconds'] and record['checks'] == run['checks']
        assert record['median_seconds'] == run['recomputed_statistics']['median_seconds']
        assert record['hpx_over_mpi_median_ratio'] == ratio
        assert record['median_over_candidate_control'] == record['median_seconds'] / control
        assert all(record['normalized_plans_equal_to_mpi'].values())
        assert record['plans_equal_to_candidate'] is True
job_text = (root / 'job.log').read_text()
assert 'MATCHED_FINAL_PASS ' in job_text and 'FINAL_STATUS PASS exit=0 stage=complete ' in job_text
steps = [line.split('\t') for line in (root / 'results.tsv').read_text().splitlines()]
assert all(row[1] == 'PASS' for row in steps)
assert [row[0] for row in steps if row[0].startswith('benchmark_')] == ['benchmark_' + label for label in labels]
assert not re.search(r'warning:|error:|segmentation fault|segfault|out.of.memory|fatal:', job_text, re.I)
metadata = (root / 'metadata.txt').read_text()
for value in ('OMPI_MCA_pml=ucx', 'OMPI_MCA_btl=self,sm', 'UCX_TLS=rc,sm,self'):
    assert value in metadata
reused_pairs = {'baseline_inputs.sha256':'baseline_inputs.sha256', 'binaries.sha256':'binaries.sha256',
                'candidate_source.sha256':'candidate_source.sha256', 'hpx-flags.sh':'primary_hpx-flags.sh',
                'primary_candidate.binary.sha256':'primary_candidate.binary.sha256',
                'primary_candidate_archive.sha256':'primary_candidate_archive.sha256',
                'primary_mpi.binary.sha256':'primary_mpi.binary.sha256',
                'prototype_inputs.sha256':'prototype_inputs.sha256',
                'receive_FINAL_STATUS':'FINAL_STATUS', 'receive_job.sbatch':'job.sbatch'}
reused = {}
for current, prior in reused_pairs.items():
    assert (root / 'reused_artifacts' / current).read_bytes() == (previous / prior).read_bytes(),current
    reused[current] = {'same_as':'../1125605/' + prior,'sha256':sha(root / 'reused_artifacts' / current)}
primary = previous.parent / '1125395'
assert (root / 'reused_artifacts/primary_FINAL_STATUS').read_bytes() == (primary / 'FINAL_STATUS').read_bytes()
reused['primary_FINAL_STATUS'] = {'same_as':'../1125395/FINAL_STATUS','sha256':sha(root / 'reused_artifacts/primary_FINAL_STATUS')}
for name in ('direct_receive', 'pooled_receive'):
    for artifact in ('archive_members.json', 'artifacts.sha256'):
        current = root / 'reused_artifacts' / name / artifact
        prior = previous / 'prototypes' / name / artifact
        assert current.read_bytes() == prior.read_bytes()
        reused[name+'/'+artifact] = {'same_as':'../1125605/prototypes/'+name+'/'+artifact,'sha256':sha(current)}
    current = root / 'reused_artifacts' / name / 'source-hpx-comm.cpp'
    prior = prototypes / name / 'hpx-comm.cpp'
    assert current.read_bytes() == prior.read_bytes()
    reused[name+'/source-hpx-comm.cpp'] = {'same_as':'../receive_prototypes/'+name+'/hpx-comm.cpp','sha256':sha(current)}
assert len(reused) == 17
preservation = {}
for record, log in [('input.sha256','inputs_unchanged.log'), ('binaries.sha256','binaries_unchanged.log'),
                    ('reused_artifacts/baseline_inputs.sha256','baseline_unchanged.log'),
                    ('reused_artifacts/primary_candidate_archive.sha256','candidate_archive_unchanged.log'),
                    ('reused_artifacts/prototype_inputs.sha256','prototype_inputs_unchanged.log'),
                    ('reused_artifacts/pooled_receive/artifacts.sha256','pool_artifacts_unchanged.log'),
                    ('reused_artifacts/direct_receive/artifacts.sha256','direct_artifacts_unchanged.log'),
                    ('reused_artifacts/candidate_source.sha256','candidate_source_unchanged.log')]:
    preservation[log] = match_remote_ok(record, log)
known = {}
for record in ('primary_mpi.binary.sha256','primary_candidate.binary.sha256',
               'pooled_receive/artifacts.sha256','direct_receive/artifacts.sha256'):
    known.update(manifest(root/'reused_artifacts'/record))
for name,digest in manifest(root/'binaries.sha256').items():
    assert known[name] == digest
for name,digest in manifest(root/'input.sha256').items():
    local = Path('benchmarks/summarize.py') if name.endswith('/summarize.py') else root/Path(name).name
    assert sha(local) == digest
for run in runs.values():
    run['normalized_plan_sha256'] = {direction:hashlib.sha256(text.replace('hpx-','mpi-').encode()).hexdigest()
                                     for direction,text in run.pop('plans').items()}
report = {'status':'PASS','job_id':'1125688','sample_count':28,'numerical_check_count':12,
          'raw_statistics_recomputed':True,'all_normalized_plans_equal':True,
          'all_hpx_runtime_flags_equal':True,'runtime_argv':expected_runtime,
          'runs':runs,'archive_sha256':sha(archive),'clean_completion':status,'accounting':accounting,
          'slurm_stderr_empty':True,'all_execution_steps_pass':True,
          'reused_artifacts_verified':reused,'preservation_log_ok_counts':preservation,
          'binary_records_match_prior_manifests':True,
          'validation_boundary':'Final-job binary/source preservation uses complete recorded pre/post checks. No binaries were downloaded again in this text-only final bundle; prior binary/archive audit is retained in job1125605.'}
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'samples':28,'checks':12,'medians':{name:run['recomputed_statistics']['median_seconds'] for name,run in runs.items()},'archive_sha256':report['archive_sha256']},indent=2))
