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

"""Plot every measured sample and median, without inferred uncertainty intervals."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'fftw-progress-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parent
summary = json.loads((root / 'SUMMARY.json').read_text())
assert summary['status'] == 'PASS'
matplotlib.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                            'svg.fonttype': 'none', 'axes.axisbelow': True})
labels = ['1  MPI, opening control', '2  Release pool, original HPX',
          '3  Lean rendezvous, cap 1000 ms', '4  Same binary, cap 1 ms',
          '5  Cap 1000 ms, repeat', '6  MPI, closing control']
colors = ['#566578', '#77869a', '#176c91', '#c55b26', '#176c91', '#566578']
offsets = [-0.18, -0.12, -0.06, 0.0, 0.06, 0.12, 0.18]
fig, ax = plt.subplots(figsize=(11.8, 6.2))
fig.subplots_adjust(left=0.31, right=0.86, top=0.79, bottom=0.27)
for row, (key, label, color) in enumerate(zip(summary['run_order'], labels, colors)):
    case = summary['cases'][key]
    ax.scatter(case['samples_seconds'], [row + value for value in offsets],
               s=38, color=color, edgecolor='white', linewidth=0.5, zorder=3)
    median = case['median_seconds']
    ax.vlines(median, row - 0.27, row + 0.27, color=color, linewidth=3.1, zorder=2)
    ax.text(1.04, row, '{:.6f}'.format(median), ha='left', va='center',
            transform=ax.get_yaxis_transform(),
            color='#273440', fontsize=10, fontfamily='DejaVu Sans Mono')
ax.set_yticks(range(6))
ax.set_yticklabels(labels)
ax.invert_yaxis()
ax.set_ylim(5.55, -0.55)
ax.set_xlim(3.15, 4.55)
ax.set_xticks([3.2, 3.4, 3.6, 3.8, 4.0, 4.2, 4.4])
ax.set_xlabel('Forward time: maximum across four ranks (seconds)', labelpad=12)
ax.grid(axis='x', color='#d9e0e5', linewidth=0.7)
ax.tick_params(axis='both', length=0, pad=10)
for spine in ax.spines.values():
    spine.set_visible(False)
fig.text(0.055, 0.94, 'Idle cap 1 ms did not improve the median',
         fontsize=18, fontweight='bold', color='#142b3c')
fig.text(0.055, 0.885, 'QueenBee 1125945  ·  1024³  ·  4 nodes × 64 workers  ·  fixed sendimm=0',
         fontsize=11.5, color='#526575')
fig.text(0.882, 0.815, 'Median (s)', ha='left', fontsize=10, color='#526575')
fig.text(0.055, 0.055, 'All seven samples are shown per case; vertical bars mark medians. No confidence intervals.\n'
         'Execution order runs top to bottom. Repeated controls expose variation; they do not remove fixed-order effects.',
         fontsize=10.3, color='#526575', linespacing=1.5)
for suffix in ('png', 'svg'):
    fig.savefig(str(root / ('progress_samples.' + suffix)), dpi=200,
                facecolor='white', metadata={'Creator': 'FFTW HPX evidence; GPL-2.0-or-later'})
plt.close(fig)
