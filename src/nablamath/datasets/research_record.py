"""Versioned research artifact records: traces, simulations, scenes and observations.

Each computational profile is replayed by its designated checker. Observational
records validate shape/metadata only and explicitly remain unverified as facts.
"""
from dataclasses import dataclass
import json
import math
from ..core.semantic_ir import canonical_json,fingerprint


@dataclass(frozen=True)
class ResearchRecord:
    payload_json: str

    def __post_init__(self):
        if len(self.payload_json.encode())>8*1024*1024:raise ValueError('Artefato excede limite')
        data=json.loads(self.payload_json)
        required={'record_kind','schema_version','kind','payload','license_id','provenance','scope','limitations','synthetic','split','verifier_version'}
        if set(data)!=required or data['record_kind']!='research_artifact' or data['schema_version']!=1 or data['verifier_version']!='research-replay-v1':
            raise ValueError('Contrato de artefato científico inválido')
        if (any(not isinstance(data[k],str) or not data[k].strip() for k in ('license_id','provenance','scope','limitations'))
                or type(data['synthetic']) is not bool or data['split'] not in ('unassigned','train','validation','test') or not isinstance(data['payload'],dict)):
            raise ValueError('Metadados, origem e partição obrigatórios')
        verification=_check(data['kind'],data['payload'])
        if not verification['valid']:raise ValueError('Artefato não passou na reconferência')
        object.__setattr__(self,'payload_json',canonical_json(data))

    def to_data(self):return json.loads(self.payload_json)
    @property
    def content_id(self):return fingerprint(self.to_data())
    @property
    def semantic_id(self):
        d=self.to_data();p=d['payload'];kind=d['kind']
        if kind=='exact_trace':identity={'task_id':p['task_id']}
        elif kind=='ode':identity=p['model_spec']
        elif kind=='domain':identity={'model':p['model'],'inputs':p['inputs']}
        elif kind=='diffusion':identity={k:p[k] for k in ('initial','boundary','length','diffusivity','duration')}
        elif kind=='scene':identity=p.get('model',p)
        else:identity=p
        return fingerprint({'kind':kind,'identity':identity})
    def verification(self):return _check(self.to_data()['kind'],self.to_data()['payload'])
    @classmethod
    def from_data(cls,data):return cls(canonical_json(data))
    def with_split(self,split):return self.from_data({**self.to_data(),'split':split})


def _check(kind,payload):
    if kind=='exact_trace':
        from ..verify.trace import VerificationTrace
        valid=VerificationTrace.from_data(payload).to_data()['verification']['valid']
    elif kind=='domain':
        from ..knowledge.provenance_audit import replay_domain
        valid=replay_domain(payload)
    elif kind=='ode':
        from ..worlds.model_spec import ModelSpec
        from ..worlds.validation import simulate,simulate_adaptive
        spec=payload['model_spec'];model=ModelSpec(spec['name'],tuple(spec['initial']),spec['rate'],spec['duration'])
        if payload['method']=='dopri54':
            actual=simulate_adaptive(model,atol=payload['atol'],rtol=payload['rtol'],initial_step=payload.get('initial_step'))
        else:actual=simulate(model,steps=payload['steps'],method=payload['method'])
        valid=canonical_json(payload)==canonical_json(actual)
    elif kind=='diffusion':
        from ..worlds.pde.diffusion import solve_diffusion
        options={k:payload[k] for k in ('length','diffusivity','duration','steps','boundary','method','snapshot_stride')}
        valid=canonical_json(payload)==canonical_json(solve_diffusion(payload['initial'],**options))
    elif kind=='scene':
        from ..graphics.scene_graph import GeometryScene
        from ..graphics.artifacts import replay_model
        from ..verify.geometry import verify_geometry
        scene=GeometryScene.from_data(payload)
        valid=verify_geometry(scene).valid and replay_model(scene)['valid']
    elif kind=='observation':
        if set(payload)!={'rows','units','instrument','calibration','uncertainty_scope'} or not all(isinstance(payload[k],str) and payload[k].strip() for k in ('instrument','calibration','uncertainty_scope')):
            raise ValueError('Origem observacional/calibração obrigatórias')
        rows=payload['rows'];units=payload['units']
        if not isinstance(rows,list) or not 1<=len(rows)<=10000 or not isinstance(units,list) or not units or any(not isinstance(u,str) or not u.strip() for u in units):
            raise ValueError('Perfil observacional inválido')
        for row in rows:
            if set(row)!={'values','uncertainties'} or len(row['values'])!=len(units) or len(row['uncertainties'])!=len(units):raise ValueError('Dimensões observacionais inválidas')
            if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in row['values']+row['uncertainties']) or any(u<0 for u in row['uncertainties']):raise ValueError('Observações não finitas')
        return {'valid':True,'method':'observation_shape_and_metadata_only','scientific_claim_verified':False,'external_provenance_authenticated':False}
    else:raise ValueError('Perfil de artefato não suportado')
    return {'valid':bool(valid),'method':kind+'_reexecution','scientific_claim_verified':False,
            'external_provenance_authenticated':False,'scope':'computational consistency only; not unrestricted physical or semantic truth'}


def make_research_record(kind,payload,*,license_id,provenance,scope,limitations,synthetic,split='unassigned'):
    return ResearchRecord.from_data({'record_kind':'research_artifact','schema_version':1,'kind':kind,'payload':payload,
            'license_id':license_id,'provenance':provenance,'scope':scope,'limitations':limitations,'synthetic':synthetic,
            'split':split,'verifier_version':'research-replay-v1'})


def parse_record(data):
    if data.get('record_kind')=='research_artifact':return ResearchRecord.from_data(data)
    from .schema import ScientificRecord
    return ScientificRecord.from_data(data)
