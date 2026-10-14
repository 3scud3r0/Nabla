"""Portable immutable cell snapshots, hash-chain checks and full operation replay."""
import json
from pathlib import Path
from ..core.semantic_ir import canonical_json,fingerprint
from .session import CalculationSession


class Notebook:
    def __init__(self,title='Nabla notebook'):
        if not isinstance(title,str) or not title.strip():
            raise ValueError('Notebook requer titulo')
        self.title=title
        self._cells=[]

    @property
    def cells(self):
        return json.loads(canonical_json(self._cells))

    def append(self,calculation):
        if len(self._cells)>=1000:
            raise ValueError('Notebook limitado a 1000 celulas')
        data=calculation.to_data()
        previous=self._cells[-1]['cell_id'] if self._cells else None
        payload={'previous':previous,'calculation':data}
        self._cells.append({**payload,'cell_id':fingerprint(payload)})
        return self._cells[-1]['cell_id']

    def to_data(self):
        payload={'schema_version':1,'title':self.title,'cells':self.cells}
        return {**payload,'content_id':fingerprint(payload)}

    def save(self,path):
        with Path(path).open('x',encoding='utf-8') as stream:
            stream.write(canonical_json(self.to_data())+'\n')

    def replay(self):
        previous=None
        for cell in self._cells:
            payload={'previous':cell['previous'],'calculation':cell['calculation']}
            if cell['previous']!=previous or cell['cell_id']!=fingerprint(payload):
                raise ValueError('Cadeia de celulas adulterada')
            result=CalculationSession.replay_request(cell['calculation']['request'])
            if result.to_data()!=cell['calculation']:
                raise ValueError('Resultado de celula divergente na reexecucao')
            previous=cell['cell_id']
        return len(self._cells)

    @classmethod
    def load(cls,path):
        path=Path(path)
        if path.stat().st_size>16*1024*1024:
            raise ValueError('Notebook excede 16 MiB')
        data=json.loads(path.read_text(encoding='utf-8'))
        if set(data)!={'schema_version','title','cells','content_id'} or data['schema_version']!=1 or not isinstance(data['cells'],list) or len(data['cells'])>1000:
            raise ValueError('Contrato de notebook invalido')
        digest=data.pop('content_id')
        if digest!=fingerprint(data):
            raise ValueError('Hash de notebook divergente')
        notebook=cls(data['title'])
        notebook._cells=data['cells']
        notebook.replay()
        return notebook
