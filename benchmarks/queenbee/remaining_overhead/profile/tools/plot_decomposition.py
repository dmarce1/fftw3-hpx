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
"""Render exact additive means from the independently reduced profile summary."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', tempfile.mkdtemp(prefix='fftw_profile_mpl_'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

root = Path(__file__).resolve().parent.parent
report = json.loads((root / 'analysis_summary.json').read_text())
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                     'svg.fonttype': 'none', 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.spines.left': False})
fig = plt.figure(figsize=(10.0, 4.9), facecolor='white')
ax = fig.add_axes([0.12, 0.31, 0.81, 0.42])
parts = [
    ('fft_worker_phases', 'FFTW worker phases', '#4477AA', 'white'),
    ('pairwise_staging_and_allocation', 'Pairwise staging + allocation/free', '#CCBB44', '#172B3A'),
    ('exchange_without_receive_copy', 'Exchange excluding final receive copy', '#EE7733', '#172B3A'),
    ('receive_copy', 'Final receive copy', '#228833', 'white'),
    ('residual', 'Unattributed residual', '#BBBBBB', '#172B3A'),
]
for backend, y in [('mpi', 1), ('hpx', 0)]:
    run = report['runs'][backend]
    left = 0.0
    for key, label, color, text_color in parts:
        value = run['mean_components_seconds'][key]
        ax.barh(y, value, left=left, height=0.48, color=color, edgecolor='white', linewidth=1)
        if value > 0.2:
            ax.text(left + value / 2, y, '{:.3f}'.format(value), ha='center', va='center', color=text_color, fontsize=10)
        left += value
    assert abs(left - run['mean_total_seconds']) < 1e-12
    ax.text(left + 0.06, y, '{:.3f} s'.format(left), ha='left', va='center', weight='bold', color='#172B3A')
ax.set_yticks([1, 0], ['MPI', 'HPX pooled'])
ax.tick_params(axis='y', length=0, pad=10)
ax.set_xlim(0, 4.65)
ax.set_ylim(-0.65, 1.65)
ax.set_xticks([0, 1, 2, 3, 4])
ax.set_xlabel('Mean forward time on each sample’s slowest rank (seconds)', labelpad=9)
ax.set_axisbelow(True)
ax.grid(axis='x', color='#E5E7EB', linewidth=0.7)
fig.text(0.12, 0.975, 'The profiled gap is concentrated in exchange', va='top', fontsize=16, weight='bold', color='#172B3A')
fig.text(0.12, 0.915, 'QueenBee · 1024³ · 4 ranks × 64 workers · seven samples · job 1125891', va='top', fontsize=10, color='#52616B')
handles = [Patch(facecolor=color, label=label) for _, label, color, _ in parts]
fig.legend(handles=handles, loc='upper left', bbox_to_anchor=(0.112, 0.87), ncol=2,
           frameon=False, fontsize=9, handlelength=1.3, columnspacing=1.5)
fig.text(0.12, 0.105, 'Components are selected from the actual critical rank, then averaged; each stack equals its mean total.\nFinal receive copy is subtracted from its enclosing exchange scope. Residual is not assigned to a pure operation.',
         fontsize=9, color='#52616B', va='top', linespacing=1.5)
fig.savefig(root / 'critical_rank_decomposition.png', dpi=220)
fig.savefig(root / 'critical_rank_decomposition.svg', metadata={'Date': None})
plt.close(fig)
print('PLOT_PASS exact additive critical-rank means')
