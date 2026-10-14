"""Exact elemental balancing for neutral formulas and ideal two-species equilibrium."""
from collections import Counter
from functools import reduce
from fractions import Fraction
import math
import re
from ...core.semantic_ir import rational
from ...math.linear_algebra import Matrix
from ..contracts import result,si,ONE,MOLE


ELEMENTS=frozenset('H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og'.split())

def composition(formula):
    if not isinstance(formula,str) or not formula or len(formula)>128:
        raise ValueError('Fórmula neutra limitada obrigatória')
    tokens=re.findall(r'[A-Z][a-z]?|\d+|[()]',formula)
    if ''.join(tokens)!=formula or len(tokens)>64:
        raise ValueError('Isótopos, cargas e notação desconhecida não suportados')
    stack=[Counter()]; index=0
    while index<len(tokens):
        token=tokens[index]
        if token=='(':
            if len(stack)>=5:
                raise ValueError('Fórmula muito aninhada')
            stack.append(Counter());index+=1;continue
        if token==')':
            if len(stack)==1 or not stack[-1]:
                raise ValueError('Parêntese inválido')
            group=stack.pop()
        elif re.fullmatch(r'[A-Z][a-z]?',token):
            if token not in ELEMENTS:raise ValueError('Elemento químico desconhecido')
            group=Counter({token:1})
        else:
            raise ValueError('Contagem sem elemento')
        index+=1;count=1
        if index<len(tokens) and tokens[index].isdigit():
            count=int(tokens[index]);index+=1
        if not 1<=count<=1000:
            raise ValueError('Contagem atômica fora do limite')
        stack[-1].update({key:value*count for key,value in group.items()})
    if len(stack)!=1 or not stack[0] or max(stack[0].values())>1000000:
        raise ValueError('Fórmula incompleta ou muito grande')
    return dict(sorted(stack[0].items()))


def balance_reaction(reactants,products):
    reactants,products=tuple(reactants),tuple(products)
    if not reactants or not products or len(reactants)+len(products)>16 or len(set(reactants+products))!=len(reactants+products):
        raise ValueError('Reação requer espécies distintas e no máximo 16')
    molecules=[composition(f) for f in reactants+products]
    elements=sorted(set().union(*(set(m) for m in molecules)))
    rows=tuple(tuple(Fraction(m.get(element,0))*(1 if j<len(reactants) else -1) for j,m in enumerate(molecules)) for element in elements)
    reduced,_=Matrix(rows).echelon();pivots={}
    for row in reduced.rows:
        pivot=next((i for i,v in enumerate(row) if v),None)
        if pivot is not None:pivots[pivot]=row
    free=[j for j in range(len(molecules)) if j not in pivots]
    if len(free)!=1:
        raise ValueError('Balanceamento deve ter uma única razão estequiométrica')
    values=[Fraction(0)]*len(molecules);values[free[0]]=1
    for pivot,row in pivots.items():values[pivot]=-row[free[0]]
    denominator=math.lcm(*(v.denominator for v in values));integers=[int(v*denominator) for v in values]
    divisor=reduce(math.gcd,integers)
    coefficients=[v//divisor for v in integers]
    if all(v<0 for v in coefficients):coefficients=[-v for v in coefficients]
    if any(v<=0 for v in coefficients):
        raise ValueError('Não há balanceamento estritamente positivo na orientação dada')
    residuals={element:sum(row[j]*coefficients[j] for j in range(len(molecules))) for element,row in zip(elements,rows)}
    return result('chemistry','neutral_elemental_balance',{'reactants':reactants,'products':products},
                  {'coefficients':coefficients,'element_residuals':residuals},
                  {'coefficients':'stoichiometric_integer','element_residuals':'atoms'},
                  {'all_elements_balanced':all(v==0 for v in residuals.values()),'primitive':reduce(math.gcd,coefficients)==1},
                  'Neutral elemental conservation only; not thermodynamics, kinetics or experimental feasibility.')


def two_species_equilibrium(total_moles,equilibrium_constant):
    n=si(total_moles,MOLE,positive=True);k=si(equilibrium_constant,ONE,positive=True)
    a=n/(1+k);b=n-a
    return result('chemistry','ideal_A_to_B_equilibrium',{'total_moles':total_moles,'equilibrium_constant':equilibrium_constant},
                  {'A':a,'B':b},{'A':'mol','B':'mol'},
                  {'material_balance':a+b==n,'equilibrium_ratio':b/a==k},
                  'Ideal isomerization A <-> B; K supplied externally, no activity corrections or kinetic prediction.')
