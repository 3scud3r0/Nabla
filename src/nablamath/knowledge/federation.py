"""Offline snapshot exchange, optional HMAC authentication and fork-preserving federation."""
import hashlib
import hmac
import json
from ..core.semantic_ir import canonical_json,fingerprint
from .versioned_claims import ClaimLedger
from .provenance_audit import Evidence,audit_ledger
from .semantic_reconciliation import reconcile


def export_snapshot(ledger,evidence,*,peer_id,key=None):
    if not peer_id.strip():raise ValueError('Identificador de origem obrigatório')
    audit=audit_ledger(ledger,evidence)
    if not audit['valid']:raise ValueError('Proveniência incompleta ou evidência inválida')
    payload={'schema_version':1,'peer_id':peer_id,'ledger':ledger.to_data(),
             'evidence':{k:v.to_data() for k,v in sorted(evidence.items())}}
    bundle={**payload,'snapshot_id':fingerprint(payload)}
    if key is not None:
        if not isinstance(key,bytes) or len(key)<32:raise ValueError('Chave compartilhada de pelo menos 32 bytes requerida')
        bundle['authentication']=hmac.new(key,canonical_json(bundle).encode(),hashlib.sha256).hexdigest()
    return bundle


def verify_snapshot(bundle,*,key=None,allow_unsigned=False):
    try:
        if len(canonical_json(bundle).encode())>32*1024*1024:raise ValueError('Snapshot excede limite')
        unsigned={k:v for k,v in bundle.items() if k!='authentication'}
        payload={k:v for k,v in unsigned.items() if k!='snapshot_id'}
        if set(payload)!={'schema_version','peer_id','ledger','evidence'} or payload['schema_version']!=1 or fingerprint(payload)!=unsigned['snapshot_id']:
            raise ValueError('Contrato ou hash de snapshot inválido')
        if not isinstance(payload['peer_id'],str) or not payload['peer_id'].strip():raise ValueError('Origem ausente')
        authenticated=False
        if key is not None:
            if not isinstance(key,bytes) or len(key)<32:raise ValueError('Chave inválida')
            expected=hmac.new(key,canonical_json(unsigned).encode(),hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected,bundle.get('authentication','')):raise ValueError('Autenticação de origem falhou')
            authenticated=True
        elif not allow_unsigned or 'authentication' in bundle:
            raise ValueError('Chave de origem ausente; snapshot não autenticado')
        ledger=ClaimLedger.from_data(payload['ledger'])
        evidence={k:Evidence.from_data(v) for k,v in payload['evidence'].items()}
        audit=audit_ledger(ledger,evidence)
        return {'valid':audit['valid'],'authenticated':authenticated,'peer_id':payload['peer_id'],
                'snapshot_id':bundle['snapshot_id'],'audit':audit,'scientific_truth_established':False}
    except (ValueError,KeyError,TypeError,ArithmeticError) as exc:
        return {'valid':False,'authenticated':False,'reason':str(exc)}


class Federation:
    def __init__(self,*,trusted_peers=None,allow_unsigned=False):
        self.trusted_peers=dict(trusted_peers or {});self.allow_unsigned=allow_unsigned;self._snapshots={}

    def ingest(self,bundle):
        peer=bundle.get('peer_id','')
        verification=verify_snapshot(bundle,key=self.trusted_peers.get(peer),allow_unsigned=self.allow_unsigned)
        if not verification['valid']:raise ValueError('Snapshot rejeitado: '+str(verification))
        self._snapshots[bundle['snapshot_id']]=json.loads(canonical_json(bundle))
        return verification

    def reconcile(self,*,metadata=None):
        ledgers=[ClaimLedger.from_data(b['ledger']) for b in self._snapshots.values()]
        report=reconcile(ledgers,metadata=metadata)
        return {**report,'snapshot_ids':sorted(self._snapshots),'peers':sorted({b['peer_id'] for b in self._snapshots.values()})}


class SignedFederation:
    """Offline federation with individually pinned Ed25519 authorship keys.

    Replays are idempotent by snapshot ID. Revocation is checked again when
    reconciling, so a formerly accepted key cannot remain implicitly trusted.
    """
    def __init__(self, trust):
        self.trust = trust
        self._envelopes = {}

    def ingest(self, envelope):
        from .identity import verify_signed_snapshot
        report = verify_signed_snapshot(envelope, self.trust)
        if not report['valid']:
            raise ValueError('Envelope rejeitado: '+report.get('reason', 'evidência inválida'))
        self._envelopes[report['snapshot_id']] = json.loads(canonical_json(envelope))
        return report

    def reconcile(self, *, metadata=None):
        federation = Federation(allow_unsigned=True)
        for envelope in self._envelopes.values():
            # The internal unsigned import is reached only after signature replay.
            self.ingest(envelope)
            federation.ingest(envelope['snapshot'])
        return {**federation.reconcile(metadata=metadata), 'authentication': 'Ed25519-pinned-peer-key',
                'real_world_identity_verified': False}
