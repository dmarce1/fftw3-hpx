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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Seed a fresh, offline HPX build from explicit options, never old internals.

Python 3.6 compatible. The prepare step is data processing only; configure,
compile, and installation belong to the separately reviewed Slurm script.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex


ORIGINAL = Path('/work/dmarce1/OctotigerII/experiments/isolated-solvers-2026-09-30/source/packages/release/hpx')
DESTINATION = Path('/work/dmarce1/fftw3_hpx_remaining_20261023/lean_hpx')
SOURCE_COMMIT = 'c9b81b401fbe6ba4a0306feff71d18ef01c71b34'
LEAN_OFF = (
    'APEX', 'FETCH_APEX', 'PARCEL_PROFILING', 'LOGGING', 'IO_COUNTERS',
    'THREAD_CUMULATIVE_COUNTS',
)
DEBUG_OFF = (
    'VERIFY_LOCKS', 'VERIFY_LOCKS_BACKTRACE', 'THREAD_BACKTRACE_ON_SUSPENSION',
    'SPINLOCK_DEADLOCK_DETECTION', 'THREAD_DEBUG_INFO',
    'STACKOVERFLOW_DETECTION', 'SANITIZERS', 'VALGRIND', 'ITTNOTIFY',
    'ATTACH_DEBUGGER_ON_TEST_FAILURE', 'TESTS_DEBUG_LOG',
)
REQUIRED_ON = (
    'DISTRIBUTED_RUNTIME', 'NETWORKING', 'PARCELPORT_MPI',
    'PARCELPORT_MPI_MULTITHREADED', 'ASYNC_MPI', 'THREAD_GUARD_PAGE',
    'THREAD_MANAGER_IDLE_BACKOFF', 'IO_POOL', 'TIMER_POOL',
)
PORTABLE = (
    'CMAKE_C_COMPILER', 'CMAKE_CXX_COMPILER', 'CMAKE_CXX_FLAGS', 'CMAKE_C_FLAGS',
    'CMAKE_CXX_FLAGS_RELEASE', 'CMAKE_C_FLAGS_RELEASE', 'CMAKE_INSTALL_LIBDIR',
    'CMAKE_PREFIX_PATH', 'Boost_DIR', 'Hwloc_INCLUDE_DIR', 'Hwloc_LIBRARY',
    'Jemalloc_INCLUDE_DIR', 'Jemalloc_LIBRARY', 'MPI_CXX_COMPILER', 'MPI_HOME',
)


def cache(path):
    result = {}
    for line in Path(path).read_text().splitlines():
        match = re.match(r'^([^/#][^:]*):([^=]+)=(.*)$', line)
        if match:
            key, kind, value = match.groups()
            result[key] = (kind, value)
    return result


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def prepare(original, output):
    values = cache(original)
    require(values['CMAKE_BUILD_TYPE'][1] == 'Release', 'Original must be Release')
    require(values['HPX_WITH_MALLOC'][1] == 'jemalloc', 'Allocator drift')
    require(values['HPX_WITH_STDEXEC'][1] == 'OFF', 'Unexpected active stdexec fetch')
    require(values['HPX_WITH_FETCH_ASIO'][1] == 'ON', 'Expected bundled Asio')
    for suffix in REQUIRED_ON:
        require(values['HPX_WITH_' + suffix][1] == 'ON', 'Original drift: ' + suffix)
    for suffix in DEBUG_OFF + ('PARCELPORT_TCP', 'THREAD_STACK_MMAP'):
        require(values['HPX_WITH_' + suffix][1] == 'OFF', 'Original drift: ' + suffix)
    # Carry all external HPX options, including module-prefixed feature switches.
    # INTERNAL feature checks and CMAKE source/build directories are excluded.
    seed = {key: entry for key, entry in values.items()
            if key.startswith('HPX_') and entry[0] in ('BOOL', 'STRING', 'PATH', 'FILEPATH')}
    for key in PORTABLE:
        if key in values:
            kind, value = values[key]
            seed[key] = ('STRING' if kind == 'UNINITIALIZED' else kind, value)
    for suffix in LEAN_OFF + DEBUG_OFF:
        require('HPX_WITH_' + suffix in values, 'Unknown original option: ' + suffix)
        seed['HPX_WITH_' + suffix] = ('BOOL', 'OFF')
    seed.update({
        'CMAKE_BUILD_TYPE': ('STRING', 'Release'),
        'CMAKE_INSTALL_PREFIX': ('PATH', str(DESTINATION / 'install')),
        'CMAKE_CXX_FLAGS_RELEASE': ('STRING', '-O3 -DNDEBUG'),
        'CMAKE_C_FLAGS_RELEASE': ('STRING', '-O3 -DNDEBUG'),
        'CMAKE_EXPORT_COMPILE_COMMANDS': ('BOOL', 'ON'),
        'FETCHCONTENT_SOURCE_DIR_ASIO': ('PATH', str(ORIGINAL / 'build/_deps/asio-src')),
        'FETCHCONTENT_BASE_DIR': ('PATH', str(DESTINATION / 'build/_deps')),
        'FETCHCONTENT_FULLY_DISCONNECTED': ('BOOL', 'ON'),
        'FETCHCONTENT_UPDATES_DISCONNECTED': ('BOOL', 'ON'),
    })
    output.mkdir(parents=True, exist_ok=True)
    text = ['# Generated from the verified original cache by GPL-2.0-or-later prepare.py.']
    for key, (kind, value) in sorted(seed.items()):
        require(']==]' not in value and '\n' not in value, 'Unsafe CMake literal')
        text.append('set({} [==[{}]==] CACHE {} "Isolated HPX comparison" FORCE)'.format(key, value, kind))
    (output / 'initial-cache.cmake').write_text('\n'.join(text) + '\n')
    changed = {key: {'before': values.get(key, [None, None])[1], 'after': value}
               for key, (_, value) in seed.items() if values.get(key, [None, None])[1] != value}
    record = {'source_commit': SOURCE_COMMIT,
              'original_cache_sha256': hashlib.sha256(Path(original).read_bytes()).hexdigest(),
              'seed': seed, 'intentional_changes': changed}
    (output / 'configuration.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PREPARE_PASS retained_external_options={} intentional_changes={}'.format(len(seed), len(changed)))


