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
"""Synthetic parser checks only; these are not runtime or benchmark evidence."""
import argparse
import importlib.util
from pathlib import Path
import re

base=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('profile_analyzer',base/'analyze.py')
a=importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
out=base/'analyzer_check'
out.mkdir(exist_ok=True)
args=argparse.Namespace(ranks=4,samples=7,threads=64,extent=1024,warmups=2,legacy_mpi_baseline=False)
root=base.parents[2]
runs=[]
for backend,name in [('mpi','mpi'),('hpx','pooled_receive')]:
    original=(root/'benchmarks/queenbee/optimization/1125688'/('benchmark_'+name+'.log')).read_text()
    extra=[]
    for sample,elapsed in re.findall(r'SAMPLE backend=\w+ index=(\d+) max_rank_seconds=(\S+)',original):
        for rank in range(4):
            duration=float(elapsed)*(1-(3-rank)*0.01)
            values={metric:[0,0,0.] for metric in a.METRICS}
            def setval(name,calls,seconds=0,bytes=0): values[name]=[calls,bytes,seconds]
            setval('run_jobs_wall',3,duration*.3)
            setval('enqueue_wall',3,duration*.02)
            setval('inline_work_wall',3,duration*.12)
            setval('join_wall',3,duration*.14)
            setval('exchange_wall',6,duration*.4,6*2**30)
            setval('pairwise_copy_wall',4,duration*.1,4*2**30)
            setval('pairwise_allocate_wall',2,duration*.01,2*2**30)
            setval('pairwise_free_wall',2,duration*.01)
            setval('task_wall_sum',192,duration*15)
            setval('task_thread_cpu_observed',192,duration*14)
            setval('queue_delay_sum',189,duration*.4)
            setval('pairwise_chunks_wall',2,duration*.55)
            setval('local_transpose_children_wall',6,duration*.4)
            if backend=='hpx':
                setval('send_initiation_wall',6,duration*.01)
                setval('receive_wait_wall',6,duration*.18)
                setval('send_completion_wait_wall',6,duration*.01)
                setval('receive_memcpy_wall',6,duration*.17,6*2**30)
                setval('pool_allocate_wall',6,duration*.001,6*2**30)
                setval('pool_hit',6,bytes=6*2**30)
                setval('pool_deallocate_wall',6,duration*.001,6*2**30)
                setval('pool_keep',6,bytes=6*2**30)
                setval('post_announce_initiation_wall',6,duration*.005)
                setval('readiness_phase_wall',6,duration*.01)
                setval('receive_finish_wall',6,duration*.18)
                setval('announce_completion_wait_wall',6,duration*.002)
                setval('exchange_rest_wall',12,duration*.003)
                setval('message_load',6,bytes=6*2**30)
                setval('direct_message_load',4,bytes=4*2**30)
                setval('owned_message_load',2,bytes=2*2**30)
                setval('required_posted_message_load',4,bytes=4*2**30)
            ns_values={metric:round(value[2]*1e9) for metric,value in values.items()}
            if backend=='hpx':
                ns_values['exchange_wall']=sum(ns_values[metric] for metric in a.EXCHANGE_PHASES)
            for metric,(calls,bytes,seconds) in values.items():
                extra.append(f'PROFILE_DETAIL backend={backend} rank={rank} sample={sample} metric={metric} calls={calls} bytes={bytes} seconds={ns_values[metric]*1e-9:.17g} nanoseconds={ns_values[metric]}')
            extra.append(f'PROFILE_DETAIL_TOTAL backend={backend} rank={rank} sample={sample} seconds={duration:.17g} process_cpu_seconds={duration*20:.17g} pending_scopes=0 late_scopes=0')
    path=out/('SYNTHETIC_'+backend+'.log')
    data='SYNTHETIC PARSER FIXTURE: NOT MEASURED DIAGNOSTIC DATA\n'+original+'\n'+'\n'.join(extra)+'\n'
    path.write_text(data)
    run=a.analyze(path,args)
    assert len(run['rank_samples'])==28
    assert len(run['critical_rank_samples'])==7
    assert all(row['rank']==3 for row in run['critical_rank_samples'])
    runs.append(run)
    cases={
        'missing_metric':re.sub(r'^PROFILE_DETAIL .*metric=pool_hit .*\n','',data,count=1,flags=re.M),
        'pending_scope':data.replace('pending_scopes=0','pending_scopes=1',1),
        'late_scope':data.replace('late_scopes=0','late_scopes=1',1),
        'duplicate_metric':data+'\n'+extra[0]+'\n',
        'wrong_sample_backend':data.replace('SAMPLE backend='+backend,'SAMPLE backend=wrong',1),
        'negative_residual':data.replace('metric=run_jobs_wall calls=3', 'metric=run_jobs_wall calls=3',1),
        'nested_jobs':data.replace('metric=nested_jobs calls=0','metric=nested_jobs calls=1',1),
        'separate_send':data.replace('metric=separate_send_wall calls=0','metric=separate_send_wall calls=1',1),
        'bad_workload':data.replace('warmups=2','warmups=3',1),
        'invalid_runtime':'REMAINING_PROFILE_INVALID test\n'+data,
        'interleaved':data.replace(extra[0],extra[0]+' '+extra[1],1),
        'negative_duration':data.replace('metric=pool_hit calls=6 bytes=6442450944 seconds=0','metric=pool_hit calls=6 bytes=6442450944 seconds=-1',1) if backend=='hpx' else data.replace('metric=pool_hit calls=0 bytes=0 seconds=0','metric=pool_hit calls=0 bytes=0 seconds=-1',1),
    }
    cases['negative_residual']=re.sub(r'(metric=run_jobs_wall calls=3 bytes=0 seconds=)\S+',r'\g<1>1000',data,count=1)
    if backend=='hpx':
        cases['phase_coverage']=re.sub(r'(metric=exchange_rest_wall calls=12 bytes=0 seconds=)\S+ nanoseconds=\d+',r'\g<1>0 nanoseconds=0',data,count=1)
        cases['phase_one_ns']=re.sub(r'(metric=exchange_rest_wall calls=12 bytes=0 seconds=)(\S+) nanoseconds=(\d+)',lambda match:match.group(1)+format((int(match.group(3))+1)*1e-9,'.17g')+' nanoseconds='+str(int(match.group(3))+1),data,count=1)
        cases['phase_calls']=data.replace('metric=readiness_phase_wall calls=6','metric=readiness_phase_wall calls=5',1)
        cases['load_partition']=data.replace('metric=direct_message_load calls=4','metric=direct_message_load calls=3',1)
        cases['required_target']=data.replace('metric=required_posted_message_load calls=4','metric=required_posted_message_load calls=5',1)
        cases['no_exact_ns']=re.sub(r' nanoseconds=\d+','',data)
    for case,invalid in cases.items():
        target=out/('INVALID_'+backend+'_'+case+'.log')
        target.write_text(invalid)
        try: a.analyze(target,args)
        except ValueError: pass
        else: raise RuntimeError('accepted invalid fixture: '+str(target))
    print(backend,'PASS positive=1 negative='+str(len(cases)))
legacy=(out/'SYNTHETIC_mpi.log').read_text()
legacy='\n'.join(line for line in legacy.splitlines() if not any('metric='+metric+' ' in line for metric in a.EXTRA_METRICS))+'\n'
legacy=re.sub(r' nanoseconds=\d+','',legacy)
legacy_path=out/'SYNTHETIC_legacy_mpi.log'
legacy_path.write_text(legacy)
try: a.analyze(legacy_path,args)
except ValueError: pass
else: raise RuntimeError('legacy MPI accepted without explicit permission')
args.legacy_mpi_baseline=True
assert a.analyze(legacy_path,args)['metric_schema']=='legacy_mpi_baseline_no_readiness'
assert runs[0]['normalized_plan_sha256']==runs[1]['normalized_plan_sha256']
print('ANALYZER_SYNTHETIC_CHECK PASS plans_equal=1 measured_diagnostics=0')
