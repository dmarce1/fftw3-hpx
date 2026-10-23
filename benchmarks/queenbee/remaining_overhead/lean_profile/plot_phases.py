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

"""Plot additive critical-rank means; no inferred confidence intervals."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'fftw-lean-profile-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

root = Path(__file__).resolve().parent
summary = json.loads((root / 'SUMMARY.json').read_text())
assert summary['status'] == 'PASS'
matplotlib.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                            'svg.fonttype': 'none', 'axes.axisbelow': True})
means = {key: summary['diagnostics'][key]['critical_rank_means'] for key in ('mpi', 'hpx')}
fig = plt.figure(figsize=(11.8, 7.1))
upper = fig.add_axes([0.18, 0.53, 0.76, 0.23])
lower = fig.add_axes([0.18, 0.22, 0.76, 0.13])
components = [('run_jobs_wall', 'Local threaded FFT', '#2c6e94'),
              ('pairwise_copy_wall', 'Pairwise copies', '#458a86'),
              ('pairwise_memory', 'Pairwise allocate/free', '#87a7a3'),
              ('exchange_wall', 'Exchange', '#cf7b35'),
              ('residual_seconds', 'Remaining forward work', '#b5bdc6')]
for row, backend in enumerate(('mpi', 'hpx')):
    mean = means[backend]
    left = 0
    for metric, label, color in components:
        value = mean['pairwise_allocate_wall'] + mean['pairwise_free_wall'] if metric == 'pairwise_memory' else mean[metric]
        upper.barh(row, value, left=left, height=0.48, color=color, linewidth=0)
        if value >= 0.2:
            upper.text(left + value / 2, row, '{:.3f}'.format(value), ha='center', va='center',
                       fontsize=10.5, color='white' if metric != 'residual_seconds' else '#253440')
        left += value
    assert abs(left - mean['seconds']) < 1e-12
    upper.text(left + 0.045, row, '{:.6f} s'.format(left), va='center', fontsize=10)
upper.set_yticks([0, 1])
upper.set_yticklabels(['MPI diagnostic', 'HPX diagnostic'])
upper.set_ylim(1.7, -0.6)
upper.set_xlim(0, 4.45)
upper.set_xlabel('Mean of the actual slowest rank in each sample (seconds)', labelpad=8)
upper.legend(handles=[Patch(facecolor=color, label=label) for metric,label,color in components],
             loc='upper center', bbox_to_anchor=(0.46, 1.38), ncol=3, frameon=False, fontsize=10,
             handlelength=1.3, columnspacing=1.5)
hpx = means['hpx']
phases = [('Readiness', hpx['readiness_phase_wall'], '#a95243'),
          ('Incoming completion', hpx['receive_wait_wall'], '#e0a044'),
          ('Outgoing completion', hpx['send_completion_wait_wall'], '#785e93')]
other = sum(hpx[key] for key in ('post_announce_initiation_wall', 'send_initiation_wall',
            'receive_finish_wall', 'announce_completion_wait_wall', 'exchange_rest_wall'))
phases.append(('Other five phases', other, '#8f9aa6'))
left = 0
for label, value, color in phases:
    lower.barh(0, value, left=left, height=0.48, color=color, linewidth=0)
    if value >= 0.05:
        lower.text(left + value/2, 0, '{:.4f}'.format(value), ha='center', va='center', color='white', fontsize=10)
    left += value
assert abs(left - hpx['exchange_wall']) < 1e-12
lower.text(left + 0.012, 0, '{:.6f} s'.format(left), va='center', fontsize=10)
lower.set_yticks([0]); lower.set_yticklabels(['HPX exchange'])
lower.set_ylim(-0.7, 0.7); lower.set_xlim(0, 1.04)
lower.set_xlabel('Disjoint exchange phases on those same critical ranks (seconds)', labelpad=8)
lower.legend(handles=[Patch(facecolor=color, label=label+' ({:.4f} s)'.format(value)) for label,value,color in phases],
             loc='lower center', bbox_to_anchor=(0.46, 1.02), ncol=2, frameon=False, fontsize=10,
             handlelength=1.3, columnspacing=1.8)
for ax in (upper, lower):
    ax.grid(axis='x', color='#e1e6e9', linewidth=0.6)
    ax.tick_params(length=0, pad=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
fig.text(0.045, 0.945, 'Measured exchange phases in lean rendezvous', fontsize=19, fontweight='bold', color='#142b3c')
fig.text(0.045, 0.895, 'QueenBee 1125966 · 1024³ · 4 × 64 workers · diagnostic means from seven samples', fontsize=11.3, color='#526575')
fig.text(0.045, 0.073, 'Diagnostic HPX median was 10.9% above its clean control; timing perturbation and run-order effects remain.\n'
         'Shared phase boundaries add exactly. Readiness includes peer delay; nested counters are excluded. No confidence intervals.',
         fontsize=10.2, color='#526575', linespacing=1.5)
for suffix in ('png', 'svg'):
    fig.savefig(str(root / ('critical_rank_phases.' + suffix)), dpi=200, facecolor='white',
                metadata={'Creator': 'FFTW HPX evidence; GPL-2.0-or-later'})
plt.close(fig)
