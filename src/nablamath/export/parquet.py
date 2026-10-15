"""Optional Arrow export with explicit searchable metadata and lossless JSON payload."""
from pathlib import Path
from ..core.semantic_ir import canonical_json
from ..datasets.schema import ScientificRecord


def _arrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        return pa, pq
    except ImportError as exc:
        raise RuntimeError('Instale nablamath[data] para Parquet') from exc


def write_parquet(records, destination):
    pa, pq = _arrow()
    records = tuple(records)
    if not records:
        raise ValueError('Dataset vazio')
    rows = [{'record_id': r.content_id, 'family': r.task.family, 'split': r.to_data()['split'],
             'license_id': r.to_data()['license_id'], 'payload': canonical_json(r.to_data())} for r in records]
    table = pa.Table.from_pylist(rows)
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        pq.write_table(table, handle, compression='zstd')
    return path


def read_parquet(source):
    import json
    _, pq = _arrow()
    path = Path(source)
    if path.stat().st_size > 64*1024*1024:
        raise ValueError('Parquet excede limite de arquivo')
    parquet = pq.ParquetFile(path)
    metadata = parquet.metadata
    uncompressed = sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))
    if metadata.num_rows > 10000 or uncompressed > 64*1024*1024:
        raise ValueError('Parquet excede limites antes da alocação')
    table = parquet.read()
    if set(table.column_names) != {'record_id','family','split','license_id','payload'}:
        raise ValueError('Colunas Parquet inesperadas')
    if table.num_rows > 10000 or table.nbytes > 64 * 1024 * 1024:
        raise ValueError('Parquet excede limites')
    records = []
    for row in table.to_pylist():
        record = ScientificRecord.from_data(json.loads(row['payload']))
        if (record.content_id != row['record_id'] or record.task.family != row['family']
                or record.to_data()['split'] != row['split'] or record.to_data()['license_id'] != row['license_id']):
            raise ValueError('Índice Parquet diverge do conteúdo')
        records.append(record)
    return tuple(records)


def write_parquet_stream(records,destination,*,batch_size=128,max_records=100000):
    """Validated row-group streaming; atomic publication, no overwrite, mixed profiles."""
    import os
    import tempfile
    from ..datasets.research_record import parse_record
    if type(batch_size) is not int or not 1<=batch_size<=1000 or type(max_records) is not int or not 1<=max_records<=100000:
        raise ValueError('Orçamentos inválidos')
    pa,pq=_arrow();path=Path(destination);count=0
    schema=pa.schema([('record_id',pa.string()),('record_kind',pa.string()),('split',pa.string()),('license_id',pa.string()),('payload',pa.string())])
    descriptor,staging=tempfile.mkstemp(prefix='.nabla-arrow-',dir=path.parent)
    os.close(descriptor)
    try:
        with pq.ParquetWriter(staging,schema,compression='zstd') as writer:
            rows=[]
            for record in records:
                data=record.to_data();record=parse_record(data);count+=1
                if count>max_records:raise ValueError('Registros excedem orçamento')
                rows.append({'record_id':record.content_id,'record_kind':data.get('record_kind','forge_task'),
                             'split':data['split'],'license_id':data['license_id'],'payload':canonical_json(data)})
                if len(rows)>=batch_size:
                    writer.write_table(pa.Table.from_pylist(rows,schema=schema));rows=[]
            if rows:writer.write_table(pa.Table.from_pylist(rows,schema=schema))
            if not count:raise ValueError('Dataset vazio')
        os.link(staging,path)
        return {'records':count,'schema_version':1,'profile':'mixed-research-records'}
    finally:
        os.unlink(staging)


def iter_parquet_stream(source,*,batch_size=128,max_records=100000,max_uncompressed_bytes=256*1024*1024):
    import json
    from ..datasets.research_record import parse_record
    _,pq=_arrow();path=Path(source)
    if type(batch_size) is not int or not 1<=batch_size<=1000 or type(max_records) is not int or not 1<=max_records<=100000 or type(max_uncompressed_bytes) is not int or not 1<=max_uncompressed_bytes<=1024**3:
        raise ValueError('Orçamentos de leitura inválidos')
    if path.stat().st_size>max_uncompressed_bytes:raise ValueError('Arquivo excede limite')
    parquet=pq.ParquetFile(path);metadata=parquet.metadata
    if metadata.num_rows>max_records or sum(metadata.row_group(i).total_byte_size for i in range(metadata.num_row_groups))>max_uncompressed_bytes:
        raise ValueError('Metadados excedem orçamento')
    expected={'record_id','record_kind','split','license_id','payload'}
    if set(parquet.schema_arrow.names)!=expected:raise ValueError('Schema misto incompatível')
    for batch in parquet.iter_batches(batch_size=batch_size):
        for row in batch.to_pylist():
            data=json.loads(row['payload']);record=parse_record(data)
            if record.content_id!=row['record_id'] or row['record_kind']!=data.get('record_kind','forge_task') or data['split']!=row['split'] or data['license_id']!=row['license_id']:
                raise ValueError('Índice diverge do conteúdo')
            yield record
