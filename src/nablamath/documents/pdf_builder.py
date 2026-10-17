"""Optional PDF compilation, isolated from the checkout and without shell escape."""
from pathlib import Path
import shutil
import tempfile
import importlib.util
import sys

from .document_model import Document
from .exporters import to_latex, to_typst
from ..artifacts.process import run_renderer


def build_pdf(document: Document, destination: Path, backend: str = "typst", *, asset_root: Path | None = None) -> Path:
    commands = {"typst": ("typst", "typ", to_typst), "latex": ("pdflatex", "tex", to_latex)}
    if backend not in commands:
        raise ValueError("Backend PDF desconhecido")
    name, suffix, exporter = commands[backend]
    compiler = shutil.which(name)
    python_typst = backend == 'typst' and compiler is None and importlib.util.find_spec('typst') is not None
    if compiler is None and not python_typst:
        raise RuntimeError(f"Compilador opcional ausente: {name}")
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    with tempfile.TemporaryDirectory(prefix="nabla-document-") as directory:
        root = Path(directory)
        for section in document.sections:
            for figure in section.figures:
                if asset_root is None:
                    raise ValueError("Figuras requerem diretorio de artefatos")
                from .figures import validate_figure
                asset = validate_figure(figure, asset_root)
                if asset.is_symlink() or not asset.resolve().is_relative_to(Path(asset_root).resolve()):
                    raise ValueError("Figura fora do diretorio de artefatos")
                target = root / figure.path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(asset, target)
        source = root / f"document.{suffix}"
        source.write_text(exporter(document), encoding="utf-8")
        args = ([compiler, "compile", "--root", str(root), str(source), str(root / "document.pdf")]
                if backend == "typst" else
                [compiler, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", source.name])
        if python_typst:
            args = [sys.executable, '-c',
                    'import sys,typst; open(sys.argv[2],"wb").write(typst.compile(sys.argv[1], root=sys.argv[3]))',
                    str(source), str(root/'document.pdf'), str(root)]
        run_renderer(args,cwd=root,timeout=60)
        if backend == 'latex':
            # Repeated table headers, widths and page references settle on pass two.
            run_renderer(args,cwd=root,timeout=60)
        pdf = root / "document.pdf"
        if not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-'):
            raise RuntimeError("Compilacao PDF falhou: PDF ausente ou inválido")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as output:
            output.write(pdf.read_bytes())
    return destination
