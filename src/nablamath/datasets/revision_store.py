"""Content-addressed dataset revisions with CAS admission and semantic replay.

This is a local scientific-record ledger, not authenticated operator consensus.
Caller-supplied licenses and provenance are retained rather than legally verified.
Pinned revision IDs detect content changes; replacing a whole database can only
be detected by a caller retaining a trusted revision commitment externally.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
import sqlite3

from ..core.semantic_contracts import canonical_payload, load_json, require_digest, require_fields, require_text
from ..core.semantic_ir import fingerprint
from .schema import ScientificRecord

MAX_MEMBERS = 4096
MAX_ACTIONS = 256
MAX_REVISIONS = 1024
MAX_RECORD_BYTES = 1_000_000
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def bounded(items, limit, label):
    try:
        values = tuple(islice(iter(items), limit + 1))
    except TypeError as exc:
        raise ValueError(f'{label} must be a finite iterable') from exc
    if len(values) > limit:
        raise ValueError(f'{label} exceeds budget')
    return values


def _record(raw):
    data = load_json(raw)
    try:
        value = ScientificRecord(canonical_payload(data))
    except (KeyError, TypeError, IndexError, AttributeError, ArithmeticError) as exc:
        raise ValueError("Malformed scientific record payload") from exc
    encoded = canonical_payload(value.to_data())
    if len(encoded.encode()) > MAX_RECORD_BYTES:
        raise ValueError('Dataset record exceeds storage byte budget')
    return value, encoded


def _identifiers(values, *, limit, name):
    result = bounded(values, limit, name)
    for value in result:
        require_digest(value)
    if len(set(result)) != len(result):
        raise ValueError('Duplicate '+name)
    return tuple(sorted(result))


@dataclass(frozen=True)
class DatasetRevision:
    manifest_json: str

    def __post_init__(self):
        data = load_json(self.manifest_json)
        require_fields(data, {'schema_version','dataset','parent','actor','reason',
                              'added','removed','members','sequence'})
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise ValueError('Unsupported dataset revision schema')
        require_text(data['dataset'],'dataset',limit=256)
        require_text(data['actor'],'actor',limit=256)
        require_text(data['reason'],'reason')
        if data['parent'] is not None:
            require_digest(data['parent'])
        if type(data['sequence']) is not int or not 1 <= data['sequence'] <= MAX_REVISIONS:
            raise ValueError('Invalid revision sequence')
        if (data['parent'] is None) != (data['sequence'] == 1):
            raise ValueError('Only the first revision omits its parent')
        for name, limit in [('added',MAX_ACTIONS),('removed',MAX_ACTIONS),('members',MAX_MEMBERS)]:
            if not isinstance(data[name],list):
                raise ValueError('Revision identifier arrays must be JSON lists')
            if list(_identifiers(data[name],limit=limit,name=name)) != data[name]:
                raise ValueError('Revision identities must be sorted canonically')
        added, removed, members = map(set, (data['added'],data['removed'],data['members']))
        if not (added or removed) or added & removed or not added <= members or removed & members:
            raise ValueError('Invalid or empty dataset revision transition')
        object.__setattr__(self,'manifest_json',canonical_payload(data))

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def to_data(self):
        return load_json(self.manifest_json)

    def transition(self, parent):
        data = self.to_data()
        if parent is None:
            if data['parent'] is not None or data['sequence'] != 1:
                raise ValueError('Missing committed revision parent')
            before = set()
        else:
            if (not isinstance(parent,DatasetRevision) or parent.content_id != data['parent']
                    or parent.to_data()['dataset'] != data['dataset']
                    or parent.to_data()['sequence']+1 != data['sequence']):
                raise ValueError('Revision parent, dataset or sequence differs')
            before = set(parent.to_data()['members'])
        added, removed = set(data['added']),set(data['removed'])
        if added & before or not removed <= before:
            raise ValueError('Revision adds existing or removes unknown members')
        if set(data['members']) != (before-removed)|added:
            raise ValueError('Revision membership differs from replayed transition')
        return True


class DatasetLedger:
    """Bounded immutable records plus serialized optimistic revision commits."""
    def __init__(self,path,*,dataset):
        require_text(dataset,'dataset',limit=256)
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.dataset=dataset
        with self._connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS revisions(id TEXT PRIMARY KEY,parent TEXT,manifest TEXT NOT NULL,
                    FOREIGN KEY(parent) REFERENCES revisions(id));
                CREATE TABLE IF NOT EXISTS settings(name TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            db.execute("INSERT OR IGNORE INTO settings VALUES ('dataset',?)",(dataset,))
            if db.execute("SELECT value FROM settings WHERE name='dataset'").fetchone()[0] != dataset:
                raise ValueError('Ledger is already bound to another dataset')

    @classmethod
    def open_read_only(cls,path,*,dataset):
        require_text(dataset,'dataset',limit=256)
        path=Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError('Existing regular dataset database required')
        result=object.__new__(cls)
        result.path=path
        result.dataset=dataset
        result._read_only=True
        with result._connection() as db:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'records','revisions','settings'}<=tables:
                raise ValueError('Dataset tables missing or replaced by views')
            row=db.execute("SELECT value FROM settings WHERE name='dataset'").fetchone()
            if row is None or row[0]!=dataset:
                raise ValueError('Read-only dataset binding differs')
        return result

    @contextmanager
    def _connection(self):
        readonly=getattr(self,'_read_only',False)
        db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=5,isolation_level=None) if readonly else sqlite3.connect(self.path,timeout=5,isolation_level=None)
        try:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN' if readonly else 'BEGIN IMMEDIATE')
            yield db
            if db.in_transaction:
                db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    @staticmethod
    def _head(db):
        row=db.execute("SELECT value FROM settings WHERE name='head'").fetchone()
        return None if row is None else require_digest(row[0])

    @property
    def head(self):
        with self._connection() as db:
            return self._head(db)

    def _revision(self,db,identifier):
        require_digest(identifier)
        row=db.execute('SELECT substr(manifest,1,1000001),parent FROM revisions WHERE id=?',(identifier,)).fetchone()
        if row is None or len(row[0].encode()) > 1_000_000:
            raise ValueError('Missing or oversized revision')
        revision=DatasetRevision(row[0])
        if (revision.content_id != identifier or revision.to_data()['dataset'] != self.dataset
                or revision.to_data()['parent'] != row[1]):
            raise ValueError('Stored revision commitment or parent column differs')
        return revision

    def _history(self,db,identifier):
        reversed_rows=[]
        current=identifier
        seen=set()
        while current is not None:
            if current in seen or len(seen)>=MAX_REVISIONS:
                raise ValueError('Cyclic or excessive revision history')
            seen.add(current)
            row=self._revision(db,current)
            reversed_rows.append(row)
            current=row.to_data()['parent']
        parent=None
        for row in reversed(reversed_rows):
            row.transition(parent)
            parent=row
        return tuple(reversed(reversed_rows))

    @staticmethod
    def _member_bytes(db,identifiers):
        """Reject oversized snapshots before materializing their JSON payloads."""
        total=0
        for identifier in identifiers:
            row=db.execute('SELECT length(CAST(payload AS BLOB)) FROM records WHERE id=?',(identifier,)).fetchone()
            if row is None or type(row[0]) is not int or not 0<row[0]<=MAX_RECORD_BYTES:
                raise ValueError('Missing or oversized dataset record')
            total+=row[0]
            if total>MAX_SNAPSHOT_BYTES:
                raise ValueError('Dataset snapshot aggregate byte budget exceeded')
        return total

    def _load_record(self,db,identifier):
        require_digest(identifier)
        row=db.execute('SELECT substr(payload,1,1000001) FROM records WHERE id=?',(identifier,)).fetchone()
        if row is None:
            raise ValueError('Revision references unavailable scientific record')
        record,_=_record(row[0])
        if record.content_id!=identifier:
            raise ValueError('Scientific record commitment differs')
        return record

    def commit(self,*,expected_head,actor,reason,add=(),remove=()):
        """Atomic CAS; failures leave neither records nor a partial revision."""
        if getattr(self,'_read_only',False):
            raise PermissionError('Read-only dataset ledger cannot commit')
        if expected_head is not None:
            require_digest(expected_head)
        require_text(actor,'actor',limit=256)
        require_text(reason,'reason')
        incoming=bounded(add,MAX_ACTIONS,'added records')
        records={}
        incoming_bytes=0
        for item in incoming:
            if not isinstance(item,ScientificRecord):
                raise ValueError('Only independently replayed ScientificRecord values admitted')
            value,encoded=_record(item.payload_json)
            if value.content_id in records:
                raise ValueError('Duplicate added scientific record')
            incoming_bytes+=len(encoded.encode())
            if incoming_bytes>MAX_SNAPSHOT_BYTES:
                raise ValueError("Incoming dataset aggregate byte budget exceeded")
            records[value.content_id]=encoded
        removed=_identifiers(remove,limit=MAX_ACTIONS,name='removed records')
        with self._connection() as db:
            if self._head(db)!=expected_head:
                raise ValueError('Stale dataset revision head')
            history=() if expected_head is None else self._history(db,expected_head)
            parent=history[-1] if history else None
            before=set(parent.to_data()['members']) if parent else set()
            members=(before-set(removed))|set(records)
            revision=DatasetRevision(canonical_payload({'schema_version':1,'dataset':self.dataset,
                'parent':expected_head,'actor':actor,'reason':reason,'added':sorted(records),
                'removed':list(removed),'members':sorted(members),'sequence':len(history)+1}))
            revision.transition(parent)
            for key,payload in records.items():
                existing=db.execute('SELECT substr(payload,1,1000001) FROM records WHERE id=?',(key,)).fetchone()
                if existing is not None and existing[0]!=payload:
                    raise ValueError('Existing scientific record was corrupted')
                if existing is None:
                    if db.execute('SELECT count(*) FROM records').fetchone()[0]>=MAX_MEMBERS:
                        raise ValueError('Ledger record capacity exceeded; explicit archival required')
                    db.execute('INSERT INTO records VALUES (?,?)',(key,payload))
            self._member_bytes(db,sorted(members))
            # Every retained record is checked before creating a new commitment.
            for key in sorted(members):
                self._load_record(db,key)
            db.execute('INSERT INTO revisions VALUES (?,?,?)',
                       (revision.content_id,expected_head,revision.manifest_json))
            db.execute("INSERT OR REPLACE INTO settings VALUES ('head',?)",(revision.content_id,))
            return revision

    def checkout(self,*,expected_head):
        return self.snapshot(expected_head,expected_head=expected_head)

    def snapshot(self,revision_id,*,expected_head):
        """Reconstruct a historical revision only within the externally pinned chain."""
        require_digest(revision_id)
        require_digest(expected_head)
        with self._connection() as db:
            if self._head(db)!=expected_head:
                raise ValueError('Dataset head differs from externally pinned commitment')
            history=self._history(db,expected_head)
            matches=[row for row in history if row.content_id==revision_id]
            if not matches:
                raise ValueError('Revision does not belong to the pinned dataset history')
            revision=matches[0]
            self._member_bytes(db,revision.to_data()['members'])
            records=tuple(self._load_record(db,key) for key in revision.to_data()['members'])
            return revision,records

    def history(self,*,expected_head):
        require_digest(expected_head)
        with self._connection() as db:
            if self._head(db)!=expected_head:
                raise ValueError('Dataset head differs from pinned commitment')
            return self._history(db,expected_head)

    def diff(self,older,newer):
        """Compare two pinned historical snapshots without mutating the ledger."""
        with self._connection() as db:
            left=self._history(db,older)[-1]
            right=self._history(db,newer)[-1]
            a,b=set(left.to_data()['members']),set(right.to_data()['members'])
            return {'older':older,'newer':newer,'added':sorted(b-a),'removed':sorted(a-b),
                    'unchanged':len(a&b),'scope':'membership difference, not semantic novelty'}
