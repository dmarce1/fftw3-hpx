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
import sys

root = Path(sys.argv[1])
selected = sys.argv[2]
assert selected in ('parallel_copy', 'hybrid', 'rendezvous')
expected = dict(extent='1024', ranks='4', threads='64', precision='double', inplace='1', layout='normal', planner='FFTW_ESTIMATE', warmups='2', samples='7')
results = {}
for label in ('pool_release', 'selected_original', 'selected_lean', 'selected_lean_sendimm'):
    comparison = json.loads((root / ('comparison_' + label + '.log')).read_text())
    assert all(comparison['normalized_plans_equal'].values()), label
    for backend in ('mpi', 'hpx'):
        config = comparison[backend]['configuration']
        assert all(config[key] == value for key, value in expected.items()), (label, backend, config)
        assert len(comparison[backend]['samples_seconds']) == 7
        assert comparison[backend]['result']['status'] == 'PASS'
    if results:
        assert comparison['mpi'] == results['pool_release']['mpi']
        assert comparison['hpx']['plans'] == results['pool_release']['hpx']['plans']
    results[label] = comparison
medians = {label: float(comparison['hpx']['result']['median_seconds']) for label, comparison in results.items()}
medians['mpi'] = float(results['pool_release']['mpi']['result']['median_seconds'])
assert all(math.isfinite(value) and value > 0 for value in medians.values())
ratios = {label + '_over_mpi': value / medians['mpi'] for label, value in medians.items() if label != 'mpi'}
ratios['selected_original_over_pool_release'] = medians['selected_original'] / medians['pool_release']
ratios['selected_lean_over_selected_original'] = medians['selected_lean'] / medians['selected_original']
ratios['selected_lean_sendimm_over_selected_lean'] = medians['selected_lean_sendimm'] / medians['selected_lean']
ratios['selected_lean_over_pool_release'] = medians['selected_lean'] / medians['pool_release']
summary = dict(sendimm_case_extra='--hpx:ini=hpx.parcel.mpi.sendimm=1', status='PASS', selected_candidate=selected, run_order=['mpi', 'pool_release', 'selected_original', 'selected_lean', 'selected_lean_sendimm'], median_seconds=medians, median_ratios=ratios, comparisons=results, all_plans_equal=True, all_numerical_checks_pass=True, interpretation='One fixed-order four-node cohort; node and temporal effects remain. Lean HPX changes five instrumentation options together, not a single isolated option.')
(root / 'confirmation_comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
