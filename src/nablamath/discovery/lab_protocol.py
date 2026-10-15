"""Content-addressed preregistration and holdout assessment, without operating instruments."""
from ..core.semantic_ir import fingerprint
from .hypothesis import assess


def preregister(hypotheses, calibration, *, protocol, max_failures=0):
    hypotheses = tuple(hypotheses)
    if not 1 <= len(hypotheses) <= 16 or len({h.hypothesis_id for h in hypotheses}) != len(hypotheses):
        raise ValueError('Distinct bounded hypothesis set required')
    if calibration.role != 'calibration' or not isinstance(protocol, str) or not protocol.strip():
        raise ValueError('Calibration role and explicit protocol required')
    if type(max_failures) is not int or not 0 <= max_failures <= 128:
        raise ValueError('Invalid frozen failure threshold')
    for h in hypotheses:
        assess(h, calibration)
    payload = {'schema_version': 1, 'protocol': protocol, 'max_failures': max_failures,
               'hypothesis_ids': [h.hypothesis_id for h in hypotheses],
               'calibration_id': calibration.dataset_id,
               'calibration_x': sorted(str(o.x) for o in calibration.observations)}
    return {**payload, 'registration_id': fingerprint(payload)}


def evaluate_registration(registration, hypotheses, calibration, holdout):
    hypotheses = tuple(hypotheses)
    expected = preregister(hypotheses, calibration, protocol=registration['protocol'],
                          max_failures=registration['max_failures'])
    if expected != registration or holdout.role != 'holdout':
        raise ValueError('Changed registration or missing holdout role')
    if {o.x for o in calibration.observations} & {o.x for o in holdout.observations}:
        raise ValueError('Calibration/holdout input leakage')
    rows = []
    for h in hypotheses:
        result = assess(h, holdout)
        failures = sum(not r['within_uncertainty'] for r in result['rows'])
        rows.append({'assessment': result, 'failures': failures,
                     'accepted_on_supplied_holdout': failures <= registration['max_failures']})
    payload = {'schema_version': 1, 'registration_id': registration['registration_id'],
               'holdout_id': holdout.dataset_id, 'results': rows,
               'synthetic': holdout.synthetic, 'external_authentication': False,
               'scope': 'Frozen local observation assessment; not independent experimental replication'}
    return {**payload, 'report_id': fingerprint(payload)}
