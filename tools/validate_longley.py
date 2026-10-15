"""Reproduce exact least squares against pinned NIST StRD certified statistics."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def validate(root):
    from nablamath.core.semantic_ir import rational,fingerprint
    from nablamath.math.statistics.multivariate import exact_least_squares
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name,entry in manifest['files'].items():
        if Path(name).name!=name or hashlib.sha256((root/name).read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Referência externa alterada')
    text=(root/'Longley.dat').read_text(encoding='utf-8');certified={}
    for line in text.splitlines():
        match=re.match(r'\s+B([0-6])\s+([-+\d.Ee]+)\s+',line)
        if match:certified[int(match[1])]=rational(match[2])
    data=text.split('Data:     y',1)[1].splitlines()[1:]
    rows=[tuple(rational(v) for v in line.split()) for line in data if line.strip()]
    if len(rows)!=16 or len(certified)!=7 or any(len(row)!=7 for row in rows):raise ValueError('Perfil Longley inesperado')
    fit=exact_least_squares([row[1:] for row in rows],[row[0] for row in rows])
    errors=[float(abs(a-certified[i])/max(abs(certified[i]),1)) for i,a in enumerate(fit.coefficients)]
    certified_sse=rational('836424.055505915');sse_error=float(abs(fit.residual_sum_squares-certified_sse)/certified_sse)
    passed=max(errors)<5e-12 and sse_error<5e-12
    payload={'schema_version':1,'dataset':manifest['dataset'],'source_commit':manifest['commit'],
             'source_manifest_sha256':hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest(),
             'observations':16,'predictors':6,'coefficients':[str(v) for v in fit.coefficients],
             'certified_estimates':[str(certified[i]) for i in range(7)],'coefficient_relative_errors':errors,
             'residual_sum_squares':str(fit.residual_sum_squares),'certified_sse':str(certified_sse),
             'sse_relative_error':sse_error,'r_squared':str(fit.r_squared),'passed':passed,
             'scope':'published observed-data numerical benchmark; not out-of-sample, causal, physical or novelty validation'}
    return {**payload,'evaluation_id':fingerprint(payload)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    result=validate(root/'benchmarks/fixtures/longley-nist')
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({'passed':result['passed'],'max_coefficient_relative_error':max(result['coefficient_relative_errors']),'sse_relative_error':result['sse_relative_error']}))
    raise SystemExit(0 if result['passed'] else 1)
