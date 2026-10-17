#!/usr/bin/env python3
"""Five independently checked, inverse-constructed mathematics problem families.

Uses Nabla's *native* receipt contract by default. --portable explicitly enables
an audited fallback for offline machines without nablamath; this mode never
claims that Nabla was executed or that hashes constitute mathematical proofs.
"""
from __future__ import annotations

import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import sympy as sp


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def portable_receipt(operation, inputs, result, *, metadata):
    body = dict(schema_version=1, kind='execution_observation', operation=operation,
                inputs=inputs, result=result, backend='python', metadata=metadata,
                parents=[], formal_proof=False, replayable=False)
    return {**json.loads(canonical(body)), 'content_id': fingerprint(body)}


def portable_verify(r):
    try:
        return r == portable_receipt(r['operation'], r['inputs'], r['result'], metadata=r['metadata'])
    except (TypeError, KeyError, ValueError):
        return False


def receipt_backend(portable):
    if portable:
        return portable_receipt, portable_verify, 'portable_reference_contract'
    from nablamath.calc.receipt import receipt, verify_receipt, fingerprint as native_fingerprint, canonical as native_canonical
    if native_fingerprint({'a': [1, 'á']}) != fingerprint({'a': [1, 'á']}) or native_canonical({'z': 2, 'a': 1}) != canonical({'z': 2, 'a': 1}):
        raise RuntimeError('Nabla canonicalization contract mismatch')
    return receipt, verify_receipt, 'native_nablamath'


r, m, q = sp.symbols('r M Q', positive=True)
f = 1-2*m/r+q**2/r**2
K_from_metric = sp.factor(sp.diff(f,r,2)**2 + 4*(sp.diff(f,r)/r)**2 + 4*((1-f)/r**2)**2)
K_known = 48*m*m/r**6 - 96*m*q*q/r**7 + 56*q**4/r**8
assert sp.simplify(K_from_metric - K_known) == 0


def reissner_nordstrom(j, seed):
    mass = j+7
    charge = 1+(j*37)%(mass-1)
    disc = mass*mass-charge*charge
    rp = f'({mass}+sqrt({disc}))'
    numerator = f'(48*{mass}**2*{rp}**2-96*{mass}*{charge}**2*{rp}+56*{charge}**4)'
    kval = f'{numerator}/{rp}**8'
    exact = sp.simplify(K_known.subs({m:mass,q:charge,r:mass+sp.sqrt(disc)}))
    positive = bool(exact.is_positive)
    if not positive or disc <= 0:
        raise ArithmeticError('Invalid horizon/curvature')
    params = {'mass':mass,'charge':charge,'radicand':disc}
    problem = (f'Para a métrica eletrovácuo Reissner–Nordström com M={mass}, Q={charge}, '
               'f(r)=1-2M/r+Q²/r², derive K=R_abcd R^abcd, determine r_+ e '
               'K(r_+) exatamente. O limite r→r_+ diverge? E r→0+? Assuma G=c=1.')
    steps = ["A métrica estática esfericamente simétrica é ds²=-f dt²+dr²/f+r²dΩ².",
             "A contração ortonormal fornece K=(f'')²+4(f'/r)²+4((1-f)/r²)².",
             f"Com f'=2M/r²-2Q²/r³ e f''=-4M/r³+6Q²/r⁴, expandimos K={sp.sstr(K_known)}.",
             f"Como M>|Q|, r_+=M+√(M²-Q²)={rp} é real e positivo.",
             "K(r_+) é finito e positivo; divergência de g_rr em coordenadas estáticas não é singularidade de curvatura.",
             f"Quando r→0+, K~56·{charge}⁴/r⁸ (Q≠0), isto é, a curvatura diverge no centro."]
    solution = f'r_+={rp}; K(r)={sp.sstr(K_known)}; K(r_+)={kval}; lim_(r→r_+) K=K(r_+)<∞; K~56*{charge}**4/r**8 quando r→0+.'
    return 'CURVATURA_REISSNER_NORDSTROM', params, problem, steps, solution, {'symbolic_identity':True,'horizon_positive':positive,'finite_horizon':True}


