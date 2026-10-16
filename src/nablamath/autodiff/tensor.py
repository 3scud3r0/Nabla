"""Small dependency-free dense tensor reverse-mode backend.

This is the reference/correctness backend for NablaMath: multidimensional dense
storage, NumPy-style broadcasting, reverse-mode gradients, reductions, reshape,
transpose, matrix multiplication and named axes.  It deliberately does not
pretend to be a GPU backend; compiler/device lowering can target the same API.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import exp as _exp, isfinite, log as _log, prod, tanh as _tanh
from typing import Callable, Iterable, Sequence

Shape = tuple[int, ...]
Index = tuple[int, ...]


def _numel(shape: Shape) -> int: return prod(shape) if shape else 1

def _strides(shape: Shape) -> Shape:
    result=[]; running=1
    for size in reversed(shape): result.append(running); running*=size
    return tuple(reversed(result))

def _indices(shape: Shape):
    if not shape: yield (); return
    yield from product(*(range(size) for size in shape))

def _offset(index: Index, shape: Shape) -> int:
    return sum(i*s for i,s in zip(index,_strides(shape)))

def _infer(value) -> tuple[Shape, tuple[float,...]]:
    if isinstance(value,(int,float)):
        number=float(value)
        if not isfinite(number): raise ValueError("Tensor exige valores finitos")
        return (), (number,)
    if not isinstance(value,(list,tuple)) or not value: raise ValueError("Tensor exige escalar ou sequência retangular não vazia")
    child=[_infer(item) for item in value]; sub=child[0][0]
    if any(shape!=sub for shape,_ in child): raise ValueError("Dados de tensor precisam ser retangulares")
    return (len(value),)+sub, tuple(x for _,flat in child for x in flat)

def _unflatten(flat: Sequence[float], shape: Shape):
    if not shape: return float(flat[0])
    if len(shape)==1: return [float(x) for x in flat]
    chunk=_numel(shape[1:]); return [_unflatten(flat[i*chunk:(i+1)*chunk],shape[1:]) for i in range(shape[0])]

def _broadcast_shape(a: Shape,b: Shape) -> Shape:
    out=[]
    for i in range(1,max(len(a),len(b))+1):
        da=a[-i] if i<=len(a) else 1; db=b[-i] if i<=len(b) else 1
        if da!=db and da!=1 and db!=1: raise ValueError(f"Shapes incompatíveis para broadcasting: {a} e {b}")
        out.append(max(da,db))
    return tuple(reversed(out))

def _project(index: Index, source: Shape, target: Shape) -> Index:
    if not source: return ()
    pad=len(target)-len(source); result=[]
    for i,size in enumerate(source):
        value=index[pad+i]; result.append(0 if size==1 else value)
    return tuple(result)

Backward = Callable[[Sequence[float]], list[float]]

class Tensor:
    __slots__=("_flat","shape","requires_grad","_parents","op","_grad")
    def __init__(self, data, *, requires_grad: bool=False, _shape: Shape|None=None,
                 _parents: tuple[tuple["Tensor",Backward],...]=(), _op: str="leaf") -> None:
        if _shape is None: shape,flat=_infer(data)
        else:
            shape=_shape; flat=tuple(float(x) for x in data)
            if len(flat)!=_numel(shape): raise ValueError("Quantidade de dados não corresponde ao shape")
            if not all(isfinite(x) for x in flat): raise ValueError("Tensor exige valores finitos")
        self._flat=flat; self.shape=shape; self.requires_grad=bool(requires_grad); self._parents=_parents if self.requires_grad else (); self.op=_op; self._grad=[0.0]*len(flat)
    @classmethod
    def _from_flat(cls,flat:Sequence[float],shape:Shape,requires_grad:bool,parents=(),op="op") -> "Tensor": return cls(flat,requires_grad=requires_grad,_shape=shape,_parents=tuple(parents),_op=op)
    @property
    def ndim(self)->int:return len(self.shape)
    @property
    def size(self)->int:return len(self._flat)
    @property
    def grad(self): return _unflatten(self._grad,self.shape)
    def tolist(self): return _unflatten(self._flat,self.shape)
    def item(self)->float:
        if self.size!=1: raise ValueError("item() exige tensor escalar")
        return self._flat[0]
    def detach(self)->"Tensor": return Tensor._from_flat(self._flat,self.shape,False)
    @staticmethod
    def _coerce(other)->"Tensor": return other if isinstance(other,Tensor) else Tensor(other)
    def _binary(self,other,forward:Callable[[float,float],float],da:Callable[[float,float],float],db:Callable[[float,float],float],op:str)->"Tensor":
        b=self._coerce(other); out_shape=_broadcast_shape(self.shape,b.shape); out=[]; mapping=[]
        for idx in _indices(out_shape):
            ia=_project(idx,self.shape,out_shape); ib=_project(idx,b.shape,out_shape); oa=_offset(ia,self.shape); ob=_offset(ib,b.shape); a_val=self._flat[oa]; b_val=b._flat[ob]
            value=forward(a_val,b_val)
            if not isfinite(value): raise ValueError(f"Resultado não finito em {op}")
            out.append(value); mapping.append((oa,ob,a_val,b_val))
        parents=[]
        if self.requires_grad:
            def back_a(g,mapping=mapping,size=self.size):
                result=[0.0]*size
                for go,(oa,ob,av,bv) in zip(g,mapping): result[oa]+=go*da(av,bv)
                return result
            parents.append((self,back_a))
        if b.requires_grad:
            def back_b(g,mapping=mapping,size=b.size):
                result=[0.0]*size
                for go,(oa,ob,av,bv) in zip(g,mapping): result[ob]+=go*db(av,bv)
                return result
            parents.append((b,back_b))
        return Tensor._from_flat(out,out_shape,bool(parents),parents,op)
    def __add__(self,other): return self._binary(other,lambda a,b:a+b,lambda a,b:1.0,lambda a,b:1.0,"add")
    __radd__=__add__
    def __neg__(self): return self._unary(lambda x:-x,lambda x:-1.0,"neg")
    def __sub__(self,other): return self+(-self._coerce(other))
    def __rsub__(self,other): return self._coerce(other)-self
    def __mul__(self,other): return self._binary(other,lambda a,b:a*b,lambda a,b:b,lambda a,b:a,"mul")
    __rmul__=__mul__
    def __truediv__(self,other):
        b=self._coerce(other)
        if any(x==0 for x in b._flat): raise ZeroDivisionError("divisão tensorial por zero")
        return self._binary(b,lambda a,c:a/c,lambda a,c:1/c,lambda a,c:-a/(c*c),"div")
    def __rtruediv__(self,other): return self._coerce(other)/self
    def __pow__(self,exponent:int):
        if type(exponent) is not int or exponent < -32 or exponent > 32: raise ValueError("Potência tensorial exige inteiro entre -32 e 32")
        if exponent<=0 and any(x==0 for x in self._flat): raise ZeroDivisionError("potência fora do domínio")
        return self._unary(lambda x:x**exponent,lambda x:0.0 if exponent==0 else exponent*x**(exponent-1),f"pow:{exponent}")
    def _unary(self,forward:Callable[[float],float],derivative:Callable[[float],float],op:str)->"Tensor":
        out=[forward(x) for x in self._flat]
        if not all(isfinite(x) for x in out): raise ValueError(f"Resultado não finito em {op}")
        parents=[]
        if self.requires_grad:
            parents.append((self,lambda g,vals=self._flat:[go*derivative(x) for go,x in zip(g,vals)]))
        return Tensor._from_flat(out,self.shape,bool(parents),parents,op)
    def exp(self): return self._unary(_exp,_exp,"exp")
    def log(self):
        if any(x<=0 for x in self._flat): raise ValueError("log tensorial exige valores positivos")
        return self._unary(_log,lambda x:1/x,"log")
    def tanh(self): return self._unary(_tanh,lambda x:1-_tanh(x)**2,"tanh")
    def sum(self,axis:int|None=None,keepdims:bool=False)->"Tensor":
        if (axis is not None and type(axis) is not int) or type(keepdims) is not bool: raise ValueError("Eixo inteiro e keepdims booleano obrigatórios")
        if axis is None:
            total=sum(self._flat); out_shape=self.shape if False else (() if not keepdims else tuple(1 for _ in self.shape)); out=[total]
            parents=[]
            if self.requires_grad: parents.append((self,lambda g,size=self.size:[g[0]]*size))
            return Tensor._from_flat(out,out_shape,bool(parents),parents,"sum")
        axis=axis if axis>=0 else self.ndim+axis
        if not 0<=axis<self.ndim: raise ValueError("Eixo inválido")
        out_shape=self.shape[:axis]+((1,) if keepdims else ())+self.shape[axis+1:]
        buckets=[0.0]*_numel(out_shape); source_to_out=[]
        for idx in _indices(self.shape):
            out_idx=idx[:axis]+((0,) if keepdims else ())+idx[axis+1:]; oi=_offset(out_idx,out_shape); si=_offset(idx,self.shape); buckets[oi]+=self._flat[si]; source_to_out.append(oi)
        parents=[]
        if self.requires_grad:
            parents.append((self,lambda g,map_=tuple(source_to_out):[g[oi] for oi in map_]))
        return Tensor._from_flat(buckets,out_shape,bool(parents),parents,"sum")
    def mean(self,axis:int|None=None,keepdims:bool=False)->"Tensor":
        if (axis is not None and (type(axis) is not int or not -self.ndim <= axis < self.ndim)) or type(keepdims) is not bool: raise ValueError("Eixo ou keepdims inválido")
        count=self.size if axis is None else self.shape[axis if axis>=0 else self.ndim+axis]
        return self.sum(axis,keepdims)/count
    def reshape(self,*shape:int)->"Tensor":
        if len(shape)==1 and isinstance(shape[0],(tuple,list)): shape=tuple(shape[0])
        if any(type(x) is not int for x in shape): raise ValueError("reshape exige dimensões inteiras explícitas")
        shape=tuple(shape)
        if any(x<=0 for x in shape) or _numel(shape)!=self.size: raise ValueError("reshape incompatível")
        parents=[]
        if self.requires_grad: parents.append((self,lambda g:list(g)))
        return Tensor._from_flat(self._flat,shape,bool(parents),parents,"reshape")
    def transpose(self,axes:Sequence[int]|None=None)->"Tensor":
        axes=tuple(reversed(range(self.ndim))) if axes is None else tuple(axes)
        if any(type(axis) is not int for axis in axes) or sorted(axes)!=list(range(self.ndim)): raise ValueError("Permutação de eixos inválida")
        out_shape=tuple(self.shape[a] for a in axes); out=[0.0]*self.size; out_to_in=[0]*self.size
        for out_idx in _indices(out_shape):
            in_idx=[0]*self.ndim
            for out_axis,in_axis in enumerate(axes): in_idx[in_axis]=out_idx[out_axis]
            oi=_offset(out_idx,out_shape); ii=_offset(tuple(in_idx),self.shape); out[oi]=self._flat[ii]; out_to_in[oi]=ii
        parents=[]
        if self.requires_grad:
            def back(g,map_=tuple(out_to_in),size=self.size):
                result=[0.0]*size
                for oi,ii in enumerate(map_): result[ii]+=g[oi]
                return result
            parents.append((self,back))
        return Tensor._from_flat(out,out_shape,bool(parents),parents,"transpose")
    @property
    def T(self): return self.transpose()
    def matmul(self,other)->"Tensor":
        b=self._coerce(other)
        if self.ndim!=2 or b.ndim!=2 or self.shape[1]!=b.shape[0]: raise ValueError("matmul de referência suporta matrizes 2D compatíveis")
        m,k=self.shape; _,n=b.shape; out=[]
        for i in range(m):
            for j in range(n): out.append(sum(self._flat[i*k+t]*b._flat[t*n+j] for t in range(k)))
        parents=[]
        if self.requires_grad:
            def back_a(g,a=self,b=b,m=m,k=k,n=n):
                result=[0.0]*(m*k)
                for i in range(m):
                    for t in range(k): result[i*k+t]=sum(g[i*n+j]*b._flat[t*n+j] for j in range(n))
                return result
            parents.append((self,back_a))
        if b.requires_grad:
            def back_b(g,a=self,b=b,m=m,k=k,n=n):
                result=[0.0]*(k*n)
                for t in range(k):
                    for j in range(n): result[t*n+j]=sum(a._flat[i*k+t]*g[i*n+j] for i in range(m))
                return result
            parents.append((b,back_b))
        return Tensor._from_flat(out,(m,n),bool(parents),parents,"matmul")
    def __matmul__(self,other):
        if not isinstance(other, (Tensor, int, float, list, tuple)):
            return NotImplemented
        return self.matmul(other)
    def _topological(self):
        order = []
        seen = set()
        stack = [(self, False)]
        while stack:
            node, expanded = stack.pop()
            marker = id(node)
            if expanded:
                order.append(node)
                continue
            if marker in seen:
                continue
            seen.add(marker)
            stack.append((node, True))
            for parent, _ in reversed(node._parents):
                if id(parent) not in seen:
                    stack.append((parent, False))
        return order
    def backward(self,gradient=None)->None:
        order=self._topological()
        for node in order: node._grad=[0.0]*node.size
        if gradient is None:
            if self.size!=1: raise ValueError("Saída não escalar exige gradiente/cotangente explícito")
            seed=[1.0]
        elif isinstance(gradient,Tensor):
            if gradient.shape!=self.shape: raise ValueError("Cotangente com shape incorreto")
            seed=list(gradient._flat)
        else:
            seed_shape,seed_flat=_infer(gradient)
            if seed_shape!=self.shape: raise ValueError("Cotangente com shape incorreto")
            seed=list(seed_flat)
        self._grad=seed
        for node in reversed(order):
            for parent,back in node._parents:
                contribution=back(node._grad)
                if len(contribution)!=parent.size: raise RuntimeError("Backward interno retornou shape inválido")
                parent._grad=[a+b for a,b in zip(parent._grad,contribution)]

@dataclass(frozen=True)
class NamedTensor:
    tensor: Tensor
    axes: tuple[str,...]
    def __post_init__(self):
        if len(self.axes)!=self.tensor.ndim or len(set(self.axes))!=len(self.axes) or not all(a for a in self.axes): raise ValueError("Eixos nomeados devem ser únicos e corresponder ao rank")
    def align_to(self,*axes:str)->"NamedTensor":
        if set(axes)!=set(self.axes) or len(axes)!=len(self.axes): raise ValueError("align_to exige exatamente os mesmos eixos")
        perm=tuple(self.axes.index(axis) for axis in axes); return NamedTensor(self.tensor.transpose(perm),tuple(axes))
    def _align_pair(self,other:"NamedTensor"):
        union=self.axes+tuple(axis for axis in other.axes if axis not in self.axes)
        def expand(item):
            present=tuple(axis for axis in union if axis in item.axes); aligned=item.align_to(*present) if present!=item.axes else item
            shape=tuple(aligned.tensor.shape[present.index(axis)] if axis in present else 1 for axis in union)
            return aligned.tensor.reshape(shape)
        return union,expand(self),expand(other)
    def __add__(self,other):
        if not isinstance(other,NamedTensor): return NamedTensor(self.tensor+other,self.axes)
        axes,a,b=self._align_pair(other); return NamedTensor(a+b,axes)
    __radd__=__add__
    def __mul__(self,other):
        if not isinstance(other,NamedTensor): return NamedTensor(self.tensor*other,self.axes)
        axes,a,b=self._align_pair(other); return NamedTensor(a*b,axes)
    __rmul__=__mul__


def tensor_vjp(f:Callable[[Tensor],Tensor],x:Tensor,cotangent)->tuple[Tensor,object]:
    leaf=Tensor._from_flat(x._flat,x.shape,True); output=f(leaf)
    if not isinstance(output,Tensor): raise TypeError("tensor_vjp exige saída Tensor")
    output.backward(cotangent); return output,leaf.grad

def tensor_jacobian(f:Callable[[Tensor],Tensor],x:Tensor)->tuple[Tensor,tuple[tuple[float,...],...]]:
    leaf=Tensor._from_flat(x._flat,x.shape,True); output=f(leaf)
    if not isinstance(output,Tensor): raise TypeError("tensor_jacobian exige saída Tensor")
    rows=[]
    for i in range(output.size):
        seed=[0.0]*output.size; seed[i]=1.0; output.backward(Tensor._from_flat(seed,output.shape,False)); rows.append(tuple(leaf._grad))
    return output,tuple(rows)

__all__=["Tensor","NamedTensor","tensor_vjp","tensor_jacobian"]
