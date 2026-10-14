"""Conservative family-held-out deterministic partitions for v2 scientific tasks."""
from dataclasses import dataclass
from ..core.semantic_ir import fingerprint
from ..forge.deduplicate import semantic_fingerprint


@dataclass(frozen=True)
class SplitPolicy:
    train: int=80
    validation: int=10
    test: int=10
    salt: str='forge-family-v1'

    def __post_init__(self):
        values=(self.train,self.validation,self.test)
        if any(type(v) is not int or v<0 for v in values) or sum(values)!=100 or not self.salt:
            raise ValueError('Proporcoes inteiras devem somar 100 e salt deve ser nao vazio')

    def split(self,task):
        # Entire constructor family is held together, including all sizes/seeds.
        from ..forge.task_spec import FAMILIES
        ordered=sorted(FAMILIES,key=lambda family:fingerprint({'policy':self.salt,'family':family}))
        bucket=(2*ordered.index(task.family)+1)*100/(2*len(ordered))
        return 'train' if bucket<self.train else 'validation' if bucket<self.train+self.validation else 'test'

    def to_data(self):
        return {'train':self.train,'validation':self.validation,'test':self.test,'salt':self.salt,'group':'constructor_family'}


def assign_splits(tasks,policy=None):
    policy=policy or SplitPolicy()
    assigned={};semantic_splits={}
    for task in tasks:
        split=policy.split(task)
        key=semantic_fingerprint(task)
        if key in semantic_splits and semantic_splits[key]!=split:
            raise ValueError('Duplicata semantica cruzaria particoes')
        semantic_splits[key]=split
        assigned[task.content_id]=split
    return assigned


def audit_splits(partitions):
    seen_semantics={};seen_families={};overlaps=[]
    for split,tasks in partitions.items():
        if split not in {'train','validation','test'}:
            raise ValueError('Particao desconhecida')
        for task in tasks:
            for scope,key,index in [('semantic',semantic_fingerprint(task),seen_semantics),('family',task.family,seen_families)]:
                if key in index and index[key]!=split:
                    overlaps.append({'scope':scope,'key':key,'splits':sorted({index[key],split})})
                index[key]=split
    return {'clean':not overlaps,'overlaps':overlaps,'scope':'local_semantics_and_constructor_families'}