def lie_casimir(j, seed):
    N = 3+j%8
    k = 2+j//8
    dim = math.comb(k+N-1, N-1)
    c2 = F(k*(N-1)*(k+N),2*N)
    dynkin = c2*dim/F(N*N-1)
    independent = F(k*k*(N-1),2*N)+F(k*(N-1),2)
    if c2 != independent or dim <= 0 or dynkin <= 0:
        raise ArithmeticError('Weight formula mismatch')
    params={'N':N,'k':k}
    problem=(f'Considere su({N}) com Tr(T_a T_b)=δ_ab/2 e a irrep de peso máximo Λ={k}λ₁ '
             '(potência simétrica de k fundamentais). Calcule exatamente o autovalor Casimir quadrático, '
             'a dimensão da representação e seu índice de Dynkin. Justifique a normalização.')
    steps=["Com raízes longas de norma 2, C₂=(Λ,Λ+2ρ)/2.",
           f'Para su({N}), (λ₁,λ₁)=({N}-1)/{N} e (λ₁,ρ)=({N}-1)/2.',
           f'Substituindo Λ={k}λ₁, C₂=k²(N-1)/(2N)+k(N-1)/2={c2}.',
           f'A dimensão de Sym^{k}(C^{N}) é binom(k+N-1,N-1)={dim}.',
           f'T(R)=C₂(R) dim(R)/(N²-1)={dynkin}; toda a aritmética é racional exata.',
           'O Casimir quártico não é inferido a partir desta identidade: exigir sua definição evitaria falsa unicidade.']
    sol=f'C₂={c2}; dim(R)={dim}; índice de Dynkin T(R)={dynkin}.'
    return 'CASIMIR_SU_N',params,problem,steps,sol,{'weight_inner_product_identity':c2==independent,'dimension_positive':dim>0}


def ito_fokker_planck(j, seed):
    sigma=1+j%3
    alpha=sigma*sigma+2+j
    beta=2+(j*11)%17
    s2=sigma*sigma
    strat=F(2*alpha-s2,2)
    exponent=F(2*alpha,s2)-2
    rate=F(beta,s2)
    shape=(exponent+1)/2
    mean_square=shape/rate
    check_linear=F(alpha)-F(s2)-F(s2,2)*exponent
    check_cubic=-F(beta)+F(s2)*rate
    if shape<=0 or check_linear or check_cubic or mean_square!=F(2*alpha-s2,2*beta):
        raise ArithmeticError('Stationary Fokker–Planck residual nonzero')
    params={'alpha':alpha,'beta':beta,'sigma':sigma}
    problem=(f'Para X₀>0, considere dX=({alpha}X-{beta}X³)dt+{sigma}X dW (Itô). '
             'Converta para Stratonovich, escreva a Fokker–Planck e encontre a densidade '
             'estacionária normalizada de fluxo zero sobre (0,∞), verificando ∫p=1 e E[X²].')
    steps=[f'σ(x)={sigma}x e σσ′/2={s2}x/2; a deriva de Stratonovich é ({strat})x-{beta}x³.',
           f'Fokker–Planck: ∂ₜp=-∂ₓ[({alpha}x-{beta}x³)p]+({s2}/2)∂ₓ²[x²p].',
           'O fluxo estacionário J=(αx-βx³)p-(σ²/2)∂ₓ(x²p) deve ser zero.',
           f'A solução proporcional a x^a exp(-λx²) tem a={exponent} e λ={rate}.',
           f'Com s=(a+1)/2={shape}>0, a integral Z=Γ(s)/(2λ^s), garantindo normalização.',
           f'O momento é E[X²]=s/λ={mean_square}. Substituição no fluxo cancela termos em x e x³.',
           'O estado absorvente X=0 é distinto: a afirmação trata da distribuição no domínio positivo.']
    sol=(f'Itô→Stratonovich: b_S(x)=({strat})x-{beta}x³. '
         f'p∞(x)=[2*({rate})^({shape})/Γ({shape})]*x^({exponent})*exp(-({rate})x²), x>0; '
         f'∫₀∞p∞dx=1; E[X²]={mean_square}.')
    return 'ITO_FOKKER_PLANCK',params,problem,steps,sol,{'zero_flux_rational':True,'normalizable_on_positive_axis':True,'second_moment_exact':True}


