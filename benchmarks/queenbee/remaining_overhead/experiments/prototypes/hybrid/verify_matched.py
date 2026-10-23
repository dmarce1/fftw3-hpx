#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
# This program is free software under GNU GPL version 2 or any later version;
# it comes without warranty. See the repository COPYING file.
from pathlib import Path
import json,math,statistics,sys
text=Path(sys.argv[1]).read_text()
def rows(prefix):
    return [dict(part.split('=',1) for part in line.split()[1:]) for line in text.splitlines() if line.startswith(prefix+' ')]
cfg,=rows('CONFIG');result,=rows('RESULT');samples=rows('SAMPLE');checks=rows('CHECK')
assert all(cfg[key]==value for key,value in dict(backend='hpx',extent='256',ranks='2',threads='2',warmups='2',samples='7',planner='FFTW_ESTIMATE').items())
assert result['status']=='PASS'
assert [int(item['index']) for item in samples]==list(range(7))
assert {item['stage'] for item in checks}=={'forward_spectrum','initial_roundtrip','final_roundtrip'} and len(checks)==3
assert all(math.isfinite(float(item['relative_max_error'])) and 0<=float(item['relative_max_error'])<=1e-10 for item in checks)
values=[float(item['max_rank_seconds']) for item in samples]
assert all(math.isfinite(value) and value>0 for value in values)
for key,value in dict(min_seconds=min(values),median_seconds=statistics.median(values),mean_seconds=statistics.mean(values),max_seconds=max(values)).items():
    assert math.isclose(float(result[key]),value,rel_tol=1e-13)
print(json.dumps(dict(configuration=cfg,checks=checks,result=result,scope='local correctness only'),indent=2))
