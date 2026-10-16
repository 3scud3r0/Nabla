"""Portable immutable cell snapshots, hash-chain checks and full operation replay."""
import json
import os
import tempfile
from pathlib import Path
from ..core.semantic_ir import canonical_json,fingerprint
from .session import CalculationSession
from ..core.semantic_contracts import require_fields


class Notebook:
    def __init__(self,title='Nabla notebook'):
        if not isinstance(title,str) or not title.strip() or len(title)>4096:
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
        path=Path(path)
        raw=(canonical_json(self.to_data())+'\n').encode('utf-8')
        if len(raw)>16*1024*1024:
            raise ValueError('Notebook excede 16 MiB')
        descriptor,name=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
        try:
            with os.fdopen(descriptor,'wb') as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            # Exclusive atomic publication, including when a concurrent writer wins.
            os.link(name,path)
        finally:
            Path(name).unlink(missing_ok=True)

    def replay(self):
        previous=None
        for cell in self._cells:
            require_fields(cell,{'previous','calculation','cell_id'})
            require_fields(cell['calculation'],{'schema_version','request','result','limitations','formal_proof','content_id'})
            if type(cell['calculation']['schema_version']) is not int or cell['calculation']['schema_version']!=1:
                raise ValueError('Versao de calculo incompatível')
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
        def unique(items):
            result={}
            for key,value in items:
                if key in result:
                    raise ValueError('Campo JSON duplicado em notebook')
                result[key]=value
            return result
        try:
            with path.open('rb') as stream:
                raw=stream.read(16*1024*1024+1)
            if len(raw)>16*1024*1024:
                raise ValueError('Notebook excede 16 MiB')
            data=json.loads(raw,object_pairs_hook=unique)
        except RecursionError as error:
            raise ValueError('Notebook excede profundidade JSON') from error
        require_fields(data,{'schema_version','title','cells','content_id'})
        if type(data['schema_version']) is not int or data['schema_version']!=1 or not isinstance(data['cells'],list) or len(data['cells'])>1000:
            raise ValueError('Contrato de notebook invalido')
        digest=data.pop('content_id')
        if digest!=fingerprint(data):
            raise ValueError('Hash de notebook divergente')
        notebook=cls(data['title'])
        notebook._cells=data['cells']
        notebook.replay()
        return notebook
