"""Curry–Howard type checking for simply typed lambda/product/sum terms."""
from .proof_theory import formula


def type_check(term,context=None,expected=None):
    context={} if context is None else {k:formula(v) for k,v in context.items()};count=0
    def infer(node,ctx,depth=0):
        nonlocal count
        count+=1
        if count>4096 or depth>64 or not isinstance(node,dict):raise ValueError('Term budget exceeded')
        op=node.get('op')
        if op=='var':
            if node['name'] not in ctx:raise ValueError('Unbound constructive variable')
            return ctx[node['name']]
        if op=='lambda':
            name=node['name']
            if type(name) is not str or not name.isidentifier():raise ValueError('Invalid binder')
            domain=formula(node['type']);return ('imp',domain,infer(node['body'],{**ctx,name:domain},depth+1))
        if op=='apply':
            fun,arg=infer(node['function'],ctx,depth+1),infer(node['argument'],ctx,depth+1)
            if not isinstance(fun,tuple) or fun[0]!='imp' or fun[1]!=arg:raise ValueError('Application type mismatch')
            return fun[2]
        if op=='pair':return ('and',infer(node['left'],ctx,depth+1),infer(node['right'],ctx,depth+1))
        if op in ('fst','snd'):
            pair=infer(node['value'],ctx,depth+1)
            if not isinstance(pair,tuple) or pair[0]!='and':raise ValueError('Projection requires a product')
            return pair[1 if op=='fst' else 2]
        if op in ('inl','inr'):
            value=infer(node['value'],ctx,depth+1);other=formula(node['other_type'])
            return ('or',value,other) if op=='inl' else ('or',other,value)
        if op=='case':
            value=infer(node['value'],ctx,depth+1)
            if not isinstance(value,tuple) or value[0]!='or':raise ValueError('Case requires a sum')
            a=infer(node['left_body'],{**ctx,node['left_name']:value[1]},depth+1)
            b=infer(node['right_body'],{**ctx,node['right_name']:value[2]},depth+1)
            if a!=b:raise ValueError('Case result types differ')
            return a
        if op=='absurd':
            if infer(node['value'],ctx,depth+1)!=('bottom',):raise ValueError('Empty elimination requires bottom')
            return formula(node['type'])
        raise ValueError('Unsupported constructive term')
    result=infer(term,context)
    if expected is not None and result!=formula(expected):raise ValueError('Constructive result type mismatch')
    def portable(v):return [portable(x) for x in v] if isinstance(v,tuple) else v
    return {'type':portable(result),'accepted':True,'nodes':count,'scope':'Simply typed lambda calculus; no dependent universes or general recursion.'}
