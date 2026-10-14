"""Open small neural models trained with/without Nabla on a pinned external holdout.

This is a numeric-answer regressor over hashed text features, not a pretrained
language model. It tests a bounded augmentation hypothesis and retains failures.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
from ..core.semantic_ir import canonical_json,fingerprint,rational
from ..forge.reverse_builder import generate_task
from ..verify.trace import verify_candidate


@dataclass(frozen=True)
class ArithmeticExample:
    question: str
    answer: Fraction
    source: str
    split: str

    def __post_init__(self):
        object.__setattr__(self,'answer',rational(self.answer))
        if not self.question.strip() or len(self.question)>8192 or not self.source.strip() or self.split not in {'train','test','augmentation'}:
            raise ValueError('Example contract invalid')
        if abs(self.answer)>10**12:raise ValueError('Target exceeds numeric profile')

    @property
    def semantic_id(self):
        return fingerprint({'question':' '.join(self.question.split())})


def load_gsm8k(directory,*,train_count=256,test_count=128,seed=149):
    root=Path(directory)
    manifest=json.loads((root/'source-manifest.json').read_text(encoding='utf-8'))
    if manifest['dataset']!='GSM8K' or manifest['license_id']!='MIT' or set(manifest['files'])!={'LICENSE','train.jsonl','test.jsonl'}:
        raise ValueError('Pinned source manifest required')
    for name,digest in manifest['files'].items():
        path=root/name
        if path.is_symlink() or path.stat().st_size>16*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('External source integrity failed')
    if not 1<=train_count<=2000 or not 1<=test_count<=1319:raise ValueError('External sample budget invalid')
    partitions={}
    for split,count in [('train',train_count),('test',test_count)]:
        rows=[]
        for line in (root/f'{split}.jsonl').read_text(encoding='utf-8').splitlines():
            data=json.loads(line);match=re.search(r'####\s*([-+\d,./]+)\s*$',data['answer'])
            if match is None:raise ValueError('Cannot parse independently published final answer')
            rows.append(ArithmeticExample(data['question'],rational(match[1].replace(',','')),
                                         'GSM8K@'+manifest['commit'],split))
        rows.sort(key=lambda row:fingerprint({'seed':seed,'question_id':row.semantic_id}))
        if len(rows)<count:raise ValueError('Insufficient external examples')
        partitions[split]=tuple(rows[:count])
    if {r.semantic_id for r in partitions['train']}&{r.semantic_id for r in partitions['test']}:
        raise ValueError('External exact-question contamination')
    return partitions['train'],partitions['test'],manifest


def nabla_augmentation(count=256,*,seed=413):
    if type(count) is not int or not 1<=count<=2000:raise ValueError('Augmentation budget invalid')
    rows=[];seen=set();attempted=0
    while len(rows)<count and attempted<count*5:
        family=('linear_system','polynomial_integral')[attempted%2]
        derived=seed+attempted;attempted+=1;generated=generate_task(family,derived,2)
        task,candidate=generated.task,generated.witness
        if not verify_candidate(task,candidate).valid:raise ValueError('Augmentation failed exact verification')
        if family=='linear_system':
            a=task.problem['matrix'];b=task.problem['rhs']
            question=f'Find x in the linear equations {a[0][0]}*x + {a[0][1]}*y = {b[0]} and {a[1][0]}*x + {a[1][1]}*y = {b[1]}.'
            answer=rational(candidate['solution'][0])
        else:
            coefficients=task.problem['coefficients'];primitive=candidate['coefficients']
            question=f'Compute the definite integral from 0 to 1 of {coefficients[0]} + {coefficients[1]}*x.'
            answer=sum(rational(v) for v in primitive[1:])
        row=ArithmeticExample(question,answer,'Nabla inverse-v2 seed='+str(derived),'augmentation')
        if row.semantic_id not in seen:seen.add(row.semantic_id);rows.append(row)
    if len(rows)!=count:raise ValueError('Unable to generate unique augmentation within budget')
    return tuple(rows)


def _features(question,dimensions=128):
    import numpy as np
    vector=np.zeros(dimensions,dtype=np.float64)
    for token in re.findall(r'[a-z]+|-?\d+(?:/\d+)?',question.casefold()):
        digest=hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4],'big')%dimensions]+=1 if digest[4]&1 else -1
    norm=float(np.linalg.norm(vector))
    return vector/(norm or 1.)


class OpenNumericMLP:
    """128 text features -> tanh hidden layer -> signed-log numeric target."""
    def __init__(self,*,seed,hidden=32):
        import numpy as np
        if type(seed) is not int or not 1<=hidden<=128:raise ValueError('Model seed/width invalid')
        rng=np.random.default_rng(seed)
        self.parameters=[rng.normal(0,.05,(128,hidden)),np.zeros(hidden),rng.normal(0,.05,(hidden,1)),np.zeros(1)]
        self.seed=seed;self.hidden=hidden

    def fit(self,examples,*,steps=500,batch_size=32,learning_rate=.001):
        import numpy as np
        examples=tuple(examples)
        if not examples or any(e.split not in {'train','augmentation'} for e in examples):raise ValueError('Training cannot consume test data')
        if type(steps) is not int or not 1<=steps<=10000 or not 1<=batch_size<=128 or not 0<learning_rate<=.01:
            raise ValueError('Training budget invalid')
        x=np.stack([_features(e.question) for e in examples]);raw=np.array([float(e.answer) for e in examples])
        y=(np.sign(raw)*np.log1p(np.abs(raw)))[:,None]
        rng=np.random.default_rng(self.seed+7907);first=[np.zeros_like(p) for p in self.parameters];second=[np.zeros_like(p) for p in self.parameters]
        losses=[]
        for step in range(1,steps+1):
            indices=rng.integers(0,len(examples),batch_size);batch=x[indices];targets=y[indices]
            w,b,v,c=self.parameters;hidden=np.tanh(batch@w+b);prediction=hidden@v+c;error=prediction-targets
            delta=2*error/batch_size;grad_hidden=(delta@v.T)*(1-hidden*hidden)
            gradients=[batch.T@grad_hidden,np.sum(grad_hidden,axis=0),hidden.T@delta,np.sum(delta,axis=0)]
            for i,(parameter,gradient) in enumerate(zip(self.parameters,gradients)):
                gradient=np.clip(gradient,-10,10)
                first[i]=.9*first[i]+.1*gradient;second[i]=.999*second[i]+.001*gradient*gradient
                parameter-=learning_rate*(first[i]/(1-.9**step))/(np.sqrt(second[i]/(1-.999**step))+1e-8)
            loss=float(np.mean(error*error))
            if not math.isfinite(loss):raise ValueError('Nonfinite training loss')
            if step==1 or step==steps or step%100==0:losses.append({'step':step,'mse_signed_log':loss})
        return {'steps':steps,'batch_size':batch_size,'learning_rate':learning_rate,'unique_examples':len({e.semantic_id for e in examples}),'loss_trace':losses}

    def predict(self,question):
        import numpy as np
        w,b,v,c=self.parameters
        transformed=float((np.tanh(_features(question)@w+b)@v+c).item())
        transformed=max(-28.,min(28.,transformed))
        numeric=math.copysign(math.expm1(abs(transformed)),transformed)
        return int(round(numeric))

    def save(self,path):
        import numpy as np
        path=Path(path)
        with path.open('xb') as stream:np.savez_compressed(stream,w=self.parameters[0],b=self.parameters[1],v=self.parameters[2],c=self.parameters[3])
        return hashlib.sha256(path.read_bytes()).hexdigest()


    @classmethod
    def load(cls,path,*,seed,hidden=32):
        import numpy as np
        model=cls(seed=seed,hidden=hidden)
        with np.load(path,allow_pickle=False) as arrays:
            if set(arrays.files)!={'w','b','v','c'}:raise ValueError('Unexpected model tensors')
            values=[arrays[name] for name in ('w','b','v','c')]
            if any(a.shape!=b.shape or not np.isfinite(a).all() for a,b in zip(values,model.parameters)):
                raise ValueError('Invalid model shapes/values')
            model.parameters=[a.copy() for a in values]
        return model


def controlled_experiment(training,test,augmentation,*,seeds=(11,23,37),steps=500,source_manifest=None,output_directory=None):
    training,test,augmentation=tuple(training),tuple(test),tuple(augmentation)
    if not training or not test or not augmentation or not 1<=len(seeds)<=8 or len(set(seeds))!=len(seeds):raise ValueError('Nonempty cohorts and distinct seeds required')
    if any(e.split!='train' for e in training) or any(e.split!='test' for e in test) or any(e.split!='augmentation' for e in augmentation):raise ValueError('Cohort roles invalid')
    train_ids={e.semantic_id for e in training};test_ids={e.semantic_id for e in test};aug_ids={e.semantic_id for e in augmentation}
    if train_ids&test_ids or aug_ids&test_ids or len(test_ids)!=len(test):raise ValueError('Question contamination detected')
    # Same row count and optimizer schedule: the control repeats base data where
    # treatment receives synthetic data; both receive identical initial weights.
    control=training+tuple(training[i%len(training)] for i in range(len(augmentation)))
    treatment=training+augmentation
    runs=[]
    output=Path(output_directory) if output_directory else None
    protocol={'architecture':'128x32x1 numeric regressor','seeds':list(seeds),'steps':steps,
              'training_ids':sorted(train_ids),'test_ids':sorted(test_ids),'augmentation_ids':sorted(aug_ids),
              'source_manifest':source_manifest,'feature_version':'sha256-token-128-v1',
              'training_code_sha256':hashlib.sha256(Path(__file__).read_text(encoding='utf-8').encode()).hexdigest()}
    protocol_id=fingerprint(protocol)
    if output:
        output.mkdir(parents=True,exist_ok=True)
        if any(output.iterdir()):raise FileExistsError(output)
        with (output/'protocol.json').open('x',encoding='utf-8') as stream:
            stream.write(canonical_json({**protocol,'protocol_id':protocol_id})+'\n')
    for seed in seeds:
        conditions={}
        for name,examples in [('without_nabla',control),('with_nabla',treatment)]:
            model=OpenNumericMLP(seed=seed);training_report=model.fit(examples,steps=steps)
            rows=[]
            for example in test:
                predicted=model.predict(example.question)
                rows.append({'question_id':example.semantic_id,'expected':str(example.answer),'predicted':str(predicted),
                             'correct':Fraction(predicted)==example.answer,'absolute_error':float(abs(Fraction(predicted)-example.answer))})
            successes=sum(row['correct'] for row in rows)
            weights_sha=model.save(output/f'{name}-seed-{seed}.npz') if output else None
            conditions[name]={'training':training_report,'successes':successes,'total':len(test),'accuracy':successes/len(test),
                              'mean_absolute_error':math.fsum(row['absolute_error'] for row in rows)/len(rows),
                              'weights_sha256':weights_sha,'predictions':rows}
        a,b=conditions['without_nabla'],conditions['with_nabla']
        better=sum(not x['correct'] and y['correct'] for x,y in zip(a['predictions'],b['predictions']))
        worse=sum(x['correct'] and not y['correct'] for x,y in zip(a['predictions'],b['predictions']))
        n=better+worse;p=min(1.,2*sum(math.comb(n,k) for k in range(min(better,worse)+1))/2**n) if n else 1.
        runs.append({'seed':seed,'conditions':conditions,'accuracy_delta':b['accuracy']-a['accuracy'],
                     'improved_examples':better,'regressed_examples':worse,'paired_exact_p_value':p})
    deltas=[r['accuracy_delta'] for r in runs]
    payload={'schema_version':1,'protocol_id':protocol_id,'architecture':'open 128x32x1 text-feature numeric regressor, Adam, tanh',
             'code_license':'MIT','source_manifest':source_manifest,'training_ids':sorted(train_ids),'test_ids':sorted(test_ids),'augmentation_ids':sorted(aug_ids),
             'runs':runs,'mean_accuracy_gain':sum(deltas)/len(deltas),'positive_gain_observed':sum(deltas)>0,
             'gain_demonstrated_in_every_seed':all(d>0 for d in deltas),'test_labels_used_for_training':False,
             'same_optimizer_steps_and_initialization':True,'negative_results_retained':True,
             'external_evaluation':bool(source_manifest),'pretrained_or_frontier_language_model':False,
             'limitations':'Small numeric regressor and supplied cohort; no general or frontier-model utility claim. Exact-question audit does not detect all template leakage.'}
    return {**payload,'experiment_id':fingerprint(payload)}


def verify_experiment_artifacts(report,test,model_directory):
    """Replay saved predictions and aggregate metrics; this does not authenticate training."""
    try:
        payload={k:v for k,v in report.items() if k!='experiment_id'}
        if fingerprint(payload)!=report['experiment_id']:return False
        directory=Path(model_directory)
        protocol=json.loads((directory/'protocol.json').read_text(encoding='utf-8'))
        if protocol['protocol_id']!=report['protocol_id'] or fingerprint({k:v for k,v in protocol.items() if k!='protocol_id'})!=report['protocol_id']:return False
        test=tuple(test)
        if sorted(r.semantic_id for r in test)!=report['test_ids']:return False
        gains=[]
        for run in report['runs']:
            for name,condition in run['conditions'].items():
                if name not in {'without_nabla','with_nabla'}:return False
                path=directory/f'{name}-seed-{run["seed"]}.npz'
                if hashlib.sha256(path.read_bytes()).hexdigest()!=condition['weights_sha256']:return False
                model=OpenNumericMLP.load(path,seed=run['seed'])
                if len(condition['predictions'])!=len(test):return False
                for row,example in zip(condition['predictions'],test):
                    predicted=model.predict(example.question)
                    if row['question_id']!=example.semantic_id or row['expected']!=str(example.answer) or row['predicted']!=str(predicted) or row['correct']!=(Fraction(predicted)==example.answer):return False
                    if row['absolute_error']!=float(abs(Fraction(predicted)-example.answer)):return False
                success=sum(r['correct'] for r in condition['predictions'])
                if condition['total']!=len(test) or condition['successes']!=success or condition['accuracy']!=success/len(test):return False
            delta=run['conditions']['with_nabla']['accuracy']-run['conditions']['without_nabla']['accuracy']
            if delta!=run['accuracy_delta']:return False
            gains.append(delta)
        return report['mean_accuracy_gain']==sum(gains)/len(gains) and report['positive_gain_observed']==(sum(gains)>0)
    except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError):
        return False
