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
"""Restore losslessly encoded synthetic fixtures; no tests or benchmarks run."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
args=parser.parse_args()
root=Path(__file__).resolve().parent
args.output.mkdir(parents=True,exist_ok=True)
if any(args.output.iterdir()):
    raise ValueError('Output directory must be empty')
manifest=json.loads((root/'fixtures/FIXTURES.json').read_text())
for name in manifest['base_logs']:
    shutil.copyfile(str(root/'fixtures'/name),str(args.output/name))
for item in manifest['fixtures']:
    destination=args.output/item['fixture']
    if item['storage']=='raw':
        shutil.copyfile(str(root/item['path']),str(destination))
    else:
        subprocess.check_call(['patch','--batch','--silent','--output',str(destination),str(root/item['base']),'--input',str(root/item['path'])])
    data=destination.read_bytes()
    if hashlib.sha256(data).hexdigest()!=item['sha256'] or len(data)!=item['bytes']:
        raise ValueError('Fixture reconstruction mismatch: '+item['fixture'])
print('Reconstructed %d fixtures; every original SHA256 matches.' % len(manifest['fixtures']))
