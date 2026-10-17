"""Finite diagrams of rational vector spaces and Cech complexes.

The input cover/intersection labels and restriction maps are explicit hypotheses.
Computing their cohomology does not assert that a geometric cover is acyclic.
"""
from itertools import combinations
from .._structured import rational_matrix,sympy,data
from ..algebra.homological import chain_complex


def _diagram(dimensions,restrictions):
    sp=sympy()
    if not isinstance(dimensions,dict) or not 1<=len(dimensions)<=64 or any(type(k) is not str or type(v) is not int or not 1<=v<=16 for k,v in dimensions.items()):raise ValueError('Invalid stalk dimensions')
    maps={}
    for record in restrictions:
        if set(record)!={'from','to','matrix'}:raise ValueError('Closed restriction record required')
        a,b=record['from'],record['to']
        if a not in dimensions or b not in dimensions or (a,b) in maps:raise ValueError('Invalid restriction endpoints')
        m=rational_matrix(record['matrix'],maximum=16)
        if m.shape!=(dimensions[b],dimensions[a]):raise ValueError('Restriction dimension mismatch')
        maps[a,b]=m
    for (a,b),ab in maps.items():
        if a==b and ab!=sp.eye(dimensions[a]):raise ValueError('Restriction identity fails')
        for (c,d),cd in maps.items():
            if b==c and (a,d) in maps and maps[a,d]!=cd*ab:raise ValueError('Restriction composition fails')
    return maps


def global_sections(dimensions,restrictions):
    sp=sympy();maps=_diagram(dimensions,restrictions);labels=list(dimensions);offset={};n=0
    for label in labels:offset[label]=n;n+=dimensions[label]
    if n>128:raise ValueError('Global section dimension budget exceeded')
    equations=[]
    for (a,b),m in maps.items():
        for i in range(dimensions[b]):
            row=[sp.Integer(0)]*n;row[offset[b]+i]=1
            for j in range(dimensions[a]):row[offset[a]+j]-=m[i,j]
            equations.append(row)
    system=sp.Matrix(equations) if equations else sp.zeros(0,n)
    basis=system.nullspace()
    return {'dimension':len(basis),'basis':data(basis),'coordinate_order':labels,'offsets':offset}


def cech_cohomology(cover_size,intersections,dimensions,restrictions):
    sp=sympy();maps=_diagram(dimensions,restrictions)
    if type(cover_size) is not int or not 1<=cover_size<=6:raise ValueError('Cover size must be 1–6')
    cells=[]
    for degree in range(cover_size):
        cells.append([(c,intersections[','.join(map(str,c))]) for c in combinations(range(cover_size),degree+1) if ','.join(map(str,c)) in intersections])
    if any(label not in dimensions for group in cells for c,label in group):raise ValueError('Missing section space on intersection')
    sizes=[sum(dimensions[label] for _,label in group) for group in cells]
    if sum(sizes)>128:raise ValueError('Cech complex dimension budget exceeded')
    ds=[]
    for k in range(len(cells)-1):
        differential=sp.zeros(sizes[k+1],sizes[k]);out_offset=0
        offsets={};offset=0
        for cell,label in cells[k]:offsets[cell]=offset;offset+=dimensions[label]
        for cell,label in cells[k+1]:
            for removed in range(len(cell)):
                face=cell[:removed]+cell[removed+1:]
                if face not in offsets:raise ValueError('Intersection nerve must be downward closed')
                source=intersections[','.join(map(str,face))]
                restriction=sp.eye(dimensions[label]) if source==label else maps.get((source,label))
                if restriction is None:raise ValueError('Missing Cech restriction')
                i,j=out_offset,offsets[face]
                differential[i:i+dimensions[label],j:j+dimensions[source]]+=(-1)**removed*restriction
            out_offset+=dimensions[label]
        ds.append(differential)
    if any(ds[i+1]*ds[i]!=sp.zeros(ds[i+1].rows,ds[i].cols) for i in range(len(ds)-1)):raise ValueError('Cech differential squared is nonzero')
    ranks=[0]+[d.rank() for d in ds]+[0]
    return {'dimensions':[n-ranks[i]-ranks[i+1] for i,n in enumerate(sizes)],'differentials':data(ds),
            'scope':'Cohomology of the supplied finite Cech diagram; no automatic sheaf cohomology comparison.'}
