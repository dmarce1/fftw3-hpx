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
"""Plot receive results, or final results with INPUT OUTPUT_STEM final."""
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys
import tempfile

os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="fftw_hpx_plot_"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

if len(sys.argv) not in (3, 4) or (len(sys.argv) == 4 and sys.argv[3] != "final"):
    raise SystemExit("usage: plot_results.py INPUT_DIR OUTPUT_STEM [final]")
final_mode = len(sys.argv) == 4
root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
summarizer = Path(__file__).resolve().parents[2] / "summarize.py"
cases = [
    ("candidate", "Copy reduction"),
    ("pooled_receive", "Receive pool"),
    ("direct_receive", "Direct receive"),
] if final_mode else [
    ("hpx_baseline", "Original HPX"),
    ("candidate_selected", "Copy reduction / 1000 ms idle cap"),
    ("candidate_selected_backoff1", "Copy reduction / 1 ms idle cap"),
    ("pooled_selected", "Receive pool / 1 ms idle cap"),
    ("direct_selected", "Direct receive / 1 ms idle cap"),
]
records = []
for name, label in cases:
    if final_mode:
        command = shlex.split((root / ("benchmark_" + name + ".command")).read_text())
        required = {"--hpx:ini=hpx.parcel.mpi.background_threads=1",
                    "--hpx:ini=hpx.max_background_threads=1",
                    "--hpx:ini=hpx.parcel.mpi.multithreaded=1",
                    "--hpx:ini=hpx.max_idle_backoff_time=1000"}
        assert required.issubset(command), "final plot requires the matched 1000 ms runtime"
    result = json.loads(subprocess.check_output([
        sys.executable, "-I", str(summarizer), str(root / "benchmark_mpi.log"),
        str(root / ("benchmark_" + name + ".log"))], text=True))
    assert all(result["normalized_plans_equal"].values())
    if not records:
        records.append({"label": "FFTW MPI", "samples": result["mpi"]["samples_seconds"]})
    records.append({"label": label, "samples": result["hpx"]["samples_seconds"]})
mpi = statistics.median(records[0]["samples"])
for item in records:
    item["median"] = statistics.median(item["samples"])
    item["ratio_to_mpi"] = item["median"] / mpi
    assert len(item["samples"]) == 7

plt.rcParams.update({"font.size": 11, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.spines.left": False})
fig, ax = plt.subplots(figsize=(10, 4.2 if final_mode else 5.1), layout="constrained")
colors = (["#687584", "#4e7da6", "#329286", "#216d63"] if final_mode else
          ["#687584", "#bb5a38", "#7396b7", "#4e7da6", "#329286", "#216d63"])
for row, (item, color) in enumerate(zip(records, colors)):
    ax.barh(row, item["median"], color=color, height=0.57, alpha=0.85)
    ax.scatter(item["samples"], [row] * 7, c="#182a38", s=17, zorder=3,
               linewidths=0.4, edgecolors="white")
    ax.text(max(item["samples"]) + 0.17, row,
            f'{item["median"]:.3f} s  ({item["ratio_to_mpi"]:.2f}× MPI)',
            va="center", fontsize=10)
ax.set_yticks(range(len(records)), [item["label"] for item in records])
ax.invert_yaxis()
ax.set_xlim(0, max(max(item["samples"]) for item in records) + 3.9)
ax.set_xlabel("Forward transform time (seconds; lower is faster)")
ax.set_title("QueenBee · 1024³ complex FFT · 4 nodes × 64 workers", loc="left", weight="bold")
ax.xaxis.grid(True, alpha=0.16)
ax.set_axisbelow(True)
ax.tick_params(axis="y", length=0)
runtime_caption = ("All HPX versions: MPI/global background workers = 1; 1000 ms idle cap."
                   if final_mode else
                   "Modified HPX versions limit both MPI and global background workers to one.")
fig.supxlabel("Bars: medians. Dots: seven samples, each the maximum over four ranks.\n"
              "Same allocation, FFTW_ESTIMATE, two warmups; inverse and checks excluded.\n"
              + runtime_caption,
              fontsize=9)
out.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out.with_suffix(".png"), dpi=180)
fig.savefig(out.with_suffix(".svg"))
out.with_suffix(".json").write_text(json.dumps({"job": root.name, "records": records}, indent=2) + "\n")
print(out.with_suffix(".png"))
