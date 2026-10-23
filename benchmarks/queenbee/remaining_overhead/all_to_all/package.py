#!/usr/bin/env python3
# Copyright (c) 2026 Dominic C. Marcello
# SPDX-License-Identifier: GPL-2.0-or-later
"""Package verified completed evidence. Never access QueenBee or modify old results.

The download archive must contain results/JOB/... plus alltoall-JOB.out/.err.
Binary objects and the full candidate source tree may be omitted from that
archive; their complete remote artifact manifest remains mandatory. Failed or
incomplete jobs are deliberately rejected before any published path is created.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def checksums(path):
    entries = {}
    for line in path.read_text().splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *](.+)', line)
        require(match is not None, 'Malformed checksum line in ' + str(path))
        value, name = match.groups()
        require(name not in entries, 'Duplicate checksum path: ' + name)
        entries[name] = value
    require(entries, 'Empty manifest: ' + str(path))
    return entries


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--job-id', required=True)
parser.add_argument('--extracted-root', required=True, type=Path)
parser.add_argument('--archive', required=True, type=Path)
parser.add_argument('--archive-sha256', required=True)
parser.add_argument('--accounting', required=True, type=Path)
parser.add_argument('--inputs', type=Path)
parser.add_argument('--local-validation', type=Path)
parser.add_argument('--destination', type=Path)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
helper_dir = Path(__file__).resolve().parent
job = args.job_id
require(re.fullmatch(r'[0-9]+', job), 'Expected numeric job id')
require(re.fullmatch(r'[0-9a-f]{64}', args.archive_sha256), 'Expected lowercase SHA256 digest')
require(digest(args.archive) == args.archive_sha256, 'Downloaded archive SHA256 mismatch')
inputs = args.inputs or helper_dir / 'bundle'
local_validation = args.local_validation or helper_dir / 'local'
root = args.extracted_root.resolve()
source = root if root.name == job and (root / 'FINAL_STATUS').is_file() else root / 'results' / job
require(source.is_dir(), 'Missing extracted results directory: ' + str(source))
destination = args.destination or repo / 'benchmarks/queenbee/remaining_overhead/all_to_all'
staging = destination.with_name('.' + destination.name + '_staging')
require(not destination.exists(), 'Preserve existing published evidence: ' + str(destination))
require(not staging.exists(), 'Preserve existing staging evidence: ' + str(staging))
require(local_validation.is_dir(), 'Missing local validation directory')

status = dict(line.split('\t', 1) for line in (source / 'FINAL_STATUS').read_text().splitlines())
require(status.get('status') == 'PASS' and status.get('exit_status') == '0' and
        status.get('stage') == 'complete' and status.get('job_id') == job,
        'Remote job is incomplete or failed; preserve its raw evidence without publishing a successful comparison')
rows = [line.split('\t') for line in (source / 'results.tsv').read_text().splitlines()]
require(rows and all(len(row) >= 3 and row[1] == 'PASS' for row in rows), 'A remote stage failed')
required_stages = {'prior_artifacts', 'source_overlay', 'compile_transpose', 'compile_bridge',
    'replace_objects', 'compile_driver', 'compile_comm_check', 'archive_members',
    'mpi_dependencies', 'dependencies_hpx_candidate', 'dependencies_hpx_comm_check',
    'communication_pairwise', 'communication_all_to_all', 'correctness_gates',
    'alltoall_checks', 'fixed_inputs_unchanged', 'reused_binaries_unchanged',
    'source_overlay_unchanged', 'prior_artifacts_unchanged'}
required_stages.update('small_{}_{}'.format(size, mode) for size in (32, 64) for mode in ('pairwise', 'all_to_all'))
required_stages.update('benchmark_' + label for label in ('mpi_start', 'hpx_pairwise', 'hpx_all_to_all',
    'hpx_all_to_allrepeat', 'hpx_pairwiserepeat', 'mpi_end'))
for name in required_stages:
    require(sum(row[0] == name for row in rows) == 1, 'Missing or duplicate stage: ' + name)
    require((source / (name + '.command')).is_file() and (source / (name + '.log')).is_file(),
            'Missing stage command/log: ' + name)
require((source / 'source_overlay.log').read_bytes() == (source / 'source_overlay_unchanged.log').read_bytes(),
        'Source overlay pre/post evidence differs')
artifact_recheck = (source / 'artifacts_recheck.log').read_text().splitlines()
require(artifact_recheck and all(line.endswith(': OK') for line in artifact_recheck), 'Artifact post-check did not pass')

accounting_text = args.accounting.read_text()
accounting = list(csv.DictReader(io.StringIO(accounting_text), delimiter='|'))
require(accounting and 'JobID' in accounting[0] and 'State' in accounting[0] and 'ExitCode' in accounting[0],
        'Expected pipe-delimited sacct with JobID, State and ExitCode columns')
main_rows = [row for row in accounting if row['JobID'].strip() == job]
require(len(main_rows) == 1 and main_rows[0]['State'].strip() == 'COMPLETED' and
        main_rows[0]['ExitCode'].strip() == '0:0', 'Scheduler accounting does not confirm a successful completed job')
job_rows = [row for row in accounting if row['JobID'].strip() == job or row['JobID'].strip().startswith(job + '.')]
require(all(row['State'].strip() == 'COMPLETED' and row['ExitCode'].strip() == '0:0' for row in job_rows),
        'A job step has a non-success scheduler result')

input_manifest = checksums(inputs / 'SHA256SUMS')
for name, value in input_manifest.items():
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe input manifest path')
    require((inputs / name).is_file() and not (inputs / name).is_symlink(), 'Missing input: ' + name)
    require(digest(inputs / name) == value, 'Changed frozen input: ' + name)
input_files = {str(path.relative_to(inputs)) for path in inputs.rglob('*') if path.is_file() and '__pycache__' not in path.parts}
require(input_files == set(input_manifest) | {'SHA256SUMS'}, 'Unmanifested frozen input file')
for name in ('job.sbatch', 'common.sh', 'PROVENANCE.json'):
    require((source / name).read_bytes() == (inputs / name).read_bytes(), 'Remote job input differs: ' + name)
fixed = checksums(source / 'fixed_inputs.sha256')
remote_bundle_manifest = [value for name, value in fixed.items() if name.endswith('/alltoall/SHA256SUMS')]
require(remote_bundle_manifest == [digest(inputs / 'SHA256SUMS')], 'Remote bundle manifest differs')
provenance = json.loads((inputs / 'PROVENANCE.json').read_text())
source_overlay = json.loads((source / 'source_overlay.log').read_text())
require(source_overlay.get('status') == 'PASS' and source_overlay.get('all_other_sources_unchanged') is True,
        'Source overlay verification missing')
require(source_overlay['overlay'] == provenance['source_hashes'], 'Frozen sources differ from compiled source overlay')
artifacts = checksums(source / 'artifacts.sha256')
for name, value in provenance['source_hashes'].items():
    require(artifacts.get('candidate_source/' + name) == value, 'Compiled source hash mismatch: ' + name)
members = json.loads((source / 'archive_members.log').read_text())
require(members.get('status') == 'PASS' and set(members['resolved']) == {'hpx-comm.o', 'transpose-pairwise.o'},
        'Archive replacements not verified')
require(set(members['changed']) == set(members['resolved'].values()), 'Unexpected changed archive member')
for name in members['changed']:
    require(artifacts.get('objects/' + name) == members['after'][name], 'Loose replacement hash mismatch: ' + name)
summary_bytes = (source / 'alltoall_comparison.json').read_bytes()
summary = json.loads(summary_bytes)
require(summary.get('status') == 'PASS' and summary.get('timed_samples') == 42 and
        summary.get('numerical_checks') == 18 and summary.get('communication_passes') == 8 and
        summary.get('preliminary_correctness_checks') == 12, 'Incomplete comparison summary')

archive = tarfile.open(str(args.archive), 'r:*')
archive_members = {}
for member in archive.getmembers():
    relative = PurePosixPath(member.name)
    require(not relative.is_absolute() and '..' not in relative.parts, 'Unsafe archive path: ' + member.name)
    require(not member.issym() and not member.islnk(), 'Unexpected archive link: ' + member.name)
    if member.isfile():
        normalized = str(relative)
        require(normalized not in archive_members, 'Duplicate archive member: ' + normalized)
        archive_members[normalized] = member


def archive_member(suffix):
    candidates = [name for name in archive_members if name == suffix or name.endswith('/' + suffix)]
    require(len(candidates) == 1, 'Expected one archive member ending in ' + suffix)
    return candidates[0]


excluded_roots = {'bin', 'objects', 'candidate_source'}
raw_files = []
for path in sorted(source.rglob('*')):
    require(not path.is_symlink(), 'Unexpected extracted symlink: ' + str(path))
    if path.is_file() and path.relative_to(source).parts[0] not in excluded_roots:
        relative = path.relative_to(source)
        member_name = archive_member('results/' + job + '/' + relative.as_posix())
        raw_files.append((path, Path('raw') / job / relative, member_name))
excluded_archive_members = []
known_raw_members = {entry[2] for entry in raw_files}
for name, member in archive_members.items():
    marker = 'results/' + job + '/'
    if marker in name:
        relative = PurePosixPath(name.split(marker, 1)[1])
        if relative.parts[0] in excluded_roots:
            manifest_value = artifacts.get(str(relative))
            require(manifest_value is not None, 'Excluded archive file lacks artifact hash: ' + name)
            excluded_archive_members.append(dict(member=name, bytes=member.size, sha256=manifest_value,
                hash_source='raw/' + job + '/artifacts.sha256'))
        else:
            require(name in known_raw_members, 'Archive raw file missing from extraction: ' + name)
companions = []
for suffix in ('out', 'err'):
    name = 'alltoall-' + job + '.' + suffix
    member_name = archive_member(name)
    # The archive is the authoritative source; companions need not be copied
    # separately by a downloader that extracts only results/JOB.
    companions.append((Path('raw') / name, member_name))

copies = []
staging.mkdir(parents=True)


def publish(data, relative, origin, archive_name=None):
    require(len(data) <= 64 * 1024 * 1024, 'Refuse unexpectedly large text file: ' + str(relative))
    data.decode('utf-8')
    require(b'\0' not in data and not data.startswith((b'\x7fELF', b'!<arch>')), 'Refuse binary evidence file: ' + str(relative))
    target = staging / relative
    require(not target.exists(), 'Duplicate publication target: ' + str(relative))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    value = hashlib.sha256(data).hexdigest()
    require(digest(target) == value, 'Copy verification failed')
    entry = dict(source=origin, published=str(relative), sha256=value, bytes=len(data))
    if archive_name:
        entry['archive_member'] = archive_name
    copies.append(entry)


for path, relative, member_name in raw_files:
    data = path.read_bytes()
    remote = archive.extractfile(archive_members[member_name])
    require(remote is not None and data == remote.read(), 'Extracted file differs from transfer archive: ' + str(path))
    publish(data, relative, str(path), member_name)
for relative, member_name in companions:
    stream = archive.extractfile(archive_members[member_name])
    require(stream is not None, 'Missing archive companion')
    publish(stream.read(), relative, str(args.archive) + '::' + member_name, member_name)
archive.close()
for path in sorted(inputs.rglob('*')):
    if path.is_file() and '__pycache__' not in path.parts:
        publish(path.read_bytes(), Path('inputs/alltoall') / path.relative_to(inputs), str(path))
for path in sorted(local_validation.rglob('*')):
    require(not path.is_symlink(), 'Unexpected local validation symlink')
    if path.is_file():
        publish(path.read_bytes(), Path('local_validation') / path.relative_to(local_validation), str(path))
for name in ('HARNESS_VALIDATION.json', 'PACKAGING_VALIDATION.json', 'freeze.json', 'local_validate.sh', 'prepare.py'):
    path = helper_dir / name
    require(path.is_file(), 'Missing local provenance helper: ' + name)
    publish(path.read_bytes(), Path('local_validation') / name, str(path))
publish(args.accounting.read_bytes(), Path('accounting.txt'), str(args.accounting))
publish((helper_dir / 'recompute.py').read_bytes(), Path('recompute.py'), str(helper_dir / 'recompute.py'))
publish(Path(__file__).read_bytes(), Path('package.py'), str(Path(__file__).resolve()))
publish(summary_bytes, Path('SUMMARY.json'), str(source / 'alltoall_comparison.json'))
package = dict(license='GPL-2.0-or-later', job_id=job,
    input_bundle_sha256=next(iter(remote_bundle_manifest)),
    published_content='Raw text evidence, exact frozen inputs, local validation and remote artifact hashes; no binary archives or full FFTW source duplicate',
    remote_status=status, scheduler_parent=main_rows[0],
    accounting_has_MaxRSS='MaxRSS' in main_rows[0],
    local_validation_note='Historical failures and later successful runs are retained as recorded; no aggregate local pass status is inferred')
(staging / 'PACKAGE.json').write_text(json.dumps(package, indent=2) + '\n')
subprocess.check_call([sys.executable, '-I', str(staging / 'recompute.py')], stdout=subprocess.DEVNULL)
(staging / 'SOURCE_MAP.json').write_text(json.dumps(dict(license='GPL-2.0-or-later', job_id=job,
    verified_download=dict(path=str(args.archive.resolve()), sha256=args.archive_sha256),
    excluded_archive_members=excluded_archive_members,
    excluded_remote_paths=dict(prefixes=sorted(excluded_roots), manifest='raw/' + job + '/artifacts.sha256'),
    copies=copies), indent=2) + '\n')
(staging / 'SOURCE_VERIFICATION.json').write_text(json.dumps(dict(status='PASS', job_id=job,
    archive_sha256=args.archive_sha256, copied_files=len(copies),
    archive_verified_raw_files=len(raw_files) + len(companions),
    exact_frozen_source_hashes=provenance['source_hashes'],
    summary_byte_identical=True, preserved_archive_members=members['unchanged']), indent=2) + '\n')
files = sorted(path for path in staging.rglob('*') if path.is_file())
(staging / 'SHA256SUMS').write_text(''.join(digest(path) + '  ' + str(path.relative_to(staging)) + '\n' for path in files))
subprocess.check_call(['sha256sum', '-c', 'SHA256SUMS'], cwd=str(staging), stdout=subprocess.DEVNULL)
staging.rename(destination)
print(json.dumps(dict(status='PASS', destination=str(destination), job_id=job,
    files=len(files) + 1, source_copies=len(copies), summary_byte_identical=True,
    median_seconds=summary['median_seconds'], median_ratios=summary['median_ratios'],
    next_step='Write actual-results documentation and regenerate package plus parent SHA256SUMS before publication'), indent=2))
