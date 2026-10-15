"""Record positive and negative replications against a frozen local protocol."""
import math
from ..core.semantic_ir import fingerprint
from ..knowledge.replication_protocol import ReplicationProtocol


def record_replication(protocol, *, replicator, affiliations, conflicts, measured, evidence, source_evidence):
    """Evidence contains actual JSON artifacts indexed by their content digest.

    Independence is an operator declaration, never inferred from different IDs.
    source_evidence resolves every artifact preregistered by the protocol.
    """
    if not isinstance(protocol, ReplicationProtocol):
        raise ValueError('Protocol required')
    affiliations, conflicts = tuple(affiliations), tuple(conflicts)
    if not isinstance(replicator, str) or not replicator.strip() or not affiliations or any(not isinstance(x, str) or not x.strip() for x in (*affiliations, *conflicts)):
        raise ValueError('Replicator and affiliation declarations required')
    if replicator in protocol.authors or set(conflicts) & set(protocol.authors):
        raise ValueError('Declared author or conflict cannot independently replicate')
    if type(measured) not in (int, float) or not math.isfinite(measured):
        raise ValueError('Finite observed metric required')
    for mapping in (evidence, source_evidence):
        if not 1 <= len(mapping) <= 10000 or any(key != fingerprint(value) for key, value in mapping.items()):
            raise ValueError('Content-addressed evidence required')
    if not set(protocol.evidence_ids) <= set(source_evidence):
        raise ValueError('Protocol source evidence unavailable')
    payload = {'schema_version': 1, 'protocol_id': protocol.protocol_id,
               'claim_revision': protocol.claim_revision, 'replicator': replicator,
               'affiliations': list(affiliations), 'conflicts': list(conflicts),
               'metric': protocol.metric, 'measured': measured,
               'evidence': evidence, 'source_evidence': source_evidence,
               'outcome': 'within_preregistered_interval' if protocol.minimum <= measured <= protocol.maximum else 'negative_result',
               'independence': 'operator_declared_only', 'measurement_scope': 'operator-supplied observation; artifacts integrity checked, metric not recomputed', 'external_identity_verified': False,
               'claim_status_changed': False}
    return {**payload, 'replication_id': fingerprint(payload)}


def replay_replication(report, protocol):
    try:
        rebuilt = record_replication(protocol, **{key: report[key] for key in
            ('replicator', 'affiliations', 'conflicts', 'measured', 'evidence', 'source_evidence')})
        return rebuilt == report
    except (ValueError, TypeError, KeyError):
        return False
