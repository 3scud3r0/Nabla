"""Open two-tower neural learning over equation coefficients and rendered pixels.

A bounded study of intersection-sign classification, not an LLM, pretrained
frontier model, or demonstrated general scientific reasoning. NumPy is optional.
"""
from fractions import Fraction
import math
from ..core.semantic_ir import fingerprint


def _matching_pixels(actual, expected):
    # exp/tanh and BLAS can differ by a few float64 ulps across supported hosts.
    import numpy as np
    a,b=np.asarray(actual),np.asarray(expected)
    return a.shape==b.shape and np.isfinite(a).all() and np.allclose(a,b,rtol=1e-12,atol=1e-12)


def _render_pixels(equations):
    import numpy as np
    a,b,c,d,e,f=equations
    if not a*a+b*b or not c*c+d*d:raise ValueError('Equação degenerada')
    grid=np.linspace(-5,5,16);xx,yy=np.meshgrid(grid,grid)
    first=np.exp(-((a*xx+b*yy-e)/math.hypot(a,b))**2/.10)
    second=np.exp(-((c*xx+d*yy-f)/math.hypot(c,d))**2/.10)
    return np.stack((first,second)).reshape(-1).tolist()


def intersection_corpus(count,*,seed,coefficient_range=(1,5),excluded=()):
    import numpy as np
    from random import Random
    if type(count) is not int or not 2<=count<=2048 or len(coefficient_range)!=2 or not 1<=coefficient_range[0]<=coefficient_range[1]<=20:
        raise ValueError('Corpus fora do orçamento')
    rng=Random(seed);rows=[];seen=set(excluded);counts=[0,0]
    grid=np.linspace(-5,5,16);xx,yy=np.meshgrid(grid,grid)
    for attempt in range(count*100):
        def coefficient():return rng.choice((-1,1))*rng.randint(*coefficient_range)
        a,b,c,d,e,f=(coefficient() for _ in range(6));det=a*d-b*c
        if not det:continue
        x,y=Fraction(e*d-b*f,det),Fraction(a*f-e*c,det)
        if x==0:continue
        key=fingerprint({'solution':[str(x),str(y)]})
        label=int(x>0)
        if key in seen or counts[label]>=(count+label)//2:continue
        seen.add(key);counts[label]+=1
        # Pixels represent the two equations only; no solution marker or label.
        first=np.exp(-((a*xx+b*yy-e)/math.hypot(a,b))**2/.10)
        second=np.exp(-((c*xx+d*yy-f)/math.hypot(c,d))**2/.10)
        rows.append({'equations':[a,b,c,d,e,f],'pixels':np.stack((first,second)).reshape(-1).tolist(),
                     'label':label,'semantic_id':key,'question':'Is the intersection x coordinate positive?',
                     'solution':[str(x),str(y)],'synthetic':True})
        if len(rows)==count:return tuple(rows)
    raise ValueError('Diversidade insuficiente para corpus balanceado')


class MultimodalNetwork:
    def __init__(self,*,seed=0,modalities=('equation','image')):
        import numpy as np
        if not modalities or len(set(modalities))!=len(modalities) or not set(modalities)<={'equation','image'}:
            raise ValueError('Modalidades de entrada explícitas obrigatórias')
        self.modalities=tuple(modalities);rng=np.random.default_rng(seed)
        self.weights={}
        for name,size in (('equation',6),('image',512)):
            self.weights[name+'_w']=rng.normal(0,1/math.sqrt(size),(size,24))
            self.weights[name+'_b']=np.zeros(24)
        self.weights['fusion_w']=rng.normal(0,1/math.sqrt(48),(48,16))
        self.weights['fusion_b']=np.zeros(16)
        self.weights['output_w']=rng.normal(0,1/4,(16,1));self.weights['output_b']=np.zeros(1)

    @staticmethod
    def _inputs(rows):
        import numpy as np
        equation=np.asarray([r['equations'] for r in rows],dtype=np.float64)/20
        image=np.asarray([r['pixels'] for r in rows],dtype=np.float64)
        if equation.shape!=(len(rows),6) or image.shape!=(len(rows),512) or not np.isfinite(equation).all() or not np.isfinite(image).all():
            raise ValueError('Entradas multimodais incompatíveis')
        return equation,image

    def _forward(self,equation,image):
        import numpy as np
        w=self.weights
        eq=np.tanh(equation@w['equation_w']+w['equation_b']) if 'equation' in self.modalities else np.zeros((len(equation),24))
        im=np.tanh(image@w['image_w']+w['image_b']) if 'image' in self.modalities else np.zeros((len(image),24))
        fusion=np.concatenate((eq,im),axis=1);hidden=np.tanh(fusion@w['fusion_w']+w['fusion_b'])
        logits=np.clip(hidden@w['output_w']+w['output_b'],-40,40)
        probabilities=1/(1+np.exp(-logits))
        return eq,im,fusion,hidden,probabilities

    def fit(self,rows,*,seed=0,steps=1000,batch_size=32,learning_rate=.003):
        import numpy as np
        if not 2<=len(rows)<=2048 or type(steps) is not int or not 1<=steps<=10000 or type(batch_size) is not int or not 1<=batch_size<=128 or not 0<learning_rate<=.1:
            raise ValueError('Orçamento de treino inválido')
        equation,image=self._inputs(rows);labels=np.asarray([r['label'] for r in rows],dtype=float).reshape(-1,1)
        if not np.isin(labels,[0,1]).all():raise ValueError('Rótulos binários obrigatórios')
        rng=np.random.default_rng(seed);m={k:np.zeros_like(v) for k,v in self.weights.items()};v={k:np.zeros_like(a) for k,a in m.items()};losses=[]
        for step in range(1,steps+1):
            indices=rng.integers(0,len(rows),batch_size);e,i,y=equation[indices],image[indices],labels[indices]
            eq,im,fusion,hidden,p=self._forward(e,i);w=self.weights;d=(p-y)/batch_size
            gradients={'output_w':hidden.T@d,'output_b':d.sum(0)}
            dh=(d@w['output_w'].T)*(1-hidden**2)
            gradients.update(fusion_w=fusion.T@dh,fusion_b=dh.sum(0))
            df=dh@w['fusion_w'].T
            for name,source,activation,branch in (('equation',e,eq,df[:,:24]),('image',i,im,df[:,24:])):
                delta=branch*(1-activation**2) if name in self.modalities else np.zeros_like(branch)
                gradients[name+'_w']=source.T@delta;gradients[name+'_b']=delta.sum(0)
            for key,gradient in gradients.items():
                m[key]=.9*m[key]+.1*gradient;v[key]=.999*v[key]+.001*gradient**2
                w[key]-=learning_rate*(m[key]/(1-.9**step))/(np.sqrt(v[key]/(1-.999**step))+1e-8)
            if step==1 or step%100==0 or step==steps:
                losses.append({'step':step,'batch_binary_cross_entropy':float(-np.mean(y*np.log(p+1e-15)+(1-y)*np.log(1-p+1e-15)))})
        if not all(np.isfinite(w).all() for w in self.weights.values()):raise ValueError('Treino não finito')
        return losses

    def predict(self,rows):
        # No target/solution/semantic answer ID is read by this interface.
        equation,image=self._inputs(rows)
        return self._forward(equation,image)[-1].reshape(-1).tolist()

    def save(self,path):
        import numpy as np
        with open(path,'xb') as stream:np.savez_compressed(stream,**self.weights)

    @classmethod
    def load(cls,path,*,modalities=('equation','image')):
        import numpy as np
        from pathlib import Path
        if Path(path).stat().st_size>2*1024*1024:raise ValueError('Checkpoint excede limite')
        model=cls(modalities=modalities)
        with np.load(path,allow_pickle=False) as arrays:
            if set(arrays.files)!=set(model.weights):raise ValueError('Tensores inesperados')
            for name,expected in model.weights.items():
                value=arrays[name]
                if value.shape!=expected.shape or value.dtype!=np.float64 or not np.isfinite(value).all():raise ValueError('Tensor incompatível')
                model.weights[name]=value.copy()
        return model


def run_multimodal_study(train,test,*,seeds=(11,23,37),steps=1000,output=None):
    from pathlib import Path
    from ..core.semantic_ir import canonical_json
    if not train or not test or not 1<=len(seeds)<=10 or len(set(seeds))!=len(seeds):raise ValueError('Coortes/sementes inválidas')
    if {r['semantic_id'] for r in train}&{r['semantic_id'] for r in test}:raise ValueError('Contaminação semântica')
    for row in (*train,*test):
        a,b,c,d,e,f=row['equations'];x,y=map(Fraction,row['solution'])
        if not _matching_pixels(row['pixels'],_render_pixels(row['equations'])):raise ValueError('Pixels não correspondem às equações')
        if a*x+b*y!=e or c*x+d*y!=f or row['label']!=int(x>0) or row['semantic_id']!=fingerprint({'solution':[str(x),str(y)]}):
            raise ValueError('Rótulo/testemunho não passou na verificação independente')
    protocol={'schema_version':1,'train_ids':[r['semantic_id'] for r in train],'test_ids':[r['semantic_id'] for r in test],
              'seeds':list(seeds),'steps':steps,'ablations':['equation','image','equation+image'],
              'target':'sign of exact line intersection x; no solution marker in input',
              'scope':'synthetic bounded multimodal experiment, not external benchmark learning gain'}
    root=Path(output) if output is not None else None
    if root:
        root.mkdir(parents=True,exist_ok=False)
        (root/'protocol.json').write_text(canonical_json(protocol)+'\n',encoding='utf-8')
    runs=[]
    inputs=[{'equations':r['equations'],'pixels':r['pixels']} for r in test]
    for seed in seeds:
        for modalities in (('equation',),('image',),('equation','image')):
            model=MultimodalNetwork(seed=seed,modalities=modalities);losses=model.fit(train,seed=seed,steps=steps)
            probabilities=model.predict(inputs);correct=[int(p>=.5)==r['label'] for p,r in zip(probabilities,test)]
            filename=f"seed-{seed}-{'-'.join(modalities)}.npz"
            if root:
                model.save(root/filename)
                if MultimodalNetwork.load(root/filename,modalities=modalities).predict(inputs)!=probabilities:raise ValueError('Replay de checkpoint divergiu')
            runs.append({'seed':seed,'modalities':list(modalities),'correct':sum(correct),'total':len(test),
                         'accuracy':sum(correct)/len(test),'probabilities':probabilities,'expected_labels':[r['label'] for r in test],
                         'correct_mask':correct,'training_losses':losses,'checkpoint':filename})
    payload={'protocol':protocol,'runs':runs,'external_learning_gain_established':False,
             'limitations':'Synthetic classification only; modalities share an underlying equation; coefficient-range OOD is not all forms of novelty.'}
    report={**payload,'study_id':fingerprint(payload)}
    if root:
        (root/'report.json').write_text(canonical_json(report)+'\n',encoding='utf-8')
        (root/'corpus.json').write_text(canonical_json({'train':train,'test':test})+'\n',encoding='utf-8')
    return report


def verify_multimodal_study(directory):
    """Replay all saved predictions and ablations; not independent retraining."""
    import json
    from pathlib import Path
    root=Path(directory)
    try:
        for name in ('report.json','protocol.json','corpus.json'):
            if (root/name).is_symlink() or (root/name).stat().st_size>16*1024*1024:return False
        report=json.loads((root/'report.json').read_text(encoding='utf-8'))
        protocol=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
        corpus=json.loads((root/'corpus.json').read_text(encoding='utf-8'))
        payload={k:v for k,v in report.items() if k!='study_id'}
        if fingerprint(payload)!=report['study_id'] or report['protocol']!=protocol:return False
        train,test=corpus['train'],corpus['test']
        if [r['semantic_id'] for r in train]!=protocol['train_ids'] or [r['semantic_id'] for r in test]!=protocol['test_ids'] or set(protocol['train_ids'])&set(protocol['test_ids']):return False
        for row in (*train,*test):
            if not _matching_pixels(row['pixels'],_render_pixels(row['equations'])):return False
            a,b,c,d,e,f=row['equations'];x,y=map(Fraction,row['solution'])
            if (a*x+b*y!=e or c*x+d*y!=f or row['label']!=int(x>0)
                    or row['semantic_id']!=fingerprint({'solution':[str(x),str(y)]})):return False
        expected={(seed,tuple(modalities)) for seed in protocol['seeds'] for modalities in (('equation',),('image',),('equation','image'))}
        if len(report['runs'])!=len(expected) or {(r['seed'],tuple(r['modalities'])) for r in report['runs']}!=expected:return False
        for run in report['runs']:
            filename=f"seed-{run['seed']}-{'-'.join(run['modalities'])}.npz"
            if run['checkpoint']!=filename or (root/filename).is_symlink():return False
            model=MultimodalNetwork.load(root/filename,modalities=run['modalities'])
            probabilities=model.predict([{'equations':r['equations'],'pixels':r['pixels']} for r in test])
            correct=[int(p>=.5)==r['label'] for p,r in zip(probabilities,test)]
            if (len(probabilities)!=len(run['probabilities'])
                    or any(not math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12) for a,b in zip(probabilities,run['probabilities'])) or run['expected_labels']!=[r['label'] for r in test] or correct!=run['correct_mask']
                    or run['correct']!=sum(correct) or run['total']!=len(test) or run['accuracy']!=sum(correct)/len(test)):return False
        return report['external_learning_gain_established'] is False
    except (ValueError,KeyError,TypeError,OSError):return False
