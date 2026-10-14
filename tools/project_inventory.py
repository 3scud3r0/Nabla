"""Audit tracked project files and vision paths without creating placeholder modules.

Run from any directory; only Git-tracked files are counted. Stage new files first.
Python code lines are token-bearing physical lines (including docstrings); for
other code formats they are nonblank lines excluding whole-line comments.
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import subprocess
import tokenize
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = {'docs/audits/FILE_INVENTORY.md', 'docs/audits/file_inventory.csv'}
CODE = {'.py', '.lean', '.js', '.mjs', '.ts', '.sh', '.ps1', '.cmd', '.css', '.html'}


def git(*args: str) -> str:
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode()


def measure(path: Path) -> tuple[int | None, int | None]:
    raw = path.read_bytes()
    if b'\0' in raw:
        return None, None
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return None, None
    lines = len(text.splitlines())
    if path.suffix not in CODE:
        return lines, None
    if path.suffix == '.py':
        ignored = {tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                   tokenize.DEDENT, tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT}
        occupied = set()
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in ignored:
                occupied.update(range(token.start[0], token.end[0] + 1))
        return lines, len(occupied)
    return lines, sum(bool(line.strip()) and not line.lstrip().startswith(
        ('#', '//', '--', '/*', '*', '*/', '<!--')) for line in text.splitlines())


def category(name: str) -> str:
    if name == 'math.txt':
        return 'bundle gerado'
    for prefix, label in [('legacy/', 'histórico'), ('tests/', 'testes'),
                          ('src/', 'fonte'), ('lean/', 'Lean'), ('docs/', 'documentação')]:
        if name.startswith(prefix):
            return label
    return 'infraestrutura/outros'


def inventory(base: str) -> None:
    changes = {}
    deleted = []
    fields = git('diff', '--name-status', '-z', '--find-renames', base).split('\0')
    i = 0
    while i < len(fields) and fields[i]:
        status, name = fields[i:i+2]
        i += 2
        if status.startswith('R'):
            previous, name = name, fields[i]
            i += 1
            changes[name] = f'movido de {previous}'
        elif status == 'D':
            deleted.append(name)
        else:
            changes[name] = {'A': 'novo', 'M': 'alterado'}.get(status, status)
    rows = []
    for name in sorted(git('ls-files', '-z').split('\0')):
        if not name or name in REPORTS or not (ROOT / name).is_file():
            continue
        lines, code = measure(ROOT / name)
        rows.append([name, changes.get(name, 'existente'), category(name),
                     lines, code, (ROOT / name).stat().st_size])
    destination = ROOT / 'docs/audits'
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / 'file_inventory.csv').open('w', newline='') as handle:
        writer = csv.writer(handle, lineterminator='\n')
        writer.writerow(['arquivo', 'situação', 'categoria', 'linhas_físicas', 'linhas_código', 'bytes'])
        writer.writerows(rows)
    changed = [row for row in rows if row[1] != 'existente']
    new = [row for row in rows if row[1] == 'novo']
    physical = sum(row[3] or 0 for row in rows)
    code = sum(row[4] or 0 for row in rows if row[2] != 'histórico')
    summary = Counter(row[1].split(' de ')[0] for row in changed)
    output = ['# Inventário completo dos arquivos', '',
              f'Base de comparação: `{base}`. Inventário de todos os arquivos versionados presentes, incluindo os existentes.', '',
              f'**{len(rows)} arquivos; {physical:,} linhas físicas; {code:,} linhas de código fora do histórico.**', '',
              f'Novos: {len(new)}; alterações/movimentações: {dict(summary)}. Removidos: {len(deleted)}.', '',
              'Linhas físicas incluem comentários e espaços. Código Python conta linhas com tokens, incluindo docstrings; '
              'outros formatos de código contam linhas não vazias sem comentários de linha inteira (estimativa). '
              '“—” significa formato não código/binário. O bundle `math.txt` duplica fontes e não entra no total de código. '
              'Histórico movido não representa código novo. Os dois relatórios deste inventário são excluídos para evitar autocontagem. '
              'Caches, ambientes virtuais, builds e amostras locais ignoradas não são arquivos do PR.', '',
              'Reproduzir após adicionar arquivos ao índice:', '',
              f'```sh\npython tools/project_inventory.py --base {base}\n```', '',
              '## Arquivos removidos', '']
    output += [f'- `{name}`' for name in deleted] or ['Nenhum.']
    output += ['', '## Todos os arquivos, por caminho', '',
               '| Arquivo | Situação | Categoria | Linhas | Código |',
               '| --- | --- | --- | ---: | ---: |']
    for name, status, group, lines, count, _ in rows:
        output.append(f'| `{name}` | {status} | {group} | {lines if lines is not None else "—"} | {count if count is not None else "—"} |')
    (destination / 'FILE_INVENTORY.md').write_text('\n'.join(output) + '\n')
    print(f'{len(rows)} arquivos; {len(new)} novos; {code} linhas de código fora do histórico; {dict(summary)}')


def phase_map() -> None:
    vision = (ROOT / 'vision.md').read_text()
    sections = re.split(r'^### Fase ', vision, flags=re.M)[1:]
    rows = []
    output = ['# Caminhos para as fases 0–13', '',
              'Gerado de `vision.md` por `python tools/project_inventory.py --phases`. '
              'Existência de arquivo não comprova conclusão de fase. Fases 1–12 têm implementações delimitadas e testes; '
              'as fases seguintes possuem bases parciais ou permanecem planejadas. '
              'A fase 13 é um horizonte aberto, sem lista fechada de arquivos.', '',
              '## Regras de organização', '',
              '- `src/nablamath/`: API canônica; `tests/`: verificações independentes; `lean/Nabla/`: provas.',
              '- `legacy/current_scripts/`: acervo preservado; fora da descoberta de testes e do pacote instalado.',
              '- `lean/lakefile.toml`: configuração única; `lake-manifest.json`: dependências fixadas.',
              '- `dataset/` permanece compatível com a API anterior; `datasets/` recebe a nova política de partições.',
              '- `math.txt` é regenerado das fontes; não deve ser editado diretamente.',
              '- Novos módulos das fases futuras devem ocupar os caminhos abaixo quando tiverem implementação e testes.',
              '- Contratos compartilhados: IR em `core/`, recibos em `verify/`, cenas em `graphics/` e documentos em `documents/`.',
              '- Serviços, SDKs, protocolo, site e empacotamento existentes continuam nos seus diretórios próprios.', '']
    for section in sections:
        title = section.splitlines()[0]
        content = section.split('\n---', 1)[0].split('\n## ', 1)[0]
        paths = []
        for line in content.splitlines():
            if line.startswith(('**Arquivos', '**Pastas', '| `')):
                paths.extend(re.findall(r'`([^`]+)`', line))
        output += [f'## Fase {title}', '', '| Caminho previsto | Estado do caminho |', '| --- | --- |']
        for path in paths:
            candidates = [ROOT/path, ROOT/'src/nablamath'/path]
            actual = next((p for p in candidates if p.exists()), None)
            status = f'Presente: `{actual.relative_to(ROOT)}`' if actual else 'Planejado'
            output.append(f'| `{path}` | {status} |')
            rows.append((title, path, status))
        if not paths:
            output.append('| Contratos e compatibilidade de longo prazo | Horizonte aberto |')
        output.append('')
    (ROOT/'docs/architecture/vision-phases.md').write_text('\n'.join(output))
    print(f'Mapa atualizado: {len(sections)} fases, {len(rows)} caminhos auditados.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='f57b0465d10586edce0eca9aa815260289044d21')
    parser.add_argument('--phases', action='store_true')
    args = parser.parse_args()
    if args.phases:
        phase_map()
    else:
        inventory(args.base)
