"""Small intuitionistic natural-deduction checker, with explicit assumptions.

Proofs are nested trees, not arbitrary code. This is an independently inspectable
finite checker and is not advertised as a Lean kernel certificate.
"""
def formula(value,depth=0):
    if depth>32:raise ValueError('Formula depth exceeded')
    if type(value) is str and value.isidentifier() and not value.startswith('_'):return value
    if isinstance(value,list) and value and value[0]=='bottom' and len(value)==1:return ('bottom',)
    if isinstance(value,list) and len(value)==3 and value[0] in ('and','or','imp'):
        return (value[0],formula(value[1],depth+1),formula(value[2],depth+1))
    raise ValueError('Unsupported propositional formula')


def check_proof(proof,assumptions=(),expected=None,*,max_nodes=4096):
    context=tuple(formula(v) for v in assumptions);visited=0
    def check(node,ctx,depth=0):
        nonlocal visited
        visited+=1
        if visited>max_nodes or depth>64 or not isinstance(node,dict):raise ValueError('Proof tree budget exceeded')
        rule=node.get('rule');children=node.get('premises',[])
        if not isinstance(children,list) or len(children)>3:raise ValueError('Invalid premises')
        if rule=='assumption':
            target=formula(node['formula'])
            if children or target not in ctx:raise ValueError('Undischarged assumption')
            return target
        if rule=='imp_intro':
            if len(children)!=1:raise ValueError('Implication introduction needs one subproof')
            antecedent=formula(node['assumption']);return ('imp',antecedent,check(children[0],ctx+(antecedent,),depth+1))
        values=[check(v,ctx,depth+1) for v in children]
        if rule=='and_intro' and len(values)==2:return ('and',*values)
        if rule in ('and_left','and_right') and len(values)==1 and isinstance(values[0],tuple) and values[0][0]=='and':return values[0][1 if rule=='and_left' else 2]
        if rule=='imp_elim' and len(values)==2 and isinstance(values[0],tuple) and values[0][0]=='imp' and values[0][1]==values[1]:return values[0][2]
        if rule=='or_left' and len(values)==1:return ('or',values[0],formula(node['other']))
        if rule=='or_right' and len(values)==1:return ('or',formula(node['other']),values[0])
        if rule=='or_elim' and len(values)==3:
            disjunction,left,right=values
            if (isinstance(disjunction,tuple) and disjunction[0]=='or' and
                isinstance(left,tuple) and left[0]=='imp' and isinstance(right,tuple) and right[0]=='imp' and
                left[1]==disjunction[1] and right[1]==disjunction[2] and left[2]==right[2]):return left[2]
        if rule=='bottom_elim' and values==[('bottom',)]:return formula(node['formula'])
        raise ValueError('Invalid natural-deduction inference')
    conclusion=check(proof,context)
    if expected is not None and conclusion!=formula(expected):raise ValueError('Proof concludes a different proposition')
    def portable(v):return [portable(x) for x in v] if isinstance(v,tuple) else v
    return {'accepted':True,'conclusion':portable(conclusion),'nodes':visited,'logic':'intuitionistic propositional natural deduction','formal_proof':False}
