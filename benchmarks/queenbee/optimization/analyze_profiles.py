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
"""Validate and analyze complete instrumented matched_3d HPX benchmark logs.

Pass log paths or a results directory. Directory inputs select only
benchmark_*profile*.log. Default expectations are four ranks and seven samples.
Use --json for full machine-readable results, including every rank/sample.
No benchmark, build, remote access, or input mutation is performed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys

METRICS = (
    "copy_bytes_inclusive", "message_bytes_inclusive", "receive_bytes_inclusive",
    "run_jobs_inclusive", "send_inclusive", "recv_inclusive", "sendrecv_inclusive",
)
CONFIGURATION_KEYS = (
    "extent", "ranks", "threads", "precision", "inplace", "layout", "planner",
    "warmups", "samples",
)
MARKER = re.compile(r"(?:^|\s)(PROFILE_TOTAL|PROFILE|SAMPLE|RESULT|CONFIG_DIAGNOSTIC|CONFIG|CHECK) (?=\w+=)")
NOTES = [
    "All durations are seconds. PROFILE counters are inclusive wall times, not CPU times.",
    "Copy, message construction, and receive counters are contained in send/recv/sendrecv; do not add them to those totals.",
    "Residual = each rank/sample total - run_jobs - sendrecv. This decomposition requires the audited nonnested forward plan and no separate send/recv calls.",
    "Residual includes serial transposes, other uninstrumented FFT work, and wrapper/instrumentation/clock overhead; it is not an exclusive serial-transpose measurement.",
    "Medians are computed independently per component; their sum need not equal the median total. Critical-rank rows use components from the actual maximum-time rank for each sample.",
    "Instrumented results are diagnostic and must not replace the uninstrumented primary benchmark.",
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(text):
    result = {}
    for token in text.split():
        require("=" in token, "Malformed field: " + token)
        key, value = token.split("=", 1)
        require(key not in result, "Duplicate field: " + key)
        result[key] = value
    return result


def number(text, label, positive=False):
    value = float(text)
    require(math.isfinite(value) and (value > 0 if positive else value >= 0),
            "Invalid " + label + ": " + text)
    return value


def integer(text, label):
    require(re.fullmatch(r"[0-9]+", text) is not None, "Invalid " + label + ": " + text)
    return int(text)


def close(left, right):
    return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-9)


def put_unique(container, key, value, label):
    require(key not in container, "Duplicate " + label + ": " + str(key))
    container[key] = value


def read_run(path, rank_count, sample_count):
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    profiles, totals, samples, diagnostics, checks = {}, {}, {}, {}, {}
    configurations, results = [], []
    for line_number, line in enumerate(text.splitlines(), 1):
        markers = list(MARKER.finditer(line))
        if not markers:
            continue
        require(len(markers) == 1, "Interleaved records at line " + str(line_number))
        marker = markers[0]
        kind = marker.group(1)
        payload = line[marker.end():]
        if kind == "CONFIG_DIAGNOSTIC":
            match = re.fullmatch(r"rank=([0-9]+) key=(\S+) value=(.*)", payload)
            require(match is not None, "Malformed diagnostic configuration at line " + str(line_number))
            rank = int(match.group(1))
            require(rank < rank_count, "Unexpected diagnostic rank " + str(rank))
            put_unique(diagnostics, (rank, match.group(2)), match.group(3), "configuration")
            continue
        row = fields(payload)
        if kind == "PROFILE":
            require(set(row) == {"rank", "sample", "metric", "calls", "seconds"}, "Unexpected PROFILE fields")
            rank = integer(row["rank"], "rank")
            sample = integer(row["sample"], "sample")
            metric = row["metric"]
            require(rank < rank_count and sample < sample_count and metric in METRICS, "Unexpected PROFILE key " + str((rank, sample, metric)))
            calls = integer(row["calls"], "calls")
            seconds = number(row["seconds"], "profile seconds")
            require(calls > 0 or seconds == 0, "Nonzero duration for zero calls")
            put_unique(profiles, (rank, sample, metric), {"calls": calls, "seconds": seconds}, "PROFILE")
        elif kind == "PROFILE_TOTAL":
            require(set(row) == {"rank", "sample", "seconds"}, "Unexpected PROFILE_TOTAL fields")
            key = (integer(row["rank"], "rank"), integer(row["sample"], "sample"))
            require(key[0] < rank_count and key[1] < sample_count, "Unexpected PROFILE_TOTAL key " + str(key))
            put_unique(totals, key, number(row["seconds"], "total seconds", positive=True), "PROFILE_TOTAL")
        elif kind == "SAMPLE":
            require(set(row) == {"backend", "index", "max_rank_seconds"} and row["backend"] == "hpx", "Unexpected SAMPLE fields/backend")
            index = integer(row["index"], "sample index")
            require(index < sample_count, "Unexpected SAMPLE index")
            put_unique(samples, index, number(row["max_rank_seconds"], "SAMPLE seconds", positive=True), "SAMPLE")
        elif kind == "CONFIG":
            configurations.append(row)
        elif kind == "RESULT":
            results.append(row)
        elif kind == "CHECK":
            put_unique(checks, row["stage"], row, "CHECK stage")

    expected = {(rank, sample, metric) for rank in range(rank_count)
                for sample in range(sample_count) for metric in METRICS}
    require(set(profiles) == expected, "Incomplete PROFILE matrix: got {}, expected {}; missing {}".format(len(profiles), len(expected), sorted(expected - set(profiles))[:5]))
    expected_totals = {(rank, sample) for rank in range(rank_count) for sample in range(sample_count)}
    require(set(totals) == expected_totals, "Incomplete PROFILE_TOTAL matrix: got {}, expected {}".format(len(totals), len(expected_totals)))
    require(set(samples) == set(range(sample_count)), "Incomplete SAMPLE records")
    require(len(configurations) == len(results) == 1, "Expected one CONFIG and one RESULT")
    configuration, result = configurations[0], results[0]
    require(configuration["backend"] == result["backend"] == "hpx", "Expected HPX backend")
    require(result["status"] == "PASS", "Benchmark RESULT did not pass")
    for row in (configuration, result):
        require(integer(row["ranks"], "ranks") == rank_count and integer(row["samples"], "samples") == sample_count, "Unexpected configured ranks or samples")
    for key in ("extent", "threads"):
        require(configuration[key] == result[key], "CONFIG/RESULT mismatch: " + key)
    require(set(checks) == {"forward_spectrum", "initial_roundtrip", "final_roundtrip"}, "Incomplete correctness checks")
    for row in checks.values():
        require(number(row["relative_max_error"], "check error") <= number(row["tolerance"], "check tolerance", positive=True), "Failed correctness check " + row["stage"])
    sample_values = [samples[index] for index in range(sample_count)]
    for key, value in (("min_seconds", min(sample_values)), ("median_seconds", statistics.median(sample_values)),
                       ("mean_seconds", statistics.mean(sample_values)), ("max_seconds", max(sample_values))):
        require(close(number(result[key], key, positive=True), value), "RESULT does not match SAMPLE: " + key)

    plans = {}
    for direction in ("FORWARD", "BACKWARD"):
        matches = re.findall(r"^PLAN_" + direction + r"_BEGIN\n(.*?)\nPLAN_" + direction + r"_END$", text, re.MULTILINE | re.DOTALL)
        require(len(matches) == 1, "Expected one " + direction + " plan")
        normalized = matches[0].replace("hpx-", "mpi-")
        plans[direction.lower()] = hashlib.sha256(normalized.encode()).hexdigest()

    rank_samples, per_rank, critical = [], [], []
    for rank in range(rank_count):
        rank_rows = []
        for sample in range(sample_count):
            metrics = {name: profiles[(rank, sample, name)] for name in METRICS}
            require(metrics["send_inclusive"]["calls"] == metrics["recv_inclusive"]["calls"] == 0, "Separate send/recv calls invalidate the requested two-phase residual")
            residual = totals[(rank, sample)] - metrics["run_jobs_inclusive"]["seconds"] - metrics["sendrecv_inclusive"]["seconds"]
            require(residual >= -1e-6, "Negative residual suggests nested/overlapping phase timers: rank {} sample {}".format(rank, sample))
            row = {"rank": rank, "sample": sample, "total_seconds": totals[(rank, sample)],
                   "residual_seconds": residual, "metrics": metrics}
            rank_rows.append(row)
            rank_samples.append(row)
        per_rank.append({
            "rank": rank,
            "median_seconds": dict(
                [("total", statistics.median(row["total_seconds"] for row in rank_rows)),
                 ("residual", statistics.median(row["residual_seconds"] for row in rank_rows))] +
                [(name, statistics.median(row["metrics"][name]["seconds"] for row in rank_rows)) for name in METRICS]),
            "calls_per_sample": {name: sorted({row["metrics"][name]["calls"] for row in rank_rows}) for name in METRICS},
        })
    for sample in range(sample_count):
        rows = [row for row in rank_samples if row["sample"] == sample]
        maximum = max(row["total_seconds"] for row in rows)
        require(close(maximum, samples[sample]), "Rank maximum differs from SAMPLE at index {}: {} vs {}".format(sample, maximum, samples[sample]))
        tied = [row for row in rows if row["total_seconds"] == maximum]
        critical.append({"sample": sample, "critical_ranks": [row["rank"] for row in tied],
                         "sample_max_seconds": samples[sample], "rank_max_seconds": maximum,
                         "difference_seconds": maximum - samples[sample], "decompositions": tied})
    return {
        "path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
        "validated_counts": {"PROFILE": len(profiles), "PROFILE_TOTAL": len(totals), "SAMPLE": len(samples)},
        "configuration": configuration, "checks": checks, "result": result,
        "normalized_plan_sha256": plans, "per_rank": per_rank,
        "critical_rank_per_sample": critical, "rank_samples": rank_samples,
        "diagnostic_configuration": {str(rank): {key: value for (site, key), value in diagnostics.items() if site == rank} for rank in range(rank_count)},
    }


def print_table(rows):
    print("rank/sample  total       run_jobs    sendrecv    copy_bytes  receive     residual")
    for label, total, jobs, sendrecv, copy, receive, residual in rows:
        print("{:<11} {:>11.6f} {:>11.6f} {:>11.6f} {:>11.6f} {:>11.6f} {:>11.6f}".format(label, total, jobs, sendrecv, copy, receive, residual))


def print_report(report):
    for note in report["notes"]:
        print("NOTE: " + note)
    print("Normalized plans equal across runs: " + json.dumps(report["normalized_plans_equal"]))
    for run in report["runs"]:
        print("\nRUN " + run["path"])
        print("Validated rows: " + json.dumps(run["validated_counts"], sort_keys=True))
        print("Benchmark median (maximum over ranks): " + run["result"]["median_seconds"] + " seconds")
        print("Per-rank component medians:")
        rows = []
        for rank in run["per_rank"]:
            values = rank["median_seconds"]
            rows.append((str(rank["rank"]), values["total"], values["run_jobs_inclusive"], values["sendrecv_inclusive"], values["copy_bytes_inclusive"], values["receive_bytes_inclusive"], values["residual"]))
        print_table(rows)
        print("Actual critical-rank decomposition per sample (rank/sample):")
        rows = []
        for sample in run["critical_rank_per_sample"]:
            for row in sample["decompositions"]:
                metrics = row["metrics"]
                rows.append(("{}/{}".format(row["rank"], row["sample"]), row["total_seconds"], metrics["run_jobs_inclusive"]["seconds"], metrics["sendrecv_inclusive"]["seconds"], metrics["copy_bytes_inclusive"]["seconds"], metrics["receive_bytes_inclusive"]["seconds"], row["residual_seconds"]))
        print_table(rows)
        print("SAMPLE cross-check: all rank maxima match; largest absolute difference {:.17g} seconds".format(max(abs(row["difference_seconds"]) for row in run["critical_rank_per_sample"])))
        print("Phase calls per sample: " + json.dumps({str(row["rank"]): {name: row["calls_per_sample"][name] for name in ("run_jobs_inclusive", "sendrecv_inclusive")} for row in run["per_rank"]}, sort_keys=True))
        for rank, entries in sorted(run["diagnostic_configuration"].items()):
            selected = {key: value for key, value in entries.items() if "zero_copy" in key or key in ("hpx.parcel.mpi.background_threads", "hpx.parcel.mpi.multithreaded")}
            if selected:
                print("Runtime configuration rank=" + rank + " " + json.dumps(selected, sort_keys=True))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="profile log paths or result directories")
    parser.add_argument("--ranks", type=int, default=4)
    parser.add_argument("--samples", type=int, default=7)
    parser.add_argument("--json", action="store_true", help="emit full JSON instead of text tables")
    args = parser.parse_args(argv)
    require(args.ranks > 0 and args.samples > 0, "Rank and sample expectations must be positive")
    paths = []
    for entry in args.inputs:
        found = sorted(entry.glob("benchmark_*profile*.log")) if entry.is_dir() else [entry]
        require(found, "No profile logs found in " + str(entry))
        for path in found:
            if path.resolve() not in [item.resolve() for item in paths]:
                paths.append(path)
    runs = []
    for path in paths:
        try:
            runs.append(read_run(path, args.ranks, args.samples))
        except (ValueError, KeyError, OSError) as error:
            raise ValueError(str(path) + ": " + str(error)) from error
    for key in CONFIGURATION_KEYS:
        require(len({run["configuration"][key] for run in runs}) == 1, "Configurations differ across runs: " + key)
    report = {"notes": NOTES, "normalized_plans_equal": {direction: len({run["normalized_plan_sha256"][direction] for run in runs}) == 1 for direction in ("forward", "backward")}, "runs": runs}
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    else:
        print_report(report)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        sys.exit(1)
