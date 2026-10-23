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


"""Validate confirmation raw logs and emit compact reproducible evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import statistics
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('raw', type=Path)
parser.add_argument('--summarizer', type=Path, required=True)
args = parser.parse_args()
root = args.raw
labels = ('mpi', 'pool_release', 'selected_original', 'selected_lean', 'selected_lean_sendimm')
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
status = dict(line.split('\t', 1) for line in (root / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['exit_status'] == '0' and status['stage'] == 'complete'
assert status['job_id'] == '1125925' and status['candidate'] == 'rendezvous'
assert (root / 'FINAL_STATUS').read_bytes() == (root / 'CONFIRMATION_FINAL_STATUS').read_bytes()
stages = [line.split('\t') for line in (root / 'results.tsv').read_text().splitlines()]
assert len({row[0] for row in stages}) == len(stages) and all(row[1] == 'PASS' for row in stages)
cases = {}
comparison_hashes = {}
first = None
for label in labels[1:]:
    output = subprocess.check_output([sys.executable, '-I', str(args.summarizer), str(root / 'benchmark_mpi.log'), str(root / ('benchmark_' + label + '.log'))], universal_newlines=True)
    data = json.loads(output)
    assert all(data['normalized_plans_equal'].values())
    if first is None:
        first = data
        cases['mpi'] = data['mpi']
    else:
        assert first['mpi'] == data['mpi'] and first['hpx']['plans'] == data['hpx']['plans']
    cases[label] = data['hpx']
    # The paired comparison logs are duplicate plan JSON, intentionally omitted
    # from the compact publication. Verify them when using the original tree.
    recorded = root / ('comparison_' + label + '.log')
    if recorded.exists():
        assert data == json.loads(recorded.read_text())
    comparison_hashes[label] = hashlib.sha256(output.encode('utf-8')).hexdigest()
compact = {}
for label in labels:
    case = cases[label]
    assert all(case['configuration'][key] == value for key, value in expected.items())
    assert len(case['samples_seconds']) == 7 and len(case['checks']) == 3
    assert all(float(item['tolerance']) == 1e-10 for item in case['checks'])
    values = case['samples_seconds']
    compact[label] = dict(samples_seconds=values, median_seconds=statistics.median(values), minimum_seconds=min(values), maximum_seconds=max(values), mean_seconds=statistics.mean(values), checks=case['checks'], plans_sha256={key: hashlib.sha256(value.encode('utf-8')).hexdigest() for key, value in case['plans'].items()}, raw_log_sha256=hashlib.sha256((root / ('benchmark_' + label + '.log')).read_bytes()).hexdigest())
mpi_median = compact['mpi']['median_seconds']
ratios = {label + '_over_mpi': compact[label]['median_seconds'] / mpi_median for label in labels[1:]}
for left, right in (('selected_original', 'pool_release'), ('selected_lean', 'selected_original'), ('selected_lean', 'pool_release'), ('selected_lean_sendimm', 'selected_lean')):
    ratios[left + '_over_' + right] = compact[left]['median_seconds'] / compact[right]['median_seconds']
commands = {}
for label in labels:
    lines = (root / ('benchmark_' + label + '.command')).read_text().strip().splitlines()
    tokens = shlex.split(lines[-1])
    assert tokens[:2][1] == '-n' and tokens[2] == '4'
    assert '--map-by' in tokens and 'ppr:1:node' in tokens and '--interleave=all' in tokens
    assert all(option in tokens for option in ('--size=1024', '--threads=64', '--warmups=2', '--samples=7'))
    if label != 'mpi':
        for option in ('--hpx:threads=64', '--hpx:localities=4', '--hpx:ini=hpx.parcel.mpi.enable!=1', '--hpx:ini=hpx.parcel.tcp.enable!=0', '--hpx:ini=hpx.parcel.bootstrap!=mpi', '--hpx:ini=hpx.parcel.mpi.background_threads=1', '--hpx:ini=hpx.max_background_threads=1', '--hpx:ini=hpx.parcel.mpi.multithreaded=1', '--hpx:ini=hpx.max_idle_backoff_time=1000'):
            assert option in tokens, (label, option)
    commands[label] = tokens
extra = '--hpx:ini=hpx.parcel.mpi.sendimm=1'
assert commands['selected_lean_sendimm'].count(extra) == 1
assert commands['selected_lean'] == [token for token in commands['selected_lean_sendimm'] if token != extra]
communication = {}
for label in ('selected_lean', 'selected_lean_sendimm'):
    count = (root / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS')
    assert count == 4
    communication[label] = count
members = json.loads((root / 'archive_members.log').read_text())
assert members['status'] == 'PASS' and members['changed'] == ['hpx-comm.o'] and members['unchanged'] == 31
before, after = members['before'], members['after']
assert len(before) == len(after) == 32 and list(before) == list(after)
assert [name for name in before if before[name] != after[name]] == ['hpx-comm.o']
receipts = {}
for manifest, log, expected_count in (('fixed_inputs.sha256', 'fixed_inputs_unchanged.log', 49), ('reused_binaries.sha256', 'reused_binaries_unchanged.log', 3), ('artifacts.sha256', 'artifacts_recheck.log', 5)):
    names = [line.split('  ', 1)[1] for line in (root / manifest).read_text().splitlines()]
    checks = (root / log).read_text().splitlines()
    assert len(names) == expected_count and checks == [name + ': OK' for name in names]
    receipts[manifest] = expected_count
for log in ('prior_artifacts.log', 'prior_artifacts_unchanged.log'):
    lines = (root / log).read_text().splitlines()
    assert len(lines) == 85 and all(line.endswith(': OK') for line in lines)
assert (root / 'prior_artifacts.log').read_bytes() == (root / 'prior_artifacts_unchanged.log').read_bytes()
selection = dict(line.split('=', 1) for line in (root / 'selection.txt').read_text().splitlines())
assert selection['candidate'] == 'rendezvous' and selection['prior_job'] == '1125899'
assert selection['source_sha256'] == 'cf160a561ec182410f343aa47e04458b8adc4b847a56545e8bd284ef8e43905c'
assert hashlib.sha256((root / 'objects/selected_lean/source-hpx-comm.cpp').read_bytes()).hexdigest() == selection['source_sha256']
assert hashlib.sha256((root / 'matched_3d.cpp').read_bytes()).hexdigest() == '9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41'
for log in ('lean_dependencies.log', 'lean_comm_dependencies.log'):
    data = json.loads((root / log).read_text())
    assert data['status'] == 'PASS' and not data['apex_present']
    assert all('/lean_hpx/install/' in path for path in data['hpx_libraries'])
    assert all('/openmpi-5.0.11-gcc13.2/install/' in path for path in data['mpi_libraries'])
summary = dict(license='GPL-2.0-or-later', status='PASS', job_id='1125925', job_status=status, selected_candidate='rendezvous', configuration=expected, run_order=list(labels), cases=compact, median_ratios=ratios, numerical_checks=15, timed_samples=35, all_plans_normalized_equal=True, all_hpx_plans_byte_equal=True, paired_comparison_json_sha256=comparison_hashes, exact_same_lean_binary_with_one_extra_sendimm_option=True, communication_passes=communication, unchanged_members_in_new_lean_archive=31, preservation_receipt_counts=receipts, prior_preservation_receipts_each=85, stage_count=len(stages), selection=selection, limitations=['Fixed-order single allocation: temporal and node effects remain.', 'Original-runtime rendezvous did not reproduce the earlier 9.7% overhead.', 'Lean HPX changes multiple compiled facilities together.', 'sendimm=1 used the exact lean binary and was substantially slower.', 'Binary/archive digests are cluster receipts; this text-only package cannot rehash omitted binaries.', 'Slurm accounting was intentionally pending; job completion here is its own FINAL_STATUS receipt.'])
print(json.dumps(summary, indent=2))
