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


import json
import math
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
labels = ('pooled_current', 'pool_release', 'parallel_copy', 'hybrid', 'lean_pool', 'rendezvous', 'hybrid_diagnostic', 'rendezvous_diagnostic')
results = {}
for label in labels:
    comparison = json.loads((root / ('comparison_' + label + '.log')).read_text())
    assert all(comparison['normalized_plans_equal'].values()), label
    config = comparison['hpx']['configuration']
    expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
    assert all(config[key] == value for key, value in expected.items()), (label, config)
    if results:
        first = results['pooled_current']
        assert comparison['mpi'] == first['mpi']
        assert comparison['hpx']['plans'] == first['hpx']['plans']
    results[label] = comparison
metrics = ('posted', 'disabled_registration', 'remote_load', 'direct_hit', 'fallback_unposted', 'pool_hit', 'pool_miss', 'unpooled_allocation', 'self_copy', 'final_copy', 'direct_copy_elided')
diagnostics = {}
for diagnostic_label in ('hybrid_diagnostic', 'rendezvous_diagnostic'):
    text = (root / ('benchmark_' + diagnostic_label + '.log')).read_text()
    pattern = r'RECEIVE_DIAGNOSTIC rank=(\d+) sample=(\d+) metric=([a-z_]+) calls=(\d+) bytes=(\d+)'
    rows = {}
    for rank, sample, metric, calls, amount in re.findall(pattern, text):
        key = (int(rank), int(sample), metric)
        assert key not in rows, ('duplicate diagnostic row', key)
        assert metric in metrics
        rows[key] = dict(calls=int(calls), bytes=int(amount))
    assert len(rows) == 4 * 7 * len(metrics), len(rows)
    records = []
    for rank in range(4):
        for sample in range(7):
            data = {metric: rows[(rank, sample, metric)] for metric in metrics}
            for field in ('calls', 'bytes'):
                def value(metric):
                    return data[metric][field]
                assert value('remote_load') == value('direct_hit') + value('fallback_unposted'), (rank, sample, field, data)
                assert value('pool_hit') + value('pool_miss') + value('unpooled_allocation') == value('fallback_unposted') + value('self_copy'), (rank, sample, field, data)
                assert value('direct_copy_elided') == value('direct_hit'), (rank, sample, field, data)
                assert value('final_copy') == value('fallback_unposted') + value('self_copy'), (rank, sample, field, data)
                assert value('unpooled_allocation') == 0, (rank, sample, field, data)
            assert data['remote_load']['calls'] > 0 and data['remote_load']['bytes'] > 0
            fractions = {field: data['direct_hit'][field] / data['remote_load'][field] for field in ('calls', 'bytes')}
            records.append(dict(rank=rank, sample=sample, metrics=data, direct_hit_fraction=fractions))
    diagnostics[diagnostic_label] = dict(expected_rows=308, observed_rows=len(rows), rank_samples=records)
summary = dict(status='PASS', primary_labels=['mpi', 'pooled_current', 'pool_release', 'lean_pool', 'parallel_copy', 'hybrid', 'rendezvous'], diagnostic_labels=['hybrid_diagnostic', 'rendezvous_diagnostic'], comparisons=results, diagnostics=diagnostics, interpretation='Diagnostic timings include atomic counter overhead and a report barrier outside the timer; use only primary cases for performance conclusions. Lean HPX changes five instrumentation options together.')
(root / 'candidate_comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(dict(status='PASS', primary_cases=7, diagnostic_cases=2, diagnostic_rows=sum(item['observed_rows'] for item in diagnostics.values()), all_plans_equal=True, all_numerical_checks_pass=True), indent=2))
