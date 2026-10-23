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
"""Instrument a disposable source snapshot; never builds or runs a benchmark.

Usage: instrument.py SOURCE_DIR [--threads] [--pairwise]
Link remaining_profile.cpp into BOTH diagnostic executables; also link
remaining_mpi_profile.cpp into MPI. Replace only the changed archive members.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

MARKER = 'FFTW_REMAINING_DIAGNOSTIC_PROFILE'


def once(text, old, new, label):
    if text.count(old) != 1:
        raise ValueError(f'{label}: expected one anchor, got {text.count(old)}')
    return text.replace(old, new, 1)


def function_span(text, pattern):
    matches = list(re.finditer(pattern, text, re.M))
    if len(matches) != 1:
        raise ValueError(f'function pattern {pattern}: {len(matches)} matches')
    opening = matches[0].end() - 1
    depth, index = 1, opening + 1
    while depth:
        if text.startswith('//', index):
            index = text.index('\n', index) + 1
        elif text.startswith('/*', index):
            index = text.index('*/', index) + 2
        elif text[index] in ('"', "'"):
            quote = text[index]
            index += 1
            while text[index] != quote:
                index += 2 if text[index] == '\\' else 1
            index += 1
        else:
            depth += (text[index] == '{') - (text[index] == '}')
            index += 1
    return opening, index - 1


def edit_function(text, pattern, change):
    start, end = function_span(text, pattern)
    return text[:start+1] + change(text[start+1:end]) + text[end:]


def prepend_scope(text, pattern, expression):
    return edit_function(text, pattern, lambda body: '\n    '+expression+'\n'+body)


def bridge_edit(text):
    text = once(text, '#include "hpx-comm.h"\n',
                '#include "hpx-comm.h"\n#include "../benchmarks/remaining_profile.h"\n', 'bridge include')
    text = once(text, '    char * allocate(size_t const bytes)\n    {\n        if (bytes != 0)',
                '    char * allocate(size_t const bytes)\n    {\n        FrpScope const profile(FRP_POOL_ALLOCATE, bytes);\n        if (bytes != 0)', 'pool allocate')
    text = once(text, '                return result;\n',
                '                frp_event(FRP_POOL_HIT, bytes);\n                return result;\n', 'pool hit')
    text = once(text, '        return new char[bytes];\n',
                '        frp_event(FRP_POOL_MISS, bytes);\n        FrpScope const heap(FRP_HEAP_ALLOCATE, bytes);\n        return new char[bytes];\n', 'pool miss')
    text = once(text, '    void deallocate(char * data, size_t const bytes) noexcept\n    {\n',
                '    void deallocate(char * data, size_t const bytes) noexcept\n    {\n        FrpScope const profile(FRP_POOL_DEALLOCATE, bytes);\n', 'pool deallocate')
    text = once(text, '                std::swap(data, cached);\n',
                '                frp_event(FRP_POOL_KEEP, bytes);\n                std::swap(data, cached);\n', 'pool keep')
    text = once(text, '        // Potentially expensive heap release never holds the pool mutex.\n        delete[] data;',
                '        // Potentially expensive heap release never holds the pool mutex.\n        if (data != nullptr) { frp_event(FRP_POOL_DELETE, bytes); }\n        delete[] data;', 'pool delete')
    text = once(text, '        return pool ? pool->allocate(bytes) : new char[bytes];',
                '        if (pool) { return pool->allocate(bytes); }\n        frp_event(FRP_POOL_MISS, bytes);\n        FrpScope const heap(FRP_HEAP_ALLOCATE, bytes);\n        return new char[bytes];', 'unpooled allocator')
    text = once(text, '        std::memcpy(data, payload.data(), bytes);',
                '        FrpScope const profile(FRP_RECEIVE_COPY, bytes);\n        std::memcpy(data, payload.data(), bytes);', 'receive copy')
    text = prepend_scope(text, r'^void runJobs\([^{};]*\n\{',
                         'FrpScope const profile(FRP_RUN_JOBS);\n    FrpJobs const jobs;')
    text = once(text, '    for (int job = 0; job < jobCount - 1; ++job)\n',
                '    {\n    FrpScope const enqueue(FRP_ENQUEUE);\n    for (int job = 0; job < jobCount - 1; ++job)\n', 'enqueue start')
    text = once(text, '        futures.push_back(hpx::async(executor, [work, data] { work(data); }));',
                '        FrpToken const queued = frp_begin(FRP_QUEUE_DELAY, 0);\n'
                '        futures.push_back(hpx::async(executor, [work, data, queued]\n'
                '        {\n            frp_end(queued);\n            FrpTask const task;\n            work(data);\n        }));', 'async task')
    text = once(text, '    work(jobData + static_cast<size_t>(jobCount - 1) * elementSize);\n    hpx::wait_all(futures);',
                '    }\n    {\n        FrpScope const inlineWork(FRP_INLINE_WORK);\n        FrpTask const task;\n'
                '        work(jobData + static_cast<size_t>(jobCount - 1) * elementSize);\n    }\n'
                '    {\n        FrpScope const wait(FRP_JOIN);\n        hpx::wait_all(futures);\n    }', 'inline and join')
    def exchange(body):
        body = '\n    FrpScope const profile(FRP_EXCHANGE, byteCount(sendCount, sendSize));\n'+body
        body = once(body, '    auto sent = collectives::set(',
                    '    auto sent = [&]\n    {\n        FrpScope const initiation(FRP_SEND_INIT);\n        return collectives::set(', 'send start')
        body = once(body, 'collectives::tag_arg(messageTag(group, destination, sendTag, true)));',
                    'collectives::tag_arg(messageTag(group, destination, sendTag, true)));\n    }();', 'send end')
        body = once(body, '    auto const incoming = collectives::get<Message>(',
                    '    auto const incoming = [&]\n    {\n        FrpScope const receive(FRP_RECV_WAIT);\n        return collectives::get<Message>(', 'receive start')
        body = once(body, '                              .get();',
                    '                              .get();\n    }();', 'receive end')
        body = once(body, '    sent.get();',
                    '    {\n        FrpScope const completion(FRP_SEND_WAIT);\n        sent.get();\n    }', 'send completion')
        return body
    text = edit_function(text, r'^extern "C" void FFTW_HPX_COMM_FN\(sendrecv\)\([^{};]*\ntry\n\{', exchange)
    for name,metric in [('send','FRP_SEPARATE_SEND'),('recv','FRP_SEPARATE_RECV')]:
        text = prepend_scope(text, r'^extern "C" void FFTW_HPX_COMM_FN\('+name+r'\)\([^{};]*\ntry\n\{',
                             'FrpScope const profile('+metric+');')
    return text


def threads_edit(text):
    text = once(text, '#include "api/api.h"\n', '#include "api/api.h"\n#include "../benchmarks/remaining_profile.h"\n', 'threads include')
    text = once(text, '     struct worker *q; /* the worker responsible for performing this work */',
                '     FrpToken queued;\n     struct worker *q; /* the worker responsible for performing this work */', 'queued field')
    text = once(text, '          w->proc(&w->d);',
                '          {\n               FrpToken const task = frp_task_begin();\n'
                '               frp_end(w->queued);\n               w->proc(&w->d);\n               frp_task_end(task);\n          }', 'pthread task')
    text = once(text, '     else {\n          struct work *r;\n',
                '     else {\n          FrpToken const jobs = frp_begin(FRP_RUN_JOBS, 0);\n'
                '          struct work *r;\n          frp_jobs_enter();\n', 'pthread envelope')
    text = once(text, '                    proc(d);',
                '                    {\n                         FrpToken const inline_work = frp_begin(FRP_INLINE_WORK, 0);\n'
                '                         FrpToken const task = frp_task_begin();\n                         proc(d);\n'
                '                         frp_task_end(task);\n                         frp_end(inline_work);\n                    }', 'pthread inline')
    text = once(text, '                    w->q = dequeue();',
                '                    FrpToken const enqueue = frp_begin(FRP_ENQUEUE, 0);\n                    w->q = dequeue();', 'pthread enqueue')
    text = once(text, '                    os_sem_up(&w->q->ready);',
                '                    w->queued = frp_begin(FRP_QUEUE_DELAY, 0);\n                    os_sem_up(&w->q->ready);\n                    frp_end(enqueue);', 'pthread signal')
    text = once(text, '          for (i = 0; i < nthr - 1; ++i) {\n',
                '          {\n          FrpToken const join = frp_begin(FRP_JOIN, 0);\n          for (i = 0; i < nthr - 1; ++i) {\n', 'pthread join start')
    text = once(text, '          STACK_FREE(r);',
                '          frp_end(join);\n          }\n          STACK_FREE(r);\n          frp_jobs_leave();\n          frp_end(jobs);', 'pthread join end')
    return text


def pairwise_edit(text, name):
    include = '#include "'+name+'-transpose.h"\n'
    text = once(text, include, include+'#include "../benchmarks/remaining_profile.h"\n', 'pairwise include')
    if text.count('memcpy(') != 2 or text.count('memmove(') != 1:
        raise ValueError('Unexpected pairwise copy count')
    text = text.replace('memcpy(', 'frp_memcpy(').replace('memmove(', 'frp_memmove(')
    def chunks(body):
        body = '\n     FrpToken const chunks = frp_begin(FRP_PAIRWISE_CHUNKS, 0);\n'+body+'\n     frp_end(chunks);\n'
        body = once(body, 'R *buf = (R*) MALLOC(sizeof(R) * sbs[0], BUFFERS);',
                    'FrpToken const allocation = frp_begin(FRP_PAIRWISE_ALLOCATE, sizeof(R) * sbs[0]);\n'
                    '               R *buf = (R*) MALLOC(sizeof(R) * sbs[0], BUFFERS);\n               frp_end(allocation);', 'pairwise allocation')
        body = once(body, 'X(ifree)(buf);',
                    '{\n               FrpToken const release = frp_begin(FRP_PAIRWISE_FREE, 0);\n'
                    '               X(ifree)(buf);\n               frp_end(release);\n               }', 'pairwise free')
        return body
    text = edit_function(text, r'^static void transpose_chunks\([^{};]*\n\{', chunks)
    def children(body):
        pattern = r'\bcld[123](?:rest)?->apply\([^;]*\);'
        def replace(match):
            return '{\n          FrpToken const child = frp_begin(FRP_LOCAL_TRANSPOSE, 0);\n          '+match.group(0)+'\n          frp_end(child);\n          }'
        body, count = re.subn(pattern, replace, body)
        if count != 4: raise ValueError('Unexpected local child apply count: '+str(count))
        return body
    return edit_function(text, r'^static void apply\([^{};]*\n\{', children)


def driver_edit(text):
    text = once(text, '\nnamespace\n{\n', '\n#include "remaining_profile.h"\n\nnamespace\n{\n', 'driver include')
    # Arm every rank before the existing barrier so early receives are counted.
    text = once(text, '    for (int sample = 0; sample < options.samples; ++sample)\n    {\n        backend.barrier();',
                '    for (int sample = 0; sample < options.samples; ++sample)\n    {\n        frp_reset();\n        backend.barrier();', 'sample reset')
    text = once(text, '        auto const begin = Clock::now();',
                '        frp_sample_begin();\n        auto const begin = Clock::now();', 'sample begin')
    line='        double const localElapsed = std::chrono::duration<double>(Clock::now() - begin).count();'
    text = once(text, line, line+'\n        frp_sample_end(localElapsed);', 'sample end')
    text = once(text, '        double const elapsed = backend.maximum(localElapsed);',
                '        double const elapsed = backend.maximum(localElapsed);\n        frp_report(Backend::name, backend.rank, sample);', 'sample report')
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--threads',action='store_true')
    parser.add_argument('--pairwise',action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    if (source/'.git').exists(): raise ValueError('Refusing a Git working tree')
    edits={'hpx/hpx-comm.cpp':bridge_edit,'benchmarks/matched_3d.cpp':driver_edit}
    if args.threads: edits['threads/threads.c']=threads_edit
    if args.pairwise:
        edits['hpx/transpose-pairwise.c']=lambda text:pairwise_edit(text,'hpx')
        edits['mpi/transpose-pairwise.c']=lambda text:pairwise_edit(text,'mpi')
    changes={}
    manifest={'diagnostic_only':True,'source':str(source),'threads':args.threads,'pairwise':args.pairwise,'files':{}}
    for name,transform in edits.items():
        path=source/name
        if path.is_symlink() or path.resolve().is_relative_to(source) is False or path.stat().st_nlink!=1:
            raise ValueError('Refusing linked source '+str(path))
        before=path.read_text()
        if MARKER in before: raise ValueError('Already instrumented '+name)
        if name=='hpx/hpx-comm.cpp' and hashlib.sha256(path.read_bytes()).hexdigest()!='57945a07f87200293e8967c7dd5aed81b869f5e1b257692f297dbac99f62634c':
            raise ValueError('Expected the frozen pooled bridge')
        after='/* '+MARKER+': temporary snapshot only. */\n'+transform(before)
        changes[path]=after
        manifest['files'][name]={'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':hashlib.sha256(after.encode()).hexdigest()}
    here=Path(__file__).resolve().parent
    for name in ('remaining_profile.h','remaining_profile.cpp','remaining_mpi_profile.cpp'):
        destination=source/'benchmarks'/name
        if destination.exists(): raise ValueError('Generated profile file already exists: '+str(destination))
        changes[destination]=(here/name).read_text()
        manifest['files']['benchmarks/'+name]={'generated_sha256':hashlib.sha256(changes[destination].encode()).hexdigest()}
    for path,value in changes.items(): path.write_text(value)
    (source/'remaining_profile_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__': main()
