# Auditoria executável — outubro de 2026

Data: 2026-10-14. Checkout base: `f57b0465d10586edce0eca9aa815260289044d21`
(`main` de `3scud3r0/Nabla`), inicialmente sem mudanças locais. As alterações
relatadas aqui permanecem no diretório de trabalho; não foi criado commit,
worktree, release ou publicação remota.

Ambiente exercitado: Linux, Python 3.12.14 em `.venv`, Node 24.19.0, SQLite da
biblioteca padrão e pdfTeX 1.40.26. Nenhuma dependência obrigatória nova foi
adicionada ao pacote. Não houve uso de credenciais de publicação.

## Base recebida e recuperação

A instalação editável funcionava, mas a importação falhava. A análise das fontes
encontrou trechos duplicados/sobrepostos em `symbolic/__init__.py`,
`symbolic/differentiate.py`, `symbolic/egraph.py` e `math/algebra/__init__.py`.
O teste `integration/test_backup_restore.py` também continha dois comandos `with`
consecutivos com indentação inválida. Foram recuperadas as APIs atuais de
certificados/e-graphs, cálculo e álgebra, preservando as verificações existentes.

Após a recuperação, 260 testes passaram e dois falharam pelo `math.txt`
desatualizado. Depois de regenerá-lo com a ferramenta canônica, os 262 testes
existentes passaram, com 12 subtestes. Não foram removidas asserções nem ignoradas
falhas para obter esse resultado.

Uma revisão posterior identificou a perda de domínio em `(1/x)-(1/x)`: a regra
`subtract_self` podia ocultar a singularidade. A condição `defined` agora é
verificada tanto na aplicação da regra quanto na reprodução do certificado.
O ruleset passou para `domain-safe-rational-v3`. A derivação de potência zero
preserva a condição de base não nula adotada pela semântica existente.

## Resultado final desta rodada

| Verificação executada | Resultado |
|---|---|
| `.venv/bin/python -m pytest -q` | 301 testes e 142 subtestes aprovados; sem falhas ou skips |
| `.venv/bin/python -m unittest discover -s tests -v` | 198 testes aprovados; este runner descobre um subconjunto diferente do pytest |
| `npm test` em `website/` | 5 testes aprovados |
| `npm run build` em `website/` | build concluído |
| `.venv/bin/python -m pip check` | nenhuma dependência quebrada |
| `.venv/bin/nabla doctor` | ambiente compatível; pdfLaTeX disponível, Lean ausente |
| `python tools/build_math_bundle.py --check` | bundle sincronizado, incluindo os novos módulos matemáticos |
| AST de todas as fontes e testes Python | análise concluída sem erros de sintaxe |
| HTTP do painel local | página 200; POST autenticado calculou `(x+x)/x` para `x=3` como 2; registro recuperado do SQLite |
| Ciclo Forge final | 12 exemplos aceitos, 6 integrais e 6 sistemas; bundle revalidado pela CLI |
| PDF do ciclo | compilado com LaTeX, 8 páginas; primeira página rasterizada e inspecionada visualmente |
| `git diff --check` | sem erros de whitespace |

O exemplo local está em `.nabla/vision-final/` (ignorado pelo Git): JSONL,
manifesto, dados de cenas, SVG/PNG e relatórios HTML, LaTeX, Typst e PDF. O exemplo
com tamanho 3 contém só treino, de acordo com a divisão conservadora por família;
nenhum conjunto de validação/teste independente foi inventado.

## Limites da evidência

As verificações mostram que o recorte de desenvolvimento local funciona. Não
foram executadas Lean/Mathlib, GPU/JAX, compilação Typst, upload Hugging Face,
SDK Rust, instaladores Windows nem a matriz completa de CI. As receitas de CI
multiplataforma existentes continuam presentes; não se afirma que esta máquina
as executou. A auditoria não recupera todo o histórico do projeto.

Não houve treinamento de LLM, medição de ganho de generalização, novidade
bibliográfica, revisão por pares externa, simulação baseada em dados observados
ou autoedição de código. Não há declaração de fase científica concluída.
Consulte [escopo, comandos e limites por fase](../SCIENTIFIC_CYCLE.md) e
[mapa de módulos](../architecture/current-modules.md).
