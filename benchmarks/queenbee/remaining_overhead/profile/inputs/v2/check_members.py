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


import hashlib
import json
from pathlib import Path
import subprocess
import sys

def members(path):
    names=subprocess.check_output(['ar','t',str(path)],text=True).splitlines()
    assert len(names)==len(set(names))
    return {name:hashlib.sha256(subprocess.check_output(['ar','p',str(path),name])).hexdigest() for name in names}
hpx,mpi,threads,root=map(Path,sys.argv[1:])
thread_names=[name for name in members(threads) if name=="threads.o" or name.endswith("_la-threads.o")]
assert len(thread_names)==1,thread_names
result={}
for label,base,path,expected in [
 ('pool_release',hpx,root/'pool_release/libfftw3_hpx.a',{'hpx-comm.o'}),
 ('hpx_profile',hpx,root/'hpx_profile/libfftw3_hpx.a',{'hpx-comm.o','transpose-pairwise.o'}),
 ('mpi_profile',mpi,root/'mpi_profile/libfftw3_mpi.a',{'transpose-pairwise.o'}),
 ('threads_profile',threads,root/'threads_profile/libfftw3_threads.a',set(thread_names))]:
    before,after=members(base),members(path)
    assert before.keys()==after.keys()
    changed={key for key in before if before[key]!=after[key]}
    assert changed==expected,(label,changed,expected)
    result[label]={'changed':sorted(changed),'unchanged':len(before)-len(changed),'before':before,'after':after}
print(json.dumps(result,indent=2))
