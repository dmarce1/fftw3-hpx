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

"""Plot all primary samples, with the instrumented diagnostic in a separate panel."""
import json
import os
from pathlib import Path
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'fftw-readiness-mpl'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

base = Path(__file__).resolve().parent
summary = json.loads((base / 'SUMMARY.json').read_text())
assert summary['status'] == 'PASS'
matplotlib.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'svg.fonttype':'none','axes.axisbelow':True})
fig, axes = plt.subplots(2,1,figsize=(12.0,7.4),sharex=True,gridspec_kw={'height_ratios':[5,1.4]})
fig.subplots_adjust(left=0.31,right=0.86,top=0.82,bottom=0.19,hspace=0.35)
labels = ['1  MPI, opening control','2  Lean rendezvous, cap 1000 ms','3  Same binary, cap 10 ms','4  Cap 1000 ms, repeat','5  MPI, closing control','6  Diagnostic HPX, cap 10 ms']
colors = ['#566578','#176c91','#c55b26','#176c91','#566578','#8c559c']
offsets = [-0.18,-0.12,-0.06,0.0,0.06,0.12,0.18]
for index, key in enumerate(summary['run_order']):
    ax = axes[0] if index < 5 else axes[1]
    row = index if index < 5 else 0
    case = summary['cases'][key]
    ax.scatter(case['samples_seconds'],[row+offset for offset in offsets],s=38,color=colors[index],edgecolor='white',linewidth=0.5,zorder=3)
    ax.vlines(case['median_seconds'],row-0.27,row+0.27,color=colors[index],linewidth=3.1)
    ax.text(1.03,row,'{:.6f}'.format(case['median_seconds']),ha='left',va='center',transform=ax.get_yaxis_transform(),fontfamily='DejaVu Sans Mono',fontsize=10)
for ax, current_labels in zip(axes,(labels[:5],labels[5:])):
    ax.set_yticks(range(len(current_labels)))
    ax.set_yticklabels(current_labels)
    ax.set_ylim(len(current_labels)-0.45,-0.55)
    ax.grid(axis='x',color='#d9e0e5',linewidth=0.7)
    ax.tick_params(axis='both',length=0,pad=9)
    for spine in ax.spines.values():
        spine.set_visible(False)
axes[0].set_title('Primary timing controls',loc='left',fontsize=11,color='#526575',pad=12)
axes[1].set_title('Instrumented diagnostic: separate timing role',loc='left',fontsize=11,color='#526575',pad=12)
axes[1].set_xlabel('Forward time: maximum across four ranks (seconds)',labelpad=12)
fig.text(0.055,0.95,'Readiness backoff cap: 1000 → 10 → 1000 ms',fontsize=18,fontweight='bold',color='#142b3c')
fig.text(0.055,0.90,'QueenBee 1125974 · 1024³ · 4 nodes × 64 workers · fixed sendimm=0',fontsize=11.5,color='#526575')
fig.text(0.883,0.83,'Median (s)',fontsize=10,color='#526575')
fig.text(0.055,0.045,'All seven samples per case; vertical bars mark medians. No inferred confidence intervals.\nRepeated controls expose variation; a fixed order does not eliminate it. Diagnostic instrumentation can alter scheduling.',fontsize=10,color='#526575',linespacing=1.5)
for suffix in ('png','svg'):
    fig.savefig(str(base / ('readiness_samples.'+suffix)),dpi=200,facecolor='white',metadata={'Creator':'FFTW HPX evidence; GPL-2.0-or-later'})
plt.close(fig)
