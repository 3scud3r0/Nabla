"""Fail-closed evidence gate for declared transfer benchmarks, never an AGI test."""
import math
from ...training._bounded import bounded_tuple
from ...core.semantic_ir import fingerprint


def assess_generalization(reports, *, minimum_per_domain=20, minimum_accuracy=.8):
    reports=bounded_tuple(reports,100,label='evaluation reports')
    if type(minimum_per_domain) is not int or minimum_per_domain<1 or type(minimum_accuracy) not in (int,float) or not 0<=minimum_accuracy<=1:
        raise ValueError('Invalid preregistered thresholds')
    if not reports: raise ValueError('Reports required')
    seen=set(); results=[]
    for report in reports:
        payload={k:v for k,v in report.items() if k!='evaluation_id'}
        if fingerprint(payload)!=report['evaluation_id']:
            raise ValueError('Corrupted evaluation')
        tolerance=report['tolerance']
        if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or not 0<=tolerance<=1:
            raise ValueError('Invalid declared tolerance')
        task_ids={row['task_id'] for row in report['results']}
        if len(task_ids)!=len(report['results']) or task_ids&seen:
            raise ValueError('Repeated evaluation tasks')
        seen.update(task_ids)
        if set(report['domains'])!={r['domain'] for r in report['results']} or report['total']!=len(report['results']):
            raise ValueError('Omitted domains or inconsistent total')
        for row in report['results']:
            prediction=row['prediction']
            valid=type(prediction) in (int,float) and math.isfinite(prediction)
            expected=row['expected']
            if type(expected) not in (int,float) or not math.isfinite(expected):
                raise ValueError('Invalid reference value')
            error=abs(prediction-expected) if valid else None
            passed=error is not None and error<=report['tolerance']
            if row['absolute_error']!=error or type(row['passed']) is not bool or row['passed']!=passed:
                raise ValueError('Outcome differs from recorded prediction')
        if report['passed']!=sum(r['passed'] for r in report['results']):
            raise ValueError('Inconsistent aggregate success count')
        for domain,metrics in report['domains'].items():
            rows=[r for r in report['results'] if r['domain']==domain]
            if len(rows)!=metrics['total'] or sum(r['passed'] for r in rows)!=metrics['passed'] or metrics['accuracy']!=metrics['passed']/metrics['total']:
                raise ValueError('Inconsistent domain statistics')
            results.append({'benchmark':report['benchmark'],'domain':domain,
                            'passed':metrics['total']>=minimum_per_domain and metrics['accuracy']>=minimum_accuracy})
    data={'checks':results,'accepted':bool(results) and all(r['passed'] for r in results),
          'minimum_per_domain':minimum_per_domain,'minimum_accuracy':minimum_accuracy,
          'evidence_ids':[r['evaluation_id'] for r in reports], 'external_review_performed':False,
          'scope':'declared benchmark thresholds; not general intelligence or scientific readiness'}
    return {**data,'assessment_id':fingerprint(data)}
