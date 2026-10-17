"""Partitioned JSON-row frame with local threads or an explicit distributed executor.

Rows are snapshotted; task functions must be trusted, deterministic application code.
An executor may be a concurrent.futures or Dask distributed Client instance.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from ..core.semantic_ir import canonical_json
from ..calc.receipt import receipt, verify_receipt


class DistributedDataFrame:
    def __init__(self, partitions, *, provenance=None):
        partitions = list(partitions)
        if not 1 <= len(partitions) <= 1024:
            raise ValueError('Require 1–1024 partitions')
        raw = canonical_json(partitions)
        if len(raw.encode()) > 16*1024*1024:
            raise ValueError('Frame exceeds 16 MiB; use smaller batches')
        snapshot = json.loads(raw)
        columns = None
        for partition in snapshot:
            if not isinstance(partition,list):
                raise ValueError('Partitions must be row lists')
            for row in partition:
                if not isinstance(row,dict) or any(not isinstance(k,str) or not k for k in row):
                    raise ValueError('Rows require named columns')
                if columns is None:
                    columns = set(row)
                if set(row) != columns:
                    raise ValueError('All rows must share a schema')
        self._partitions = snapshot
        if provenance is not None:
            if not verify_receipt(provenance) or provenance.get('result') != snapshot:
                raise ValueError('Frame provenance must bind the exact partition snapshot')
            self._provenance = json.loads(canonical_json(provenance))
        else:
            self._provenance = receipt('dataframe.from_partitions',{},snapshot)

    @classmethod
    def from_rows(cls, rows, *, partition_size=1000):
        if type(partition_size) is not int or not 1 <= partition_size <= 100000:
            raise ValueError('Invalid partition size')
        rows = list(rows)
        return cls([rows[i:i+partition_size] for i in range(0,len(rows),partition_size)] or [[]])

    @property
    def provenance(self):
        return json.loads(canonical_json(self._provenance))

    @property
    def partitions(self):
        return json.loads(canonical_json(self._partitions))

    def collect(self):
        return [row for part in self.partitions for row in part]

    def map_partitions(self, function, *, operation, executor=None):
        if not callable(function) or not isinstance(operation,str) or not operation.strip():
            raise ValueError('A trusted function and stable operation name are required')
        owned = executor is None
        executor = executor or ThreadPoolExecutor(max_workers=min(32,len(self._partitions)))
        futures = []
        try:
            futures = [executor.submit(function,part) for part in self.partitions]
            result = [future.result() for future in futures]
        except BaseException:
            for future in futures:
                future.cancel()
            raise
        finally:
            if owned:
                executor.shutdown(wait=True,cancel_futures=True)
        record = receipt(operation,{'source':self.provenance['content_id']}, result,
                         backend=type(executor).__name__, parents=[self.provenance['content_id']])
        return type(self)(result,provenance=record)

    def select(self, *columns):
        if not columns or len(set(columns)) != len(columns):
            raise ValueError('Select unique named columns')
        result = [[{k:row[k] for k in columns} for row in part] for part in self._partitions]
        return type(self)(result,provenance=receipt('dataframe.select',{'columns':list(columns)},result,
                                                  parents=[self.provenance['content_id']]))

    def sum(self, column):
        values = [row[column] for row in self.collect()]
        if any(type(v) not in (int,float) for v in values):
            raise ValueError('Sum requires a numeric column')
        total = sum(values)
        return receipt('dataframe.sum',{'column':column},total,parents=[self.provenance['content_id']])
