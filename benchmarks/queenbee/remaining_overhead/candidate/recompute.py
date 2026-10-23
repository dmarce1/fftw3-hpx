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


"""Recompute compact candidate evidence from raw logs; no builds or remote access."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('raw', type=Path)
parser.add_argument('--summarizer', required=True, type=Path)
args = parser.parse_args()
root = args.raw
primary = ('mpi', 'pooled_current', 'pool_release', 'lean_pool', 'parallel_copy', 'hybrid', 'rendezvous')
diagnostic_labels = ('hybrid_diagnostic', 'rendezvous_diagnostic')
labels = primary + diagnostic_labels
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
status = dict(line.split('\t', 1) for line in (root / 'FINAL_STATUS').read_text().splitlines())
assert status['status'] == 'PASS' and status['job_id'] == '1125899' and status['stage'] == 'complete' and status['exit_status'] == '0'
stages = [line.split('\t') for line in (root / 'results.tsv').read_text().splitlines()]
assert stages and all(row[1] == 'PASS' for row in stages)
comparisons = {}
cases = {}
for label in labels[1:]:
    raw = subprocess.check_output([sys.executable, '-I', str(args.summarizer), str(root / 'benchmark_mpi.log'), str(root / ('benchmark_' + label + '.log'))], universal_newlines=True)
    comparison = json.loads(raw)
    assert all(comparison['normalized_plans_equal'].values()), label
    for backend in ('mpi', 'hpx'):
        assert all(comparison[backend]['configuration'][key] == value for key, value in expected.items()), (label, backend)
    if comparisons:
        first = comparisons['pooled_current']
        assert comparison['mpi'] == first['mpi']
        assert comparison['hpx']['plans'] == first['hpx']['plans']
    comparisons[label] = comparison
    cases[label] = comparison['hpx']
cases['mpi'] = comparisons['pooled_current']['mpi']
compact = {}
for label in labels:
    case = cases[label]
    values = case['samples_seconds']
    assert len(values) == 7
    median = statistics.median(values)
    compact[label] = dict(role='primary' if label in primary else 'diagnostic', samples_seconds=values, median_seconds=median, minimum_seconds=min(values), maximum_seconds=max(values), mean_seconds=statistics.mean(values), checks=case['checks'], plans_sha256={key: hashlib.sha256(value.encode('utf-8')).hexdigest() for key, value in case['plans'].items()}, raw_log_sha256=hashlib.sha256((root / ('benchmark_' + label + '.log')).read_bytes()).hexdigest())
mpi_median = compact['mpi']['median_seconds']
for label, item in compact.items():
    item['median_over_mpi'] = item['median_seconds'] / mpi_median
metrics = ('posted', 'disabled_registration', 'remote_load', 'direct_hit', 'fallback_unposted', 'pool_hit', 'pool_miss', 'unpooled_allocation', 'self_copy', 'final_copy', 'direct_copy_elided')
pattern = re.compile(r'^RECEIVE_DIAGNOSTIC rank=(\d+) sample=(\d+) metric=([a-z_]+) calls=(\d+) bytes=(\d+)$')
diagnostics = {}
for label in diagnostic_labels:
    rows = {}
    for line in (root / ('benchmark_' + label + '.log')).read_text().splitlines():
        if not line.startswith('RECEIVE_DIAGNOSTIC '):
            continue
        match = pattern.fullmatch(line)
        assert match is not None, line
        rank, sample, metric, calls, amount = match.groups()
        key = (int(rank), int(sample), metric)
        assert key not in rows and metric in metrics, key
        assert 0 <= int(rank) < 4 and 0 <= int(sample) < 7
        rows[key] = dict(calls=int(calls), bytes=int(amount))
    assert len(rows) == 308
    totals = {metric: dict(calls=0, bytes=0) for metric in metrics}
    ranks = []
    for rank in range(4):
        rank_totals = {metric: dict(calls=0, bytes=0) for metric in metrics}
        rank_samples = []
        for sample in range(7):
            data = {metric: rows[(rank, sample, metric)] for metric in metrics}
            for field in ('calls', 'bytes'):
                get = lambda metric: data[metric][field]
                assert get('remote_load') == get('direct_hit') + get('fallback_unposted')
                assert get('pool_hit') + get('pool_miss') + get('unpooled_allocation') == get('fallback_unposted') + get('self_copy')
                assert get('direct_copy_elided') == get('direct_hit')
                assert get('final_copy') == get('fallback_unposted') + get('self_copy')
                assert get('unpooled_allocation') == 0
            assert data['remote_load'] == dict(calls=6, bytes=6 * 1073741824)
            if label == 'rendezvous_diagnostic':
                assert data['direct_hit'] == data['remote_load']
                assert data['final_copy'] == dict(calls=0, bytes=0)
                assert data['fallback_unposted'] == dict(calls=0, bytes=0)
            for metric in metrics:
                for field in ('calls', 'bytes'):
                    totals[metric][field] += data[metric][field]
                    rank_totals[metric][field] += data[metric][field]
            rank_samples.append(dict(sample=sample, direct_calls=data['direct_hit']['calls'], fallback_calls=data['fallback_unposted']['calls'], final_copy_calls=data['final_copy']['calls'], direct_bytes=data['direct_hit']['bytes']))
        ranks.append(dict(rank=rank, totals=rank_totals, samples=rank_samples))
    diagnostics[label] = dict(rows=len(rows), rank_samples=28, totals=totals, per_rank=ranks, direct_hit_fraction={field: totals['direct_hit'][field] / totals['remote_load'][field] for field in ('calls', 'bytes')})
communication = {}
for label in ('pool_release', 'parallel_copy', 'hybrid', 'hybrid_diagnostic', 'lean_pool', 'rendezvous', 'rendezvous_diagnostic'):
    count = (root / ('communication_' + label + '.log')).read_text().splitlines().count('communication check PASS')
    assert count == 4, label
    communication[label] = count
members = json.loads((root / 'archive_members.log').read_text())
assert set(members) == set(communication)
for label, item in members.items():
    assert item['changed'] == ['hpx-comm.o'] and item['unchanged'] == 31
    before, after = item['before'], item['after']
    assert len(before) == len(after) == 32 and set(before) == set(after)
    assert list(before) == list(after)
    assert [name for name in before if before[name] != after[name]] == ['hpx-comm.o']
ratios = {}
for label in primary[1:]:
    ratios[label + '_over_mpi'] = compact[label]['median_seconds'] / mpi_median
ratios['rendezvous_over_release_pool'] = compact['rendezvous']['median_seconds'] / compact['pool_release']['median_seconds']
ratios['rendezvous_over_parallel_copy'] = compact['rendezvous']['median_seconds'] / compact['parallel_copy']['median_seconds']
ratios['lean_pool_over_release_pool'] = compact['lean_pool']['median_seconds'] / compact['pool_release']['median_seconds']
summary = dict(license='GPL-2.0-or-later', raw_evidence='raw/1125899', status='PASS', job_id='1125899', job_status=status, configuration=expected, primary_order=list(primary), diagnostic_order=list(diagnostic_labels), cases=compact, primary_median_ratios=ratios, diagnostics=diagnostics, diagnostic_rows=sum(item['rows'] for item in diagnostics.values()), numerical_checks=27, all_plans_normalized_equal=True, all_hpx_plans_byte_equal=True, communication_passes=communication, archive_variants=7, unchanged_members_per_archive=31, stage_count=len(stages), source_provenance=json.loads((root / 'PROVENANCE.json').read_text()), limitations=['Single fixed-order allocation: temporal and node effects remain.', 'Diagnostic timings include atomic counters and an outside-timer reporting barrier and are not primary timings.', 'Lean HPX changes five instrumentation options together.', 'Cluster binary/archive hash manifests are retained records; omitted binaries cannot be independently rehashed from this text-only package.'])
print(json.dumps(summary, indent=2))
