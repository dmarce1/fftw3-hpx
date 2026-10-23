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
BASE_METRICS=METRICS
EXTRA_METRICS=('post_announce_initiation_wall', 'readiness_phase_wall', 'receive_finish_wall', 'announce_completion_wait_wall', 'exchange_rest_wall', 'message_load', 'direct_message_load', 'owned_message_load', 'empty_message_load', 'required_posted_message_load')
METRICS=BASE_METRICS+EXTRA_METRICS
EXCHANGE_PHASES=('post_announce_initiation_wall', 'readiness_phase_wall', 'send_initiation_wall', 'receive_wait_wall', 'send_completion_wait_wall', 'receive_finish_wall', 'announce_completion_wait_wall', 'exchange_rest_wall')
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
                if 'nanoseconds' in row:
                    ns=int(row['nanoseconds'])
                    require(ns>=0 and close(ns*1e-9,seconds),'invalid nanosecond counter')
                    profiles[key]['nanoseconds']=ns
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
    schema='rendezvous_partition'
    if backend=='mpi' and getattr(args,'legacy_mpi_baseline',False) and set(profiles)=={(r,s,m) for r in range(args.ranks) for s in range(args.samples) for m in BASE_METRICS}:
        schema='legacy_mpi_baseline_no_readiness'
        for rank in range(args.ranks):
            for sample in range(args.samples):
                for name in EXTRA_METRICS:
                    profiles[rank,sample,name]={'calls':0,'bytes':0,'seconds':0.0,'nanoseconds':0,'backend':'mpi','not_applicable_unmeasured':True}
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
                require(all('nanoseconds' in m[name] for name in EXCHANGE_PHASES+('exchange_wall',)), 'missing exact phase nanoseconds')
                total_ns=m['exchange_wall']['nanoseconds']
                phase_ns=sum(m[name]['nanoseconds'] for name in EXCHANGE_PHASES)
                require(total_ns==phase_ns,'exchange phase coverage differs from inclusive nanoseconds')
                exchanges=m['exchange_wall']['calls']
                require(all(m[name]['calls']==exchanges for name in EXCHANGE_PHASES if name!='exchange_rest_wall'),'phase count differs from exchange calls')
                require(m['exchange_rest_wall']['calls']==2*exchanges,'exchange rest must cover setup and destruction')
                require(seconds('receive_memcpy_wall')<=seconds('receive_finish_wall')+1e-8,'nested memcpy exceeds receive finish phase')
                for field in ('calls','bytes'):
                    require(m['message_load'][field]==sum(m[name][field] for name in ('direct_message_load','owned_message_load','empty_message_load')),'message load partition mismatch '+field)
                    require(m['required_posted_message_load'][field]<=m['direct_message_load'][field],'required target did not load directly')
                row['exchange_phase_seconds']={name:seconds(name) for name in EXCHANGE_PHASES}
                row['exchange_phase_sum_nanoseconds']=phase_ns
                row['exchange_phase_coverage_error_nanoseconds']=phase_ns-total_ns
                row['exchange_remainder_seconds']=seconds('exchange_rest_wall')
                hits,misses=m['pool_hit']['calls'],m['pool_miss']['calls']
                row['pool_hit_fraction']=hits/(hits+misses) if hits+misses else None
                row['receive_copy_gib_per_second']=m['receive_memcpy_wall']['bytes']/2**30/seconds('receive_memcpy_wall') if seconds('receive_memcpy_wall') else None
            rows.append(row)
    critical=[max((row for row in rows if row['sample']==sample),key=lambda row:row['seconds']) for sample in range(args.samples)]
    readiness_max=[]
    if backend=='hpx':
        for sample in range(args.samples):
            maximum=max((row for row in rows if row['sample']==sample),key=lambda row:row['metrics']['readiness_phase_wall']['seconds'])
            readiness_max.append({'sample':sample,'rank':maximum['rank'],'readiness_phase_seconds':maximum['metrics']['readiness_phase_wall']['seconds'],'overall_rank_seconds':maximum['seconds']})
    plans={}
    for direction in ('FORWARD','BACKWARD'):
        values=re.findall(r'PLAN_'+direction+r'_BEGIN\n(.*?)\nPLAN_'+direction+r'_END',text,re.S)
        require(len(values)==1,'missing plan')
        plans[direction.lower()]=hashlib.sha256(values[0].replace('hpx-','mpi-').encode()).hexdigest()
    medians={name:statistics.median(row['metrics'][name]['seconds'] for row in critical) for name in METRICS}
    medians.update({name:statistics.median(row[name] for row in critical) for name in ('seconds','process_cpu_seconds','residual_seconds','run_jobs_remainder_seconds')})
    means={name:statistics.mean(row['metrics'][name]['seconds'] for row in critical) for name in METRICS}
    means.update({name:statistics.mean(row[name] for row in critical) for name in ('seconds','process_cpu_seconds','residual_seconds','run_jobs_remainder_seconds')})
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'PASS',
            'configuration':config,'checks':checks,'normalized_plan_sha256':plans,
            'rank_samples':rows,'critical_rank_samples':critical,'critical_rank_medians':medians,'critical_rank_means':means,'metric_schema':schema,'sample_maximum_readiness_phase':readiness_max}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('logs',nargs='+',type=Path)
    parser.add_argument('--ranks',type=int,default=4)
    parser.add_argument('--samples',type=int,default=7)
    parser.add_argument('--threads',type=int,default=64)
    parser.add_argument('--extent',type=int,default=1024)
    parser.add_argument('--warmups',type=int,default=2)
    parser.add_argument('--legacy-mpi-baseline',action='store_true',help='Explicitly accept a complete old MPI metric schema; appended HPX-only metrics are unmeasured/not applicable zeros.')
    parser.add_argument('--json',type=Path,required=True)
    args=parser.parse_args(); runs=[analyze(path,args) for path in args.logs]
    require(all(run['normalized_plan_sha256']==runs[0]['normalized_plan_sha256'] for run in runs),'plans differ across supplied logs')
    report={'diagnostic_only':True,'status':'PASS','all_normalized_plans_equal':True,'runs':runs,
            'notes':['Task/queue/pool/local-child durations overlap other scopes and must not be added to disjoint wall totals.',
                     'Thread CPU observations require this audited nonyielding FFTW callback plan, no nested jobs and no OS-thread migration; full-process CPU remains valid across HPX waits.',
                     'Residual excludes disjoint run_jobs/exchange/pairwise-copy/allocation/free scopes; it includes serial FFT work, uninstrumented transpose work and diagnostic overhead.',
                     'Rendezvous exchange phases use exact shared nanosecond boundaries; nested memcpy/pool counters are excluded from that sum.',
                     'Readiness phase includes peer-token wait and validation; it cannot distinguish a late peer FFT from transport/progress latency. Incoming receive phase likewise is elapsed wait, not isolated network transfer time.',
                     'Critical-rank components come from each sample\'s actual slowest rank. Independently computed component medians need not sum to median total.',
                     'Diagnostic timings must be compared with unchanged uninstrumented controls; they do not replace primary performance results.']}
    mpi=[run for run in runs if run['configuration']['backend']=='mpi']
    hpx=[run for run in runs if run['configuration']['backend']=='hpx']
    if len(mpi)==len(hpx)==1:
        left,right=mpi[0]['critical_rank_samples'],hpx[0]['critical_rank_samples']
        deltas=[]
        for m,h in zip(left,right):
            require(m['sample']==h['sample'],'sample pairing mismatch')
            row={'sample':m['sample'],'mpi_critical_rank':m['rank'],'hpx_critical_rank':h['rank'],'total_seconds':h['seconds']-m['seconds'],'components_seconds':{name:h['metrics'][name]['seconds']-m['metrics'][name]['seconds'] for name in ('run_jobs_wall','exchange_wall','pairwise_copy_wall','pairwise_allocate_wall','pairwise_free_wall')}}
            row['components_seconds']['residual_seconds']=h['residual_seconds']-m['residual_seconds']
            require(close(sum(row['components_seconds'].values()),row['total_seconds']),'critical-rank delta decomposition mismatch')
            deltas.append(row)
        report['critical_rank_sample_index_deltas_hpx_minus_mpi']=deltas
        report['critical_rank_mean_delta_hpx_minus_mpi']={'total_seconds':statistics.mean(row['total_seconds'] for row in deltas),'components_seconds':{name:statistics.mean(row['components_seconds'][name] for row in deltas) for name in deltas[0]['components_seconds']}}
        report['notes'].append('Cross-run equal sample indices are bookkeeping pairs, not simultaneous or randomized trials. Arithmetic mean component deltas add to the mean total delta; independent medians do not.')
    args.json.write_text(json.dumps(report,indent=2)+'\n')
    for run in runs: print(run['path'],json.dumps(run['critical_rank_medians'],sort_keys=True))
if __name__=='__main__': main()
