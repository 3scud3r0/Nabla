"""Measured solver/budget profiles. Labels apply only to this benchmark and interpreter."""
from collections import Counter
from pathlib import Path
import platform
import math
import sys
import time

from ..core.semantic_ir import fingerprint
from ..verify.trace import verify_candidate
from .solvers import solve_task

PACKAGE_ROOT=str(Path(__file__).resolve().parents[1])


class SolverBudgetExceeded(RuntimeError):
    pass


def measure(task,strategy='exact',budget=1000000):
    if strategy not in {'exact','alternate'} or type(budget) is not int or not 1<=budget<=2000000:
        raise ValueError('Estrategia/orcamento invalido')
    steps=0
    def tracer(frame,event,arg):
        nonlocal steps
        filename=frame.f_code.co_filename
        if event=='line' and (filename.startswith(PACKAGE_ROOT) or filename.replace(chr(92),'/').endswith('/fractions.py')):
            steps+=1
            if steps>budget:
                raise SolverBudgetExceeded('python_line_budget')
        return tracer
    previous=sys.gettrace();started=time.perf_counter();candidate=None;error=None
    try:
        sys.settrace(tracer)
        candidate=solve_task(task,strategy)
        status='completed'
    except SolverBudgetExceeded:
        status='budget_exhausted'
    except (ValueError,ArithmeticError) as exc:
        status='unsupported_or_failed';error=str(exc)
    finally:
        sys.settrace(previous)
    elapsed=time.perf_counter()-started
    verification=None
    if status=='completed':
        verification=verify_candidate(task,candidate).to_data()
        if not verification['valid']:
            status='wrong_answer'
    return {'task_id':task.content_id,'family':task.family,'strategy':strategy,'budget':budget,
            'executed_python_lines':min(steps,budget+1),'elapsed_seconds':elapsed,'status':status,
            'candidate':candidate,'verification':verification,'error':error}


def difficulty_label(observations):
    successes=[row for row in observations if row['status']=='completed' and row['verification']['valid']]
    if not successes:
        return 'unresolved_within_budget'
    maximum=max(row['executed_python_lines'] for row in successes)
    if len(successes)<2:
        return 'strategy_sensitive'
    return 'low_budget' if maximum<=10000 else 'medium_budget' if maximum<=100000 else 'high_budget'


def calibrate(tasks,*,budget=1000000):
    tasks=tuple(tasks)
    if not 1<=len(tasks)<=128 or len({t.content_id for t in tasks})!=len(tasks):
        raise ValueError('Benchmark requer 1 a 128 problemas distintos')
    observations=[];ratings={}
    for task in tasks:
        measured=[measure(task,strategy,budget) for strategy in ('exact','alternate')]
        observations.extend(measured)
        ratings[task.content_id]={'label':difficulty_label(measured),'basis':'two_verified_solver_strategies_and_measured_budget'}
    report={'schema_version':1,'benchmark':'forge-local-budget-v1','python_version':platform.python_version(),'platform':platform.system(),
            'solver_version':'forge-solvers-v2','verifier_version':'forge-exact-v2',
            'task_ids':[t.content_id for t in tasks],'ratings':ratings,'observations':observations,
            'outcomes':dict(Counter(r['status'] for r in observations)),
            'limitations':'Local solver-relative calibration; line budgets include package/Fraction code. Wall time is supplementary. No external solver ranking or general difficulty claim.'}
    return {**report,'calibration_id':fingerprint(report)}


def validate_calibration(report,tasks):
    try:
        payload=dict(report);digest=payload.pop('calibration_id')
        if payload['schema_version']!=1 or digest!=fingerprint(payload) or payload['benchmark']!='forge-local-budget-v1':
            return False
        task_map={t.content_id:t for t in tasks}
        if set(payload['task_ids'])!=set(task_map) or len(payload['task_ids'])!=len(task_map):
            return False
        for task_id,task in task_map.items():
            observations=[r for r in payload['observations'] if r['task_id']==task_id]
            if len(observations)!=2 or {r['strategy'] for r in observations}!={'exact','alternate'}:
                return False
            for row in observations:
                if (row['family']!=task.family or row['status'] not in {'completed','budget_exhausted','unsupported_or_failed','wrong_answer'}
                        or type(row['budget']) is not int or not 1<=row['budget']<=2000000
                        or not isinstance(row['elapsed_seconds'],(float,int)) or not math.isfinite(row['elapsed_seconds']) or row['elapsed_seconds']<0):
                    return False
                if row['status']=='budget_exhausted' and (row['executed_python_lines']!=row['budget']+1 or row['candidate'] is not None):
                    return False
                if row['status']=='completed' and row['verification']!=verify_candidate(task,row['candidate']).to_data():
                    return False
                if row['status']=='completed' and not row['verification']['valid']:
                    return False
                if type(row['executed_python_lines']) is not int or not 0<=row['executed_python_lines']<=row['budget']+1:
                    return False
            if payload['ratings'][task_id]!={'label':difficulty_label(observations),'basis':'two_verified_solver_strategies_and_measured_budget'}:
                return False
        if payload['outcomes']!=dict(Counter(r['status'] for r in payload['observations'])):
            return False
        return True
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return False
