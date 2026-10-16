"""Atomic immutable JSONL releases of independently replayed dataset revisions.

A manifest is an integrity commitment, not a publisher signature or legal license
assessment. Releases contain only the selected revision and records, not hidden
training data or arbitrary filesystem assets. Symlinks and extra files fail closed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import tempfile

from ..core.semantic_contracts import canonical_payload, load_json, require_digest, require_fields
from ..core.semantic_ir import fingerprint
from .revision_store import DatasetLedger, DatasetRevision, MAX_MEMBERS, MAX_RECORD_BYTES, _record

MAX_RELEASE_BYTES=64*1024*1024
MAX_LINE_BYTES=MAX_RECORD_BYTES+1


def _regular(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular release file required')
    return path


def _read(path,limit):
    path=_regular(path)
    with path.open('rb') as stream:
        raw=stream.read(limit+1)
    if len(raw)>limit:
        raise ValueError('Release file byte budget exceeded')
    return raw


def _hash_file(path,limit):
    digest=hashlib.sha256()
    count=0
    with _regular(path).open('rb') as stream:
        while True:
            chunk=stream.read(65536)
            if not chunk:
                break
            count+=len(chunk)
            if count>limit:
                raise ValueError('Release byte budget exceeded')
            digest.update(chunk)
    return digest.hexdigest(),count


def export_revision(ledger,destination,*,expected_head,revision_id=None):
    if not isinstance(ledger,DatasetLedger):
        raise ValueError('DatasetLedger required')
    require_digest(expected_head)
    selected=expected_head if revision_id is None else require_digest(revision_id)
    revision,records=ledger.snapshot(selected,expected_head=expected_head)
    destination=Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.nabla-release-',dir=destination.parent))
    try:
        count=0
        digest=hashlib.sha256()
        with (staging/'records.jsonl').open('xb') as stream:
            for record in records:
                line=(canonical_payload(record.to_data())+'\n').encode()
                count+=len(line)
                if count>MAX_RELEASE_BYTES:
                    raise ValueError('Release total bytes exceeded')
                stream.write(line)
                digest.update(line)
            stream.flush()
            os.fsync(stream.fileno())
        manifest={'schema_version':1,'revision':revision.to_data(),
            'revision_id':revision.content_id,'record_ids':[r.content_id for r in records],
            'records_sha256':digest.hexdigest(),'records_bytes':count,
            'record_count':len(records),'scope':'exact local dataset revision; publisher and rights unverified'}
        manifest={**manifest,'release_id':fingerprint(manifest)}
        (staging/'manifest.json').write_text(canonical_payload(manifest)+'\n',encoding='utf-8')
        verify_release(staging,expected_revision=selected,expected_release=manifest['release_id'])
        # A nonempty existing directory cannot be overwritten by rename. Creating
        # a sentinel first avoids replacing a concurrently created empty directory.
        destination.mkdir(exist_ok=False)
        try:
            os.rename(staging,destination/'content')
        except BaseException:
            # Remove only the empty directory this call created; never erase a
            # third party's files added concurrently to that directory.
            try:
                destination.rmdir()
            except OSError:
                pass
            raise
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify_release(directory,*,expected_revision,expected_release=None):
    require_digest(expected_revision)
    if expected_release is not None:
        require_digest(expected_release)
    root=Path(directory)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular release directory required')
    # Exported destinations have a wrapper so atomic publication cannot overwrite
    # an unrelated empty destination. Verification also accepts a private stage.
    names={p.name for p in root.iterdir()}
    if names=={'content'}:
        root=root/'content'
        if root.is_symlink() or not root.is_dir():
            raise ValueError('Invalid release content directory')
        names={p.name for p in root.iterdir()}
    if names!={'manifest.json','records.jsonl'}:
        raise ValueError('Missing or unexpected release files')
    raw=_read(root/'manifest.json',1_000_000)
    manifest=load_json(raw.decode('utf-8'))
    require_fields(manifest,{'schema_version','revision','revision_id','record_ids',
                            'records_sha256','records_bytes','record_count','scope','release_id'})
    if type(manifest['schema_version']) is not int or manifest['schema_version']!=1:
        raise ValueError('Unsupported release version')
    if manifest['scope']!='exact local dataset revision; publisher and rights unverified':
        raise ValueError('Release assurance scope differs')
    revision=DatasetRevision(canonical_payload(manifest['revision']))
    if revision.content_id!=manifest['revision_id'] or revision.content_id!=expected_revision:
        raise ValueError('Dataset revision commitment mismatch')
    identifier=fingerprint({key:value for key,value in manifest.items() if key!='release_id'})
    if manifest['release_id']!=identifier or expected_release is not None and identifier!=expected_release:
        raise ValueError('Release content commitment mismatch')
    if (type(manifest['record_count']) is not int or not 0<=manifest['record_count']<=MAX_MEMBERS
        or manifest['record_ids']!=revision.to_data()['members']
        or len(manifest['record_ids'])!=manifest['record_count']):
        raise ValueError('Release membership/count mismatch')
    if type(manifest['records_bytes']) is not int or not 0<=manifest['records_bytes']<=MAX_RELEASE_BYTES:
        raise ValueError('Invalid release byte declaration')
    actual_hash,actual_bytes=_hash_file(root/'records.jsonl',MAX_RELEASE_BYTES)
    if actual_hash!=manifest['records_sha256'] or actual_bytes!=manifest['records_bytes']:
        raise ValueError('Release records changed')
    identifiers=[]
    with _regular(root/'records.jsonl').open('rb') as stream:
        while True:
            line=stream.readline(MAX_LINE_BYTES+1)
            if not line:
                break
            if len(line)>MAX_LINE_BYTES or not line.endswith(b'\n') or len(identifiers)>=MAX_MEMBERS:
                raise ValueError('Malformed/oversized release JSONL record')
            record,canonical=_record(line[:-1].decode('utf-8'))
            if line!=(canonical+'\n').encode():
                raise ValueError('Noncanonical release record')
            identifiers.append(record.content_id)
    if identifiers!=manifest['record_ids']:
        raise ValueError('Semantic record replay differs from release membership')
    return manifest