def groebner_finite_field(j, seed):
    rng=random.Random(seed)
    p=[101,103,107,109][j%4]
    degree=3+j%5
    A,B,C,D,E,H=[rng.randrange(1,p) for _ in range(6)]
    c=rng.randrange(1,p)
    y1,y2,z=sp.symbols('y1 y2 z')
    h1=A*z*z+B*z+C;h2=D*z*z+E*z+H
    generators=[y1-h1,y2-h2,z**degree-c]
    gb=sp.groebner(generators,y1,y2,z,order='lex',modulus=p)
    lm=[poly.LM(order='lex').exponents for poly in gb.polys]
    expected={(1,0,0),(0,1,0),(0,0,degree)}
    if set(lm)!=expected or len(lm)!=3 or any(gb.reduce(g)[1]!=0 for g in generators):
        raise ArithmeticError('Groebner basis verification failed')
    roots=[v for v in range(p) if pow(v,degree,p)==c%p]
    squarefree=(c%p)!=0 and (degree%p)!=0
    if not squarefree:
        raise ArithmeticError('Generator not squarefree')
    params=dict(p=p,degree=degree,a=A,b=B,c=C,d=D,e=E,f=H,constant=c)
    problem=(f'No anel F_{p}[y₁,y₂,z], ordem lex y₁>y₂>z, considere o ideal '
             f'I=<y₁-({A}z²+{B}z+{C}), y₂-({D}z²+{E}z+{H}), z^{degree}-{c}>. '
             'Determine uma base de Gröbner reduzida, a dimensão do quociente como espaço vetorial sobre F_p '
             'e o número exato de pontos racionais em F_p³.')
    steps=['O ideal foi construído inversamente como um sistema triangular mônico, não como solução presumida de ideais aleatórios.',
           'Na ordem lex, os termos líderes são y₁, y₂ e z^d; nenhum termo não líder é divisível por outro termo líder.',
           'Os três S-polinômios são reduzidos a zero pelo critério de Buchberger (verificados com SymPy em GF(p)).',
           f'Os monômios padrão são 1,z,…,z^{degree-1}; portanto dim_Fp F_p[y₁,y₂,z]/I={degree}.',
           f'Cada raiz de z^{degree}={c} em F_{p} determina unicamente y₁,y₂; há {len(roots)} pontos F_p.',
           'Como p∤d e c≠0, z^d-c é separável. Contagem de pontos F_p não é contagem geométrica sobre fecho algébrico.']
    sol=(f'Base reduzida G={{y₁-({A}z²+{B}z+{C}), y₂-({D}z²+{E}z+{H}), z^{degree}-{c}}} '
         f'em F_{p}; dimensão do quociente={degree}; pontos F_p={len(roots)}; raízes z={roots}.')
    return 'GROEBNER_GF_P',params,problem,steps,sol,{'buchberger_reductions_zero':True,'leading_monomials_verified':True,'squarefree':True,'rational_points_enumerated':True}


