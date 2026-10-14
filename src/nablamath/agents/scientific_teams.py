"""Declarative team jobs with separate roles, complete preflight and auditable results."""
from dataclasses import dataclass
from .permissions import Permissions
from .planner import Planner,verify_run
from .proposals import Proposal
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class TeamMember:
    member_id: str
    role: str
    permissions: Permissions

    def __post_init__(self):
        if not self.member_id.strip() or self.role not in {'proposer','verifier','reviewer','curator'}:
            raise ValueError('Identidade e papel científico obrigatórios')
        if self.role in {'verifier','reviewer'} and not self.permissions.allowed_tools <= {'verify','simulate'}:
            raise ValueError('Verificação/revisão não pode invocar proponentes ou publicação')


@dataclass(frozen=True)
class TeamJob:
    job_id: str
    member_id: str
    proposal: Proposal
    depends_on: tuple[str,...] = ()

    def __post_init__(self):object.__setattr__(self,'depends_on',tuple(self.depends_on))


class ScientificTeam:
    def __init__(self,members,registry):
        members=tuple(members);self.members={m.member_id:m for m in members};self.registry=registry
        if len(self.members)!=len(members) or not 2<=len(members)<=16:
            raise ValueError('Equipe requer 2–16 identidades distintas')
        roles={m.role for m in members}
        if not {'proposer','verifier'}<=roles:raise ValueError('Proponente e verificador separados obrigatórios')

    def run(self,jobs):
        jobs=tuple(jobs);seen=set()
        if not 1<=len(jobs)<=32:raise ValueError('Orçamento de tarefas excedido')
        for job in jobs:
            if not job.job_id.strip() or job.job_id in seen or not set(job.depends_on)<=seen:
                raise ValueError('Ordem/dependências de tarefas inválidas')
            member=self.members[job.member_id]
            if len(job.proposal.actions)>member.permissions.max_calls:raise ValueError('Cota individual excedida')
            for action in job.proposal.actions:
                self.registry.validate(action.tool,action.arguments,member.permissions)
            seen.add(job.job_id)
        reports=[]
        for job in jobs:
            member=self.members[job.member_id]
            run=Planner(self.registry,member.permissions).run(job.proposal)
            if not verify_run(run):raise ValueError('Recibo de tarefa não reproduzível')
            reports.append({'job_id':job.job_id,'member_id':member.member_id,'role':member.role,'run':run})
            if not run['completed']:break
        outcomes=[receipt['result']['verification']['valid'] for row in reports for receipt in row['run']['receipts'] if receipt['tool']=='verify' and receipt['status']=='completed']
        payload={'jobs':reports,'all_candidates_verified':bool(outcomes) and all(outcomes),'verification_outcomes':outcomes,'completed':len(reports)==len(jobs) and all(r['run']['completed'] for r in reports),
                 'identities_independently_authenticated':False,
                 'scope':'explicit registered local actors; no claim of independent human peer review'}
        return {**payload,'team_run_id':fingerprint(payload)}
