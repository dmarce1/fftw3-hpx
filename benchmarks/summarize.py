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
"""Validate two matched benchmark logs and emit their timing comparison."""
import json
import math
from pathlib import Path
import re
import statistics
import sys


def fields(line):
    return dict(token.split("=", 1) for token in line.split()[1:] if "=" in token)


def read(path, backend):
    text = Path(path).read_text()
    lines = text.splitlines()
    config, = [fields(line) for line in lines if line.startswith("CONFIG ")]
    result, = [fields(line) for line in lines if line.startswith("RESULT ")]
    assert config["backend"] == backend == result["backend"]
    assert result["status"] == "PASS"
    checks = [fields(line) for line in lines if line.startswith("CHECK ")]
    assert {item["stage"] for item in checks} == {"forward_spectrum", "initial_roundtrip", "final_roundtrip"}
    assert len(checks) == 3
    for item in checks:
        value = float(item["relative_max_error"])
        assert math.isfinite(value) and value <= float(item["tolerance"])
    samples = [fields(line) for line in lines if line.startswith("SAMPLE ")]
    assert [int(item["index"]) for item in samples] == list(range(int(config["samples"])))
    values = [float(item["max_rank_seconds"]) for item in samples]
    assert all(math.isfinite(value) and value > 0 for value in values)
    for key, value in (("min_seconds", min(values)), ("median_seconds", statistics.median(values)),
                       ("mean_seconds", statistics.mean(values)), ("max_seconds", max(values))):
        assert math.isclose(float(result[key]), value, rel_tol=1e-13), key
    plans = {}
    for direction in ("FORWARD", "BACKWARD"):
        match = re.search("PLAN_" + direction + "_BEGIN\n(.*?)\nPLAN_" + direction + "_END", text, re.S)
        assert match
        plans[direction.lower()] = match.group(1)
    return dict(configuration=config, checks=checks, samples_seconds=values, result=result, plans=plans)


mpi = read(sys.argv[1], "mpi")
hpx = read(sys.argv[2], "hpx")
for key in ("extent", "ranks", "threads", "precision", "inplace", "layout", "planner", "warmups", "samples"):
    assert mpi["configuration"][key] == hpx["configuration"][key], key
ratio = float(hpx["result"]["median_seconds"]) / float(mpi["result"]["median_seconds"])
comparison = dict(mpi=mpi, hpx=hpx, hpx_over_mpi_median_ratio=ratio,
                  hpx_relative_time_percent=100 * (ratio - 1),
                  normalized_plans_equal={key: mpi["plans"][key] == hpx["plans"][key].replace("hpx-", "mpi-")
                                          for key in mpi["plans"]})
print(json.dumps(comparison, indent=2))