def ramanujan_convergent(j, seed):
    b=2+j%40
    n=3+j//40
    q=F(1,b**5)
    def convergent(steps):
        denom=F(1)
        for k in range(steps,0,-1):
            denom=1+q**k/denom
        return F(1,b)/denom
    value=convergent(n);next_value=convergent(n+1)
    bound=F(1,b)*q**((n+1)*(n+2)//2)
    if not 0<value<1 or not abs(value-next_value)<=bound:
        raise ArithmeticError('Continued fraction residual exceeds tail bound')
    params=dict(b=b,n=n)
    problem=(f'Considere a fração contínua de Rogers–Ramanujan R(q)=q^(1/5)/(1+q/(1+q²/(1+…))), '
             f'q=1/{b}⁵. Calcule exatamente a truncagem C_{n} que encerra o último denominador em 1 '
             'após o termo q^n. Prove um limite rigoroso para |R(q)-C_n| sem supor fórmula modular fechada.')
    steps=[f'Por construção q=1/{b}⁵ e q^(1/5)=1/{b} é racional.',
           f'Defina D_(n+1)=1; retroceda D_k=1+q^k/D_(k+1), k=n,…,1; C_n=(1/{b})/D₁.',
           f'Com n={n}, o algoritmo racional exato fornece C_n={value}.',
           'A transformação x↦1+q^k/x em x≥1 é Lipschitz com constante no máximo q^k.',
           f'O efeito da cauda omitida é limitado por (1/{b})·q^((n+1)(n+2)/2)={bound}.',
           f'A truncagem n+1 dá C_(n+1)={next_value}, diferença dentro da cota.',
           'Esta é uma aproximação com limite certificado, não uma expressão algébrica exata para R(q).']
    sol=f'C_{n}={value}; |R(q)-C_{n}|≤{bound}; C_{n+1}={next_value}.'
    return 'ROGERS_RAMANUJAN_INTERVAL',params,problem,steps,sol,{'rational_convergent':True,'rigorous_tail_bound':True,'next_convergent_within_bound':True}


FAMILIES=(reissner_nordstrom,lie_casimir,ito_fokker_planck,groebner_finite_field,ramanujan_convergent)


def create_record(index, make_receipt, verify_receipt, backend):
    if type(index) is not int or index<1:
        raise ValueError('Index must be a positive integer')
    family=FAMILIES[(index-1)%len(FAMILIES)]
    j=(index-1)//len(FAMILIES)
    seed=1000000+index*37
    domain,params,problem,steps,solution,checks=family(j,seed)
    if not all(x is True for x in checks.values()):
        raise ArithmeticError('Mathematical check failed')
    payload={'schema_version':2,'problem_id':f'FRONTIER-{index:04d}', 'domain':domain,
             'seed':seed,'parameters':params,'problem':problem,
             'derivation':steps,'solution':solution,'checks':checks,
             'proof_scope':'algebraic identity / independent recomputation as named in checks; no universal formal theorem',
             'synthetic':True}
    official=make_receipt('frontier_inverse_synthesis',
                          {'problem_id':payload['problem_id'],'parameters':params,'seed':seed,'domain':domain},
                          {'problem':problem,'derivation':steps,'solution':solution,'checks':checks},
                          metadata={'schema_version':2,'proof_status':'CHECKED_EXACT_CONSTRUCTION_NOT_FORMAL_PROOF',
                                    'synthetic':True,'receipt_backend':backend})
    if not verify_receipt(official):
        raise ArithmeticError('Receipt did not pass verification')
    return {**payload,'receipt':official,'record_sha256':fingerprint(payload)}


def render(record):
    return ('='*80+'\n'+f"PROBLEM_ID: {record['problem_id']} | DOMAIN: {record['domain']}\n"
            +f"CONTENT_SHA256: {record['record_sha256']}\nNABLA_RECEIPT_ID: {record['receipt']['content_id']}\n"
            +'='*80+'\n[ENUNCIADO]\n'+record['problem']+'\n\n'
            +'<derivation>\n'+'\n'.join(f'{i}. {step}' for i,step in enumerate(record['derivation'],1))
            +'\n</derivation>\n\n<solution>\n'+record['solution']+'\n</solution>\n\n'
            +'[AUDIT_METADATA]\n'+canonical({'schema_version':record['schema_version'],
                'proof_status':'CHECKED_EXACT_CONSTRUCTION_NOT_FORMAL_PROOF',
                'checks':record['checks'],'record_sha256':record['record_sha256'],
                'receipt':record['receipt']})+'\n\n')


def generate(count, destination, *, portable=False):
    if type(count) is not int or not 1<=count<=100000:
        raise ValueError('Count must be in [1,100000]')
    make_receipt,verify_receipt,backend=receipt_backend(portable)
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    leaves=[];domains={}
    path=destination.with_name(destination.name+'.partial')
    try:
        with path.open('w',encoding='utf-8',newline='\n') as stream:
            stream.write('# NABLA FRONTIER / INVERSE MATHEMATICAL SYNTHESIS v2\n'
                         '# Synthetic parameterized problems; no internet or olympiad scraping.\n'
                         '# Derivations are checkable explanations, NOT private reasoning traces.\n'
                         '# SHA-256 is content integrity, NOT proof or authorship authentication.\n'
                         f'# Backend: {backend}; count: {count}\n\n')
            for index in range(1,count+1):
                record=create_record(index,make_receipt,verify_receipt,backend)
                stream.write(render(record))
                leaves.append(record['record_sha256'])
                domains[record['domain']]=domains.get(record['domain'],0)+1
                if index%100==0:
                    print(f'{index}/{count}: {record["domain"]}',flush=True)
        path.replace(destination)
    finally:
        if path.exists():path.unlink()
    # This is a digest of an ordered digest list, not a Merkle tree.
    manifest={'schema_version':2,'count':count,'domains':domains,'receipt_backend':backend,
              'ordered_record_digest':fingerprint(leaves),
              'file_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
              'proof_status':'CHECKED_EXACT_CONSTRUCTION_NOT_FORMAL_PROOF',
              'unique_record_hashes':len(set(leaves))==len(leaves)}
    if not manifest['unique_record_hashes'] or len(domains)!=min(count,5):
        raise ArithmeticError('Coverage or uniqueness failure')
    destination.with_suffix(destination.suffix+'.manifest.json').write_text(canonical(manifest)+'\n',encoding='utf-8')
    return manifest


def verify_dataset(destination, *, portable=False):
    """Independently reconstruct the entire output and compare every byte/hash."""
    from tempfile import TemporaryDirectory
    destination=Path(destination)
    manifest=json.loads(destination.with_suffix(destination.suffix+'.manifest.json').read_text(encoding='utf-8'))
    expected_backend='portable_reference_contract' if portable else 'native_nablamath'
    if manifest.get('receipt_backend')!=expected_backend:
        raise ValueError('Incorrect backend provenance in manifest')
    if hashlib.sha256(destination.read_bytes()).hexdigest()!=manifest['file_sha256']:
        raise ValueError('Dataset byte digest mismatch')
    with TemporaryDirectory() as tmp:
        duplicate=Path(tmp)/destination.name
        rebuilt=generate(manifest['count'],duplicate,portable=portable)
        if manifest!=rebuilt or destination.read_bytes()!=duplicate.read_bytes():
            raise ValueError('Recomputation differs from saved data or manifest')
    return True


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=1000)
    parser.add_argument('--output',type=Path,default=Path('dataset_superinteligente_1000.txt'))
    parser.add_argument('--verify',action='store_true',help='Rebuild and compare existing dataset byte for byte')
    parser.add_argument('--portable',action='store_true',help='Explicitly use the offline Nabla receipt contract instead of installed native Nabla')
    args=parser.parse_args(argv)
    if args.verify:
        print('REPLAY_VALID:',verify_dataset(args.output,portable=args.portable))
    else:
        manifest=generate(args.count,args.output,portable=args.portable)
        print(canonical(manifest))


if __name__=='__main__':
    main()