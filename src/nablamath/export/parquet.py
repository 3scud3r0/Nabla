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
