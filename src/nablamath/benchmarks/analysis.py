"""Stratified external solver outcomes, confidence intervals and verified answers.

Rates describe the supplied finite corpus. Correlated constructor samples do not
justify population independence; solver failures do not establish expert difficulty.
"""
import math
from collections import Counter
from statistics import median
from ..core.semantic_ir import fingerprint
from ..forge.task_spec import TaskSpec
from ..verify.trace import verify_candidate


def _wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes/total
    center = (p+z*z/(2*total))/(1+z*z/total)
    radius = z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/(1+z*z/total)
    return [max(0.,center-radius), min(1.,center+radius)]


def analyze_benchmark(report):
    rows = report['tasks']
    if not 1 <= len(rows) <= 10000 or len({r['task_id'] for r in rows}) != len(rows):
        raise ValueError('Tarefas únicas limitadas obrigatórias')
    source = {k:v for k,v in report.items() if k != 'benchmark_id'}
    if fingerprint(source) != report['benchmark_id']:
        raise ValueError('Hash do benchmark divergente')
    groups = {}
    for row in rows:
        task = TaskSpec.from_data(row['task'])
        if task.content_id != row['task_id'] or not row['results']:
            raise ValueError('Tarefa ou resultados inválidos')
        for backend, outcome in row['results'].items():
            status = outcome['status']
            if status not in {'solved','incorrect','timeout','unsupported','error'}:
                raise ValueError('Status desconhecido')
            if status == 'solved' and not verify_candidate(task, outcome['candidate']).valid:
                raise ValueError('Resposta marcada correta não passou no verificador')
            for timing in ('solver_seconds','wall_seconds'):
                value = outcome.get(timing)
                if value is not None and (isinstance(value,bool) or not math.isfinite(value) or value < 0):
                    raise ValueError('Tempo inválido')
            for family, size in (('*','*'), (task.family,'*'), (task.family,task.size)):
                groups.setdefault((backend,family,size), []).append(outcome)
    summaries = []
    for (backend, family, size), outcomes in sorted(groups.items(),key=lambda pair:tuple(map(str,pair[0]))):
        counts = Counter(row['status'] for row in outcomes)
        supported = len(outcomes)-counts['unsupported']
        timings = [row['solver_seconds'] for row in outcomes if row['status']=='solved' and 'solver_seconds' in row]
        summaries.append({'backend':backend,'family':family,'size':size,'count':len(outcomes),
                          'outcomes':dict(sorted(counts.items())), 'supported_count':supported,
                          'supported_success_rate':counts['solved']/supported if supported else None,
                          'success_wilson_95':_wilson(counts['solved'],supported),
                          'median_solved_solver_seconds':median(timings) if timings else None,
                          'scope':'conditional on supported sampled tasks; iid coverage not established'})
    payload = {'schema_version':1,'source_benchmark_id':report['benchmark_id'],'strata':summaries,
               'answer_verification':'all solved candidates rechecked',
               'expert_difficulty_established':False,
               'limitations':'Descriptive finite corpus; unsupported is not failure, incorrect can be a solver defect; timing claims are supplied measurements.'}
    return {**payload,'analysis_id':fingerprint(payload)}
