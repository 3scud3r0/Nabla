"""Compile fontes atuais e configurações do repositório em um arquivo de texto."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "NablaMath_current_sources.txt"
SOURCE_SUFFIXES = {
    ".py", ".pyi", ".lean", ".c", ".h", ".hpp", ".cpp", ".cc", ".rs",
    ".js", ".mjs", ".html", ".css", ".json", ".yml", ".yaml", ".toml",
    ".sh", ".ps1", ".cmd", ".sql", ".ipynb",
}
EXCLUDED_PARTS = {
    ".git", ".lake", ".venv", "venv", "__pycache__", "node_modules", "dist", "build",
    "target", "site-packages", "legacy", ".pytest_cache", ".mypy_cache", ".nabla",
    ".playwright-tmp", "*.egg-info",
}


def source_files(output: Path) -> list[Path]:
    files = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path == output:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS or part.startswith(("pip-", "tmp", ".tmp")) or part.endswith(".egg-info")
               for part in relative.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix().casefold())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="destino do bundle (padrão: NablaMath_current_sources.txt)")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    files = source_files(output)
    sections = [
        "NABLAMATH — BUNDLE DE CÓDIGO-FONTE E CONFIGURAÇÃO",
        "Arquivos concatenados para leitura; cada seção começa com seu caminho relativo.",
        "O diretório legacy/, ambientes, caches, dependências instaladas e dados foram excluídos.",
        f"Arquivos incluídos: {len(files)}",
        "",
    ]
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        sections.extend(("=" * 88, f"ARQUIVO: {relative}", "=" * 88, content.rstrip(), ""))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Bundle criado: {output}")
    print(f"Arquivos fonte/configuração incluídos: {len(files)}")
    print("Excluídos: legacy/, ambientes, caches, dependências e dados gerados.")


if __name__ == "__main__":
    main()
