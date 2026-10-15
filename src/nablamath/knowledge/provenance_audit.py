"""Content-addressed evidence and bounded independent replay of supported artifacts."""
from dataclasses import dataclass
import json
from ..core.semantic_ir import canonical_json,fingerprint
from ..core.units import Quantity,Unit


def restore_quantities(value):
    if isinstance(value,dict):
        if set(value)=={'value','unit'} and isinstance(value['unit'],dict):
            unit=value['unit']
            return Quantity(value['value'],Unit(tuple(unit['dimensions']),unit['scale']))
        return {k:restore_quantities(v) for k,v in value.items()}
    if isinstance(value,list):return [restore_quantities(v) for v in value]
    return value


def replay_domain(report):
    from ..domains.engineering import axial_bar,cantilever_tip
    from ..domains.materials import thermoelastic
    from ..domains.chemistry import balance_reaction,two_species_equilibrium
    from ..domains.earth import hydrostatic_pressure
    from ..domains.biology import logistic,sir
    from ..domains.control import StateSpace
    from ..domains.circuits import rc_step, series_rlc
    from ..domains.materials import isotropic_elasticity
    from ..domains.earth import layered_hydrostatics
    from ..domains.chemistry import reversible_first_order
    from ..worlds.multiphysics import electrothermal
    operations={'isotropic_small_strain_3d':isotropic_elasticity,'ideal_series_RLC_phasor':series_rlc,
                'layered_static_hydrostatics':layered_hydrostatics,'ideal_reversible_first_order':reversible_first_order,
                'ideal_series_RC_step':rc_step,'linear_axial_bar':axial_bar,'euler_bernoulli_cantilever':cantilever_tip,
                'linear_thermoelasticity':thermoelastic,'neutral_elemental_balance':balance_reaction,
                'ideal_A_to_B_equilibrium':two_species_equilibrium,'constant_density_hydrostatics':hydrostatic_pressure,
                'continuous_logistic_population':logistic,'closed_normalized_SIR':sir,
                'linear_current_driven_electrothermal':electrothermal}
    inputs=restore_quantities(report['inputs'])
    if report['model']=='normalized_continuous_siso':
        actual=StateSpace(inputs['A'],inputs['B'],inputs['C'],inputs['D']).analyze()
    else:
        actual=operations[report['model']](**inputs)
    return canonical_json(actual)==canonical_json(report) and actual['checks_passed']


@dataclass(frozen=True)
class Evidence:
    kind: str
    payload_json: str
    provenance: str
    license_id: str
    synthetic: bool

    def __post_init__(self):
        if self.kind not in {'domain_result','exact_trace','formal_certificate','observation','literature','refutation','discovery','policy'}:
            raise ValueError('Tipo de evidência desconhecido')
        if not self.provenance.strip() or not self.license_id.strip() or type(self.synthetic) is not bool or len(self.payload_json.encode())>16*1024*1024:
            raise ValueError('Metadados de evidência inválidos')
        object.__setattr__(self,'payload_json',canonical_json(json.loads(self.payload_json)))

    @property
    def payload(self):return json.loads(self.payload_json)

    @property
    def evidence_id(self):return fingerprint(self.to_data())

    def to_data(self):
        return {'kind':self.kind,'payload':self.payload,'provenance':self.provenance,
                'license_id':self.license_id,'synthetic':self.synthetic}

    @classmethod
    def from_data(cls,data):
        return cls(data['kind'],canonical_json(data['payload']),data['provenance'],data['license_id'],data['synthetic'])

    def verify(self):
        try:
            data=self.payload
            if self.kind=='domain_result':
                valid=replay_domain(data);method='domain_reexecution'
            elif self.kind=='exact_trace':
                from ..verify.trace import VerificationTrace
                trace=VerificationTrace.from_data(data)
                valid=trace.to_data()['verification']['valid'];method='independent_exact_trace'
            elif self.kind=='formal_certificate':
                from ..verify.certificate import verify_formal_certificate
                valid=verify_formal_certificate(data);method='formal_backend_reexecution'
            elif self.kind=='literature':
                from .literature import LiteratureCorpus
                corpus=LiteratureCorpus.from_data(data['corpus'])
                actual=corpus.search(data['query']['query'],limit=data.get('limit',10))
                valid=canonical_json(actual)==canonical_json(data['query']);method='local_corpus_query_reexecution'
            elif self.kind=='refutation':
                from ..falsifier.search import investigate
                actual=investigate(data['left'],data['right'],radius=data['radius'],budget=data['budget'])
                valid=canonical_json(actual)==canonical_json(data);method='bounded_refutation_reexecution'
            elif self.kind=='discovery':
                from ..discovery.research_program import verify_research
                valid=verify_research(data);method='research_reexecution'
            elif self.kind=='policy':
                from ..evolution.release_gate import verify_policy_receipt
                valid=verify_policy_receipt(data);method='analytic_policy_reexecution_no_issuer_authentication'
            else:
                # Measurement values are declarations, never verified physical facts.
                valid=isinstance(data,dict) and bool(data);method='content_integrity_only'
            return {'valid':bool(valid),'method':method,'evidence_id':self.evidence_id,
                    'external_provenance_authenticated':False}
        except (ValueError,KeyError,TypeError,ArithmeticError,RuntimeError):
            return {'valid':False,'method':'replay_failed','evidence_id':self.evidence_id,
                    'external_provenance_authenticated':False}


def audit_ledger(ledger,evidence):
    evidence=dict(evidence)
    if len(evidence)>1000 or len(ledger.revisions)>10000:raise ValueError('Auditoria excede orçamento')
    missing=[];invalid=[];checks={}
    for key,item in evidence.items():
        if key!=item.evidence_id:
            invalid.append(key);continue
        checks[key]=item.verify()
        if not checks[key]['valid']:invalid.append(key)
    for revision in ledger.revisions:
        for reference in revision.evidence:
            if reference not in evidence:missing.append({'revision_id':revision.revision_id,'evidence_id':reference})
    return {'valid':not missing and not invalid,'missing':missing,'invalid':invalid,'evidence_checks':checks,
            'scientific_truth_established':False,
            'scope':'reference integrity and supported replay; evidence-to-prose entailment and provenance require review'}
