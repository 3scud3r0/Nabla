"""Optional PDF compilation, isolated from the checkout and without shell escape."""
from pathlib import Path
import shutil
import subprocess
import tempfile

from .document_model import Document
from .exporters import to_latex, to_typst


def build_pdf(document: Document, destination: Path, backend: str = "typst", *, asset_root: Path | None = None) -> Path:
    commands = {"typst": ("typst", "typ", to_typst), "latex": ("pdflatex", "tex", to_latex)}
    if backend not in commands:
        raise ValueError("Backend PDF desconhecido")
    name, suffix, exporter = commands[backend]
    compiler = shutil.which(name)
    if compiler is None:
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
                asset = Path(asset_root) / figure.path
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
        result = subprocess.run(args, cwd=root, capture_output=True, timeout=60, check=False)
        pdf = root / "document.pdf"
        if result.returncode or not pdf.is_file() or not pdf.read_bytes().startswith(b'%PDF-'):
            raise RuntimeError("Compilacao PDF falhou: " + result.stderr.decode(errors="replace")[-500:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as output:
            output.write(pdf.read_bytes())
    return destination
