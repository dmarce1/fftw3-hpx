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


"""Validate and copy job1125884 artifacts without compiling or changing them."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys


def require(value, message):
    if not value:
        raise RuntimeError(message)


def digest(path):
    require(path.is_file() and not path.is_symlink(), 'Missing/nonregular input: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    previous, output, source, bundle = map(Path, sys.argv[1:])
    require(previous.name == '1125884', 'Only the reviewed failed build may be reused')
    status = dict(line.split('\t', 1) for line in (previous / 'FINAL_STATUS').read_text().splitlines())
    require(status['status'] == 'FAIL' and status['stage'] == 'archive_members', 'Unexpected prior failure stage')
    require(status['exit_status'] != '0', 'Invalid prior failure status')
    error = (previous / 'archive_members.log').read_text()
    require("unexpected keyword argument 'text'" in error, 'Expected Python 3.6 text keyword failure')
    job = (previous / 'job.log').read_text()
    required_steps = ('instrument', 'compile_bridge_pool_release', 'replace_bridge_pool_release',
                      'compile_matched_pool_release', 'compile_profile', 'compile_mpi_interposer',
                      'compile_threads_profile', 'replace_threads', 'compile_mpi_pairwise',
                      'replace_mpi_pairwise', 'compile_hpx_pairwise', 'compile_bridge_hpx_profile',
                      'replace_bridge_hpx_profile', 'replace_hpx_pairwise', 'compile_matched_hpx_profile',
                      'compile_mpi_profile')
    for step in required_steps:
        require(re.search(r'^PASS ' + re.escape(step) + r' ', job, re.M), 'Prior stage not completed: ' + step)
    require(not list(previous.glob('benchmark_*.log')), 'Unexpected benchmark from failed build')
    manifest = json.loads((previous / 'remaining_profile_manifest.json').read_text())
    require(manifest['diagnostic_only'] and manifest['threads'] and manifest['pairwise'], 'Wrong diagnostic scopes')
    expected_files = {'hpx/hpx-comm.cpp', 'benchmarks/matched_3d.cpp', 'threads/threads.c',
                      'hpx/transpose-pairwise.c', 'mpi/transpose-pairwise.c',
                      'benchmarks/remaining_profile.h', 'benchmarks/remaining_profile.cpp',
                      'benchmarks/remaining_mpi_profile.cpp'}
    require(set(manifest['files']) == expected_files, 'Unexpected diagnostic source set')
    preserved = {}
    for name, record in manifest['files'].items():
        generated = previous / 'diagnostic_source' / name
        expected = record.get('after_sha256', record.get('generated_sha256'))
        require(digest(generated) == expected, 'Diagnostic source changed: ' + name)
        preserved[str(generated)] = expected
        if 'before_sha256' in record:
            require(digest(source / name) == record['before_sha256'], 'Current source differs: ' + name)
        else:
            require(digest(bundle / 'profile' / Path(name).name) == expected, 'Diagnostic helper differs: ' + name)
    require(digest(previous / 'hpx-flags.sh') == digest(output / 'hpx-flags.sh'), 'HPX link flags changed')
    for tree in ('bin', 'objects'):
        before = previous / tree
        files = sorted(path for path in before.rglob('*') if path.is_file())
        require(bool(files), 'Missing previous artifact tree: ' + tree)
        for path in files:
            require(not path.is_symlink(), 'Refusing symlinked artifact: ' + str(path))
            target = output / path.relative_to(previous)
            require(not target.exists(), 'Refusing existing output: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            value = digest(path)
            shutil.copy2(str(path), str(target))
            require(digest(target) == value and digest(path) == value, 'Copy digest mismatch: ' + str(path))
            preserved[str(path)] = value
    require({p.name for p in (output / 'bin').iterdir()} == {'pool_release', 'hpx_profile', 'mpi_profile'}, 'Unexpected binary set')
    evidence = output / 'reused_build'
    evidence.mkdir()
    for name in ('FINAL_STATUS', 'job.sbatch', 'common.sh', 'job.log', 'fixed_inputs.sha256',
                 'remaining_profile_manifest.json', 'hpx-flags.sh', 'archive_members.log'):
        path = previous / name
        preserved[str(path)] = digest(path)
        shutil.copy2(str(path), str(evidence / name))
    for path in sorted(previous.glob('*.command')):
        preserved[str(path)] = digest(path)
        shutil.copy2(str(path), str(evidence / path.name))
    shutil.copy2(str(previous / 'remaining_profile_manifest.json'), str(output / 'remaining_profile_manifest.json'))
    (output / 'reused_inputs.sha256').write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(preserved.items())))
    copied = {}
    for tree in ('bin', 'objects'):
        for path in sorted((output / tree).rglob('*')):
            if path.is_file():
                copied[str(path.relative_to(output))] = digest(path)
    (output / 'reused_artifacts.sha256').write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(copied.items())))
    print(json.dumps({'status': 'PASS', 'previous_job': '1125884', 'copied_artifacts': copied,
                      'diagnostic_sources_verified': len(expected_files),
                      'completed_compile_and_link_stages': list(required_steps),
                      'note': 'Hashes recorded at guarded reuse; prior job stopped before its final artifact manifest.'}, indent=2))


if __name__ == '__main__':
    main()
