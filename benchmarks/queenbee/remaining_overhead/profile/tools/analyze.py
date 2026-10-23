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
"""Validate detailed diagnostic logs; output exact rank/sample and critical-rank decompositions."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

METRICS = ('exchange_wall', 'send_initiation_wall', 'receive_wait_wall', 'send_completion_wait_wall', 'receive_memcpy_wall', 'pool_allocate_wall', 'pool_hit', 'pool_miss', 'heap_allocate_wall', 'pool_deallocate_wall', 'pool_keep', 'pool_delete', 'run_jobs_wall', 'enqueue_wall', 'inline_work_wall', 'join_wall', 'task_wall_sum', 'queue_delay_sum', 'task_thread_cpu_observed', 'task_cpu_migration', 'nested_jobs', 'separate_send_wall', 'separate_receive_wall', 'pairwise_chunks_wall', 'pairwise_copy_wall', 'pairwise_allocate_wall', 'pairwise_free_wall', 'local_transpose_children_wall')
MARKER=re.compile(r'(PROFILE_DETAIL_TOTAL|PROFILE_DETAIL|SAMPLE|RESULT|CONFIG|CHECK) (?=\w+=)')

def require(value,message):
    if not value: raise ValueError(message)

def fields(value):
    pairs=[word.split('=',1) for word in value.split()]
    require(all(len(pair)==2 for pair in pairs),'invalid fields')
    require(len(pairs)==len({key for key,value in pairs}),'duplicate fields')
    return dict(pairs)

def close(left,right): return math.isclose(left,right,rel_tol=1e-12,abs_tol=1e-8)

def analyze(path,args):
    text=path.read_text()
    require('REMAINING_PROFILE_INVALID' not in text,'runtime rejected diagnostic scopes')
    profiles,totals,samples,checks={},{},{},{}
    configs,results=[],[]
    for number,line in enumerate(text.splitlines(),1):
        markers=list(MARKER.finditer(line))
        if not markers: continue
        require(len(markers)==1,f'interleaved records at {path}:{number}')
        marker=markers[0]; row=fields(line[marker.end():]); kind=marker.group(1)
        if kind.startswith('PROFILE_DETAIL'):
            rank,sample=int(row['rank']),int(row['sample'])
            require(0<=rank<args.ranks and 0<=sample<args.samples,'unexpected profile rank/sample')
            seconds=float(row['seconds']); require(math.isfinite(seconds) and seconds>=0,'invalid duration')
            if kind=='PROFILE_DETAIL':
                metric=row['metric']; require(metric in METRICS,'unknown metric '+metric)
                key=(rank,sample,metric); require(key not in profiles,'duplicate metric')
                calls,byte_count=int(row['calls']),int(row['bytes'])
                require(calls>=0 and byte_count>=0 and (calls>0 or seconds==byte_count==0),'invalid counters')
                profiles[key]={'calls':calls,'bytes':byte_count,'seconds':seconds,'backend':row['backend']}
            else:
                key=(rank,sample); require(key not in totals,'duplicate total')
                require(int(row['pending_scopes'])==int(row['late_scopes'])==0,'unfinished/late scope invalidates profile')
                cpu=float(row['process_cpu_seconds']); require(math.isfinite(cpu) and cpu>=0,'invalid CPU total')
                totals[key]={'seconds':seconds,'process_cpu_seconds':cpu,'backend':row['backend']}
        elif kind=='SAMPLE':
            key=int(row['index']); require(key not in samples,'duplicate sample')
            value=float(row['max_rank_seconds'])
            require(math.isfinite(value) and value>0,'invalid sample duration')
            samples[key]=(value,row['backend'])
        elif kind=='CHECK':
            require(row['stage'] not in checks,'duplicate check'); checks[row['stage']]=row
        elif kind=='CONFIG': configs.append(row)
        elif kind=='RESULT': results.append(row)
    require(len(configs)==len(results)==1,'expected one CONFIG/RESULT')
    config,result=configs[0],results[0]; backend=config['backend']
    require(backend in ('mpi','hpx') and result['backend']==backend and result['status']=='PASS','benchmark failed')
    for key,value in [('ranks',args.ranks),('samples',args.samples),('threads',args.threads),('extent',args.extent)]:
        require(int(config[key])==int(result[key])==value,'configuration mismatch '+key)
    require(config['precision']=='double' and config['planner']=='FFTW_ESTIMATE' and config['inplace']=='1','workload mismatch')
    require(config['layout']=='normal' and int(config['warmups'])==args.warmups,'layout/warmup mismatch')
    require(int(config['global_data_bytes'])==args.extent**3*16,'global data size mismatch')
    require(set(checks)=={'forward_spectrum','initial_roundtrip','final_roundtrip'},'missing correctness check')
    for row in checks.values():
        error=float(row['relative_max_error']); tolerance=float(row['tolerance'])
        require(row['backend']==backend,'check backend mismatch')
        require(math.isfinite(error) and 0<=error<=tolerance==1e-10,'numerical failure')
    require(set(profiles)=={(r,s,m) for r in range(args.ranks) for s in range(args.samples) for m in METRICS},'incomplete profile matrix')
    require(set(totals)=={(r,s) for r in range(args.ranks) for s in range(args.samples)},'incomplete totals')
    require(set(samples)==set(range(args.samples)),'incomplete samples')
    require(all(value[1]==backend for value in samples.values()),'sample backend mismatch')
    samples={key:value[0] for key,value in samples.items()}
    require(all(row['backend']==backend for row in list(profiles.values())+list(totals.values())),'backend mismatch')
    values=[samples[s] for s in range(args.samples)]
    for key,value in [('min_seconds',min(values)),('median_seconds',statistics.median(values)),('mean_seconds',statistics.mean(values)),('max_seconds',max(values))]:
        require(close(float(result[key]),value),'sample statistics mismatch')
    rows=[]
    for sample in range(args.samples):
        require(close(samples[sample],max(totals[r,sample]['seconds'] for r in range(args.ranks))),'SAMPLE differs from max rank total')
        for rank in range(args.ranks):
            m={name:profiles[rank,sample,name] for name in METRICS}
            seconds=lambda name:m[name]['seconds']
            require(m['nested_jobs']['calls']==0,'nested job envelopes invalidate disjoint residual and task CPU attribution')
            require(m['separate_send_wall']['calls']==m['separate_receive_wall']['calls']==0,'separate send/recv invalidates residual')
            residual=totals[rank,sample]['seconds']-sum(seconds(name) for name in ('run_jobs_wall','exchange_wall','pairwise_copy_wall','pairwise_allocate_wall','pairwise_free_wall'))
            require(residual>=-1e-6,'negative disjoint residual')
            job_rest=seconds('run_jobs_wall')-sum(seconds(name) for name in ('enqueue_wall','inline_work_wall','join_wall'))
            require(job_rest>=-1e-6,'negative job envelope remainder')
            require(totals[rank,sample]['seconds']>0,'zero rank duration')
            row={'rank':rank,'sample':sample,**totals[rank,sample],'metrics':m,
                 'residual_seconds':residual,'run_jobs_remainder_seconds':job_rest,
                 'average_process_cpu_cores':totals[rank,sample]['process_cpu_seconds']/totals[rank,sample]['seconds'],
                 'task_cpu_valid_for_audited_nonyielding_callback':m['task_cpu_migration']['calls']==0}
            if backend=='hpx':
                rest=seconds('exchange_wall')-sum(seconds(name) for name in ('send_initiation_wall','receive_wait_wall','send_completion_wait_wall','receive_memcpy_wall'))
                require(rest>=-1e-6,'negative exchange remainder')
                row['exchange_remainder_seconds']=rest
                hits,misses=m['pool_hit']['calls'],m['pool_miss']['calls']
                row['pool_hit_fraction']=hits/(hits+misses) if hits+misses else None
                row['receive_copy_gib_per_second']=m['receive_memcpy_wall']['bytes']/2**30/seconds('receive_memcpy_wall') if seconds('receive_memcpy_wall') else None
            rows.append(row)
    critical=[max((row for row in rows if row['sample']==sample),key=lambda row:row['seconds']) for sample in range(args.samples)]
    plans={}
    for direction in ('FORWARD','BACKWARD'):
        values=re.findall(r'PLAN_'+direction+r'_BEGIN\n(.*?)\nPLAN_'+direction+r'_END',text,re.S)
        require(len(values)==1,'missing plan')
        plans[direction.lower()]=hashlib.sha256(values[0].replace('hpx-','mpi-').encode()).hexdigest()
    medians={name:statistics.median(row['metrics'][name]['seconds'] for row in critical) for name in METRICS}
    medians.update({name:statistics.median(row[name] for row in critical) for name in ('seconds','process_cpu_seconds','residual_seconds','run_jobs_remainder_seconds')})
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'PASS',
            'configuration':config,'checks':checks,'normalized_plan_sha256':plans,
            'rank_samples':rows,'critical_rank_samples':critical,'critical_rank_medians':medians}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs',nargs='+',type=Path)
    parser.add_argument('--ranks',type=int,default=4)
    parser.add_argument('--samples',type=int,default=7)
    parser.add_argument('--threads',type=int,default=64)
    parser.add_argument('--extent',type=int,default=1024)
    parser.add_argument('--warmups',type=int,default=2)
    parser.add_argument('--json',type=Path,required=True)
    args=parser.parse_args(); runs=[analyze(path,args) for path in args.logs]
    require(all(run['normalized_plan_sha256']==runs[0]['normalized_plan_sha256'] for run in runs),'plans differ across supplied logs')
    report={'diagnostic_only':True,'status':'PASS','all_normalized_plans_equal':True,'runs':runs,
            'notes':['Task/queue/pool/local-child durations overlap other scopes and must not be added to disjoint wall totals.',
                     'Thread CPU observations require this audited nonyielding FFTW callback plan, no nested jobs and no OS-thread migration; full-process CPU remains valid across HPX waits.',
                     'Residual excludes disjoint run_jobs/exchange/pairwise-copy/allocation/free scopes; it includes serial FFT work, uninstrumented transpose work and diagnostic overhead.',
                     'Critical-rank components come from each sample\'s actual slowest rank. Independently computed component medians need not sum to median total.',
                     'Diagnostic timings must be compared with unchanged uninstrumented controls; they do not replace primary performance results.']}
    args.json.write_text(json.dumps(report,indent=2)+'\n')
    for run in runs: print(run['path'],json.dumps(run['critical_rank_medians'],sort_keys=True))
if __name__=='__main__': main()
