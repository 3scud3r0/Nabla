"""Portable immutable cell snapshots, hash-chain checks and full operation replay."""
import json
from pathlib import Path
from ..core.semantic_ir import canonical_json,fingerprint
from .session import CalculationSession
from ..core.semantic_contracts import load_json, require_fields, require_digest, validate_json


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
        # Snapshot before retaining it: callers cannot mutate an appended result.
        data=load_json(canonical_json(data), max_bytes=16*1024*1024, max_nodes=500000)
        previous=self._cells[-1]['cell_id'] if self._cells else None
        payload={'previous':previous,'calculation':data}
        self._cells.append({**payload,'cell_id':fingerprint(payload)})
        return self._cells[-1]['cell_id']

    def to_data(self):
        payload={'schema_version':1,'title':self.title,'cells':self.cells}
        return {**payload,'content_id':fingerprint(payload)}

    def save(self,path):
        data=self.to_data()
        validate_json(data, max_bytes=16*1024*1024-1, max_nodes=500000)
        raw=canonical_json(data)+'\n'
        with Path(path).open('x',encoding='utf-8') as stream:
            stream.write(raw)

    def replay(self):
        previous=None
        for cell in self._cells:
            require_fields(cell, {'previous', 'calculation', 'cell_id'})
            require_digest(cell['cell_id'])
            calculation=require_fields(cell['calculation'],
                {'schema_version', 'request', 'result', 'limitations', 'formal_proof', 'content_id'})
            if type(calculation['schema_version']) is not int or calculation['schema_version'] != 1 or calculation['formal_proof'] is not False:
                raise ValueError('Contrato de calculo invalido')
            require_digest(calculation['content_id'])
            payload={'previous':cell['previous'],'calculation':cell['calculation']}
            if cell['previous']!=previous or cell['cell_id']!=fingerprint(payload):
                raise ValueError('Cadeia de celulas adulterada')
            result=CalculationSession.replay_request(cell['calculation']['request'])
            if canonical_json(result.to_data())!=canonical_json(cell['calculation']):
                raise ValueError('Resultado de celula divergente na reexecucao')
            previous=cell['cell_id']
        return len(self._cells)

    @classmethod
    def load(cls,path):
        path=Path(path)
        if path.stat().st_size>16*1024*1024:
            raise ValueError('Notebook excede 16 MiB')
        with path.open('rb') as stream:
            raw=stream.read(16*1024*1024+1)
        if len(raw)>16*1024*1024:
            raise ValueError('Notebook excede 16 MiB')
        data=load_json(raw.decode('utf-8'), max_bytes=16*1024*1024, max_nodes=500000)
        require_fields(data, {'schema_version','title','cells','content_id'})
        if set(data)!={'schema_version','title','cells','content_id'} or type(data['schema_version']) is not int or data['schema_version']!=1 or not isinstance(data['cells'],list) or len(data['cells'])>1000:
            raise ValueError('Contrato de notebook invalido')
        digest=require_digest(data.pop('content_id'))
        if digest!=fingerprint(data):
            raise ValueError('Hash de notebook divergente')
        notebook=cls(data['title'])
        notebook._cells=data['cells']
        notebook.replay()
        return notebook
