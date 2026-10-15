"""Common-AST profiles for research papers, engineering reports and teaching notes."""
from .document_model import Document,Section

PROFILES={
 'research_paper':('Hypothesis','Method','Results','Discussion'),
 'engineering_report':('Requirements','Model','Verification','Results','Operating limits'),
 'teaching':('Learning objectives','Assumptions','Worked examples','Exercises','Solutions'),
}


def build_profile(profile,title,sections,*,limitations,references=(),synthetic=True):
    if profile not in PROFILES or not isinstance(sections,dict) or set(sections)!=set(PROFILES[profile]):
        raise ValueError('Perfil requer todas as seções declaradas sem seções desconhecidas')
    ordered=[]
    for name in PROFILES[profile]:
        section=sections[name]
        if not isinstance(section,Section) or section.heading!=name:raise ValueError('Seção deve corresponder ao perfil')
        ordered.append(section)
    evidential={'research_paper':'Results','engineering_report':'Verification','teaching':'Worked examples'}[profile]
    section=sections[evidential]
    if not section.evidence_ids and not any(t.evidence_ids for t in section.tables):raise ValueError('Perfil requer evidência rastreável')
    return Document(title,tuple(ordered),synthetic,limitations,tuple(references))