def audit(configuration, build, install):
    record = json.loads(configuration.read_text())
    actual = cache(build / 'CMakeCache.txt')
    for key, (_, expected) in record['seed'].items():
        require(key in actual and actual[key][1] == expected, 'Configured option mismatch: ' + key)
    commands = json.loads((build / 'compile_commands.json').read_text())
    require(bool(commands), 'No compilation commands')
    for entry in commands:
        flags = entry.get('arguments') or shlex.split(entry['command'])
        require('-O3' in flags and '-DNDEBUG' in flags, 'Non-release compilation: ' + entry['file'])
        require(not any(flag.startswith('-DHPX_DEBUG') or flag.startswith('-fsanitize') for flag in flags),
                'Debug/sanitizer compile flag: ' + entry['file'])
    if install:
        headers = list((install / 'include/hpx').glob('**/config/defines.hpp'))
        require(bool(headers), 'No installed HPX config headers')
        defines = set()
        commit = None
        for header in headers:
            for line in header.read_text().splitlines():
                match = re.match(r'^\s*#\s*define\s+(HPX_\w+)\b(.*)', line)
                if match:
                    defines.add(match.group(1))
                    if match.group(1) == 'HPX_HAVE_GIT_COMMIT':
                        commit = match.group(2).strip().strip('"')
        forbidden = set('HPX_HAVE_' + key for key in LEAN_OFF + DEBUG_OFF)
        forbidden.update(('HPX_DEBUG', 'HPX_HAVE_THREAD_DESCRIPTION',
                          'HPX_HAVE_THREAD_PARENT_REFERENCE', 'HPX_HAVE_THREAD_PHASE_INFORMATION',
                          'HPX_HAVE_THREAD_MINIMAL_DEADLOCK_DETECTION', 'HPX_HAVE_PARCELPORT_TCP'))
        require(not forbidden.intersection(defines), 'Unexpected instrumentation defines: ' + str(sorted(forbidden.intersection(defines))))
        for suffix in REQUIRED_ON:
            require('HPX_HAVE_' + suffix in defines, 'Missing preserved define: ' + suffix)
        require(commit == SOURCE_COMMIT, 'Installed source commit mismatch')
    print('AUDIT_PASS options={} compile_commands={} installed={}'.format(len(record['seed']), len(commands), bool(install)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode')
    prep = sub.add_parser('prepare')
    prep.add_argument('original', type=Path)
    prep.add_argument('output', type=Path)
    check = sub.add_parser('audit')
    check.add_argument('configuration', type=Path)
    check.add_argument('build', type=Path)
    check.add_argument('--install', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.original, args.output)
    elif args.mode == 'audit':
        audit(args.configuration, args.build, args.install)
    else:
        parser.error('Select prepare or audit')


if __name__ == '__main__':
    main()
