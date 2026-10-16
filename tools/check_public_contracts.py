"""Validate finite capability contracts, public links and full roadmap traceability."""
from pathlib import Path
import json
import re
from urllib.parse import unquote, urlsplit

from nablamath.core.capabilities import ScientificCapabilities
from nablamath.core.semantic_contracts import load_json

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ('README.md', 'description.md', 'vision.md', 'docs/PLANO_MESTRE_2026_2056.md',
    'docs/ARCHITECTURE_AND_ACCEPTANCE.md', 'docs/MATHEMATICS_COMPLETION_AUDIT.md',
    'docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md')


def local_links(path, root=ROOT):
    root=Path(root).resolve()
    checked=0
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
        target=target.strip().strip('<>')
        parsed=urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        resolved=(path.parent/unquote(parsed.path)).resolve()
        if not resolved.is_relative_to(root) or not resolved.exists():
            raise ValueError('Broken public link: '+str(path)+' -> '+target)
        checked+=1
    return checked


def _bounded_json(path):
    with path.open('rb') as stream:
        raw=stream.read(1_000_001)
    if len(raw)>1_000_000:
        raise ValueError('Public contract exceeds byte budget')
    return load_json(raw.decode('utf-8'))


def validate(root=ROOT):
    root=Path(root).resolve()
    registry=ScientificCapabilities.load(root/'docs/acceptance/scientific_capabilities.yaml')
    registry.validate_evidence(root)
    matrix=_bounded_json(root/'docs/acceptance/evidence_matrix.json')
    trace=_bounded_json(root/'docs/acceptance/vision_traceability.json')
    rows=trace['requirements']
    if len(rows)!=213 or [row['id'] for row in rows]!=list(range(1,214)):
        raise ValueError('Vision mapping must preserve all 213 requirement identities')
    originals=matrix['requirements']
    if (len(originals)!=213 or any(type(row.get('id')) is not int for row in originals)
        or [row['id'] for row in originals]!=list(range(1,214))
        or any(type(row.get('id')) is not int for row in rows)):
        raise ValueError('Acceptance matrix must preserve all 213 requirement identities')
    for row, original in zip(rows,originals):
        if row['target']!=original['target'] or row['status']!=original['status']:
            raise ValueError('Stale or rewritten vision traceability')
        if row['implementation']!=original['implementation'] or row['tests']!=original['tests']:
            raise ValueError('Traceability differs from acceptance matrix')
        if (not isinstance(row['phases'],list) or not row['phases']
            or any(not isinstance(phase,str) for phase in row['phases'])
            or len(set(row['phases']))!=len(row['phases'])
            or any(phase not in ['F'+str(i) for i in range(14)] for phase in row['phases'])):
            raise ValueError('Unknown phase mapping')
    disposition=_bounded_json(root/'docs/acceptance/remaining_85_implementation.json')
    former=disposition['requirements']
    expected=disposition['baseline_planned_ids']
    if (len(former)!=85 or len(expected)!=85 or len(set(expected))!=85
        or any(type(key) is not int or not 1<=key<=213 for key in expected)
        or [row['id'] for row in former]!=expected):
        raise ValueError('Disposition must cover all85 originally planned items exactly')
    indexed={row['id']:row for row in originals}
    for row in former:
        if type(row['id']) is not int or row['status']!='partial':
            raise ValueError('Local disposition must not claim validated acceptance')
        for field in ('implementation','tests','remaining'):
            if row[field]!=indexed[row['id']][field]:
                raise ValueError('Disposition evidence differs from original requirement matrix')
        if row['change_kind'] not in ('implementation_or_contract_changed','existing_tested_profile_recognized'):
            raise ValueError('Unknown implementation disposition kind')
    backlog=_bounded_json(root/'docs/acceptance/backlog_traceability.json')
    if backlog['count']!=104 or len(backlog['items'])!=104:
        raise ValueError('All104 original backlog items require explicit disposition')
    import hashlib
    original=(root/'docs/audits/PHASES_1_12_COMPLETION_BACKLOG.json').read_bytes()
    if backlog['original_source_sha256']!=hashlib.sha256(original).hexdigest():
        raise ValueError('Historical backlog source changed')
    if backlog['all_backlog_acceptance_established'] is not False:
        raise ValueError('Path overlap cannot establish full backlog acceptance')
    links=sum(local_links(root/name,root) for name in DOCUMENTS)
    return {'requirements':len(rows),'local_links':links,'capability_manifest_id':registry.content_id,
            'scope':'local contract/link consistency; no external review or scientific completion implied'}


if __name__=='__main__':
    print(json.dumps(validate(),sort_keys=True))
