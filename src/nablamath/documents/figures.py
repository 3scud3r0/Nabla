"""Content-addressed figure ingestion and integrity validation."""
import hashlib
from pathlib import Path
from .document_model import Figure


def ingest_figure(source: Path, asset_root: Path, caption: str) -> Figure:
    source, root = Path(source), Path(asset_root)
    raw = source.read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 32 * 1024 * 1024:
        raise ValueError('Figura deve ser PNG até 32 MiB')
    figure = Figure(f'figures/{hashlib.sha256(raw).hexdigest()}.png', caption)
    target = root / figure.path
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('Artefato com hash incompatível')
    else:
        with target.open('xb') as output:
            output.write(raw)
    validate_figure(figure, root)
    return figure


def validate_figure(figure: Figure, asset_root: Path) -> Path:
    root = Path(asset_root).resolve()
    path = root / figure.path
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Figura fora do diretório de artefatos')
    raw = path.read_bytes()
    if (not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 32 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != path.stem):
        raise ValueError('Conteúdo da figura não corresponde ao identificador')
    return path
