#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
"""Freeze current owned inputs after local validation; never access QueenBee."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile

repo = Path(__file__).resolve().parents[2]
bundle = Path(__file__).resolve().parent / 'bundle'
target = bundle / 'source'
assert not target.exists(), 'Input source snapshot already frozen; preserve it.'
files = ['hpx/hpx-comm.cpp', 'hpx/hpx-comm.h', 'hpx/transpose-pairwise.c',
         'hpx/hpx-comm-check.cpp', 'benchmarks/matched_3d.cpp', 'benchmarks/summarize.py']
for name in files:
    destination = target / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(repo / name), str(destination))
driver_hash = hashlib.sha256((target / 'benchmarks/matched_3d.cpp').read_bytes()).hexdigest()
assert driver_hash == '9327f8e3e9bb4a78509e7e12f11c093125dd67cdc0ab6b56fbdb8728fc7c4d41'
provenance = dict(license='GPL-2.0-or-later',
    source_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=str(repo), universal_newlines=True).strip(),
    candidate_source='Explicit frozen working-tree inputs; source changes not yet committed',
    hpx_source_commit='c9b81b401fbe6ba4a0306feff71d18ef01c71b34',
    hpx_changes=False, tcp_enabled=False, mpi_implementation='Open MPI 5.0.11',
    workload='1024^3 double-complex in-place FFTW_ESTIMATE, 4 nodes, 1 rank/node, 64 FFT workers/rank, 2 warmups, 7 samples',
    runtime_selector='FFTW_HPX_TRANSPOSE_EXCHANGE', modes=['pairwise', 'all_to_all'],
    idle_backoff_cap_ms=10, source_hashes={name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in files})
(bundle / 'PROVENANCE.json').write_text(json.dumps(provenance, indent=2) + '\n')
(bundle / 'SOURCE.diff').write_bytes(subprocess.check_output(['git', 'diff', '--'] + files, cwd=str(repo)))
paths = sorted(p for p in bundle.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'SHA256SUMS')
(bundle / 'SHA256SUMS').write_text(''.join('{}  {}\n'.format(hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(bundle)) for p in paths))
archive = bundle.parent / 'alltoall_bundle.tar.gz'
with tarfile.open(str(archive), 'w:gz') as output:
    output.add(str(bundle), arcname='alltoall', filter=lambda entry: None if '__pycache__' in entry.name else entry)
print(json.dumps(dict(bundle=str(bundle), archive=str(archive), sha256=hashlib.sha256(archive.read_bytes()).hexdigest()), indent=2))
