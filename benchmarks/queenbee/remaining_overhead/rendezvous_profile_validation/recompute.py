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
"""Recompute compact evidence from preserved raw logs without running any FFTs."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

root=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('frozen_profile_analyzer',root/'tools/analyze.py')
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

def compact(reports):
    runs=[]
    for directory,report in reports:
        mpi,hpx=report
        if mpi['normalized_plan_sha256']!=hpx['normalized_plan_sha256']:
            raise ValueError('Plans differ')
        for left,right in zip(mpi['rank_samples'],hpx['rank_samples']):
            if (left['rank'],left['sample'])!=(right['rank'],right['sample']):
                raise ValueError('Rank/sample order differs')
            for metric in ('run_jobs_wall','task_wall_sum'):
                if left['metrics'][metric]['calls']!=right['metrics'][metric]['calls']:
                    raise ValueError('MPI/HPX callback counts differ')
        raw=root/'raw'/directory
        sources=[path for path in sorted(raw.rglob('*.log')) if path.name.startswith('benchmark_') or path.parent.name.endswith('_rank_logs')]
        runs.append({'directory':directory,'configuration':hpx['configuration'],'status':'PASS','numerical_checks':6,'samples_each_backend':len(hpx['critical_rank_samples']),'normalized_plan_sha256':hpx['normalized_plan_sha256'],'mpi_rank_samples':len(mpi['rank_samples']),'hpx_rank_samples':len(hpx['rank_samples']),'phase_coverage_error_nanoseconds':sorted(set(row['exchange_phase_coverage_error_nanoseconds'] for row in hpx['rank_samples'])),'message_load_counts':{name:sum(row['metrics'][name]['calls'] for row in hpx['rank_samples']) for name in ('message_load','direct_message_load','owned_message_load','empty_message_load','required_posted_message_load')},'final_receive_copy_bytes':sum(row['metrics']['receive_memcpy_wall']['bytes'] for row in hpx['rank_samples']),'callback_calls_match_every_rank_sample':True,'callback_call_counts_per_rank_sample':{name:sorted(set(row['metrics'][name]['calls'] for row in hpx['rank_samples'])) for name in ('run_jobs_wall','task_wall_sum','nested_jobs','task_cpu_migration')},'raw_log_sha256':{str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}})
    return {'license':'GPL-2.0-or-later','status':'PASS','scope':'Local diagnostic correctness and instrumentation validation; not cluster performance evidence.','production_bridge_sha256':hashlib.sha256((root/'source_inputs/hpx/hpx-comm.cpp').read_bytes()).hexdigest(),'diagnostic_bridge_sha256':hashlib.sha256((root/'transformation/hpx-comm.cpp').read_bytes()).hexdigest(),'unchanged_primary_driver_sha256':hashlib.sha256((root/'source_inputs/benchmarks/matched_3d.cpp').read_bytes()).hexdigest(),'runs':runs}

reports=[]
with tempfile.TemporaryDirectory(prefix='fftw_profile_evidence_') as temporary:
    for directory,ranks,threads in [('local_runtime',4,1),('local_threaded',3,2)]:
        args=argparse.Namespace(ranks=ranks,samples=7,threads=threads,extent=64,warmups=2,legacy_mpi_baseline=False)
        runs=[]
        for backend in ('mpi','hpx'):
            raw=root/'raw'/directory
            sources=[raw/('benchmark_'+backend+'.log')]+[raw/(backend+'_rank_logs')/(backend+'-'+str(rank)+'.log') for rank in range(ranks)]
            merged=Path(temporary)/(directory+'_'+backend+'.log')
            merged.write_bytes(b'\n'.join(path.read_bytes() for path in sources))
            runs.append(a.analyze(merged,args))
        reports.append((directory,runs))
print(json.dumps(compact(reports),indent=2))
