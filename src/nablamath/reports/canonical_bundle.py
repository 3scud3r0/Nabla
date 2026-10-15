"""Canonical report exports with stable numbering and byte-bound evidence maps."""
from hashlib import sha256
from html import escape
import json
from ..core.semantic_ir import fingerprint
from ..core.semantic_contracts import canonical_payload
from ..calc.session import encode
from ..documents.document_model import Document
from ..documents.exporters import to_html, to_latex, to_typst


def report_bundle(document, evidence):
    if not isinstance(document, Document) or type(evidence) is not dict:
        raise ValueError('Typed document and evidence mapping required')
    canonical_payload(evidence)
    canonical_payload(encode(document.to_data()))
    bindings = {}
    numbering = []
    counters = dict(equation=0, figure=0, table=0)
    for section_index, section in enumerate(document.sections, 1):
        identifiers = list(section.evidence_ids)
        for table in section.tables:
            identifiers.extend(table.evidence_ids)
        for identifier in identifiers:
            if identifier not in evidence or fingerprint(evidence[identifier]) != identifier:
                raise ValueError('Missing or modified evidence payload')
            bindings[identifier] = evidence[identifier]
        for kind in counters:
            for local_index, _ in enumerate(getattr(section, kind + 's'), 1):
                counters[kind] += 1
                numbering.append(dict(kind=kind, number=counters[kind], section=section_index,
                                      local_index=local_index))
    # The canonical numbering index is separate from backend layout decisions.
    appendix = '\n'.join(f'{row["kind"]} {row["number"]}: section {row["section"]}, item {row["local_index"]}' for row in numbering)
    exports = dict(html=to_html(document), latex=to_latex(document), typst=to_typst(document))
    exports['html'] = exports['html'].replace('</html>', '<pre aria-label="Object numbering">'+escape(appendix)+'</pre></html>')
    payload = dict(schema_version=1, document=document.to_data(), document_id=document.content_id,
                   evidence=bindings, numbering=numbering,
                   export_hashes={name:sha256(text.encode()).hexdigest() for name,text in exports.items()},
                   scope='Canonical source and export integrity; no PDF compilation or scientific endorsement implied')
    return json.loads(json.dumps(dict(manifest={**payload, 'bundle_id':fingerprint(payload)}, exports=exports)))


def verify_report_bundle(bundle):
    try:
        canonical_payload(bundle)
        manifest = bundle['manifest']
        document = Document.from_data(manifest['document'])
        return bundle == report_bundle(document, manifest['evidence'])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False
