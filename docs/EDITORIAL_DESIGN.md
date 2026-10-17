# PDFs científicos: composição e verificação

Os PDFs compartilham uma composição A4 com margens de impressão, hierarquia
tipográfica, corpo serifado, títulos sem serifa, paleta discreta azul-petróleo,
legendas consistentes, equações numeradas e rodapés legíveis. Tipografia não
certifica a validade científica do conteúdo.

`documents/exporters.py` produz Typst e LaTeX a partir do mesmo documento
estruturado. Equações preservam a AST e frações são compostas como frações.
Tabelas longas repetem cabeçalhos, podem atravessar páginas e preservam todos os
valores. Figuras têm ajuste de proporção e limite de altura. LaTeX usa fontes
Latin Modern quando disponíveis e duas passagens para estabilizar tabelas.

Os novos artefatos de documentos declaram `render_profile=nabla-print-v2`.
O verificador conserva os renderizadores v1 para verificar publicações anteriores
com os bytes originais, sem reformatar silenciosamente evidências históricas.

Os Living Papers acrescentam título, autores e resumo; resumos curtos com uma
figura usam grade equilibrada, enquanto relatórios extensos fluem em largura
completa. Valores racionais, vetores e matrizes pequenas recebem apresentação
matemática. Decimais exibidos com `≈` são arredondados para dez algarismos
significativos; os dados completos permanecem no bundle histórico. Estruturas
grandes são identificadas como prévias, com sua dimensão e referência ao bundle.
Não se atribui exatidão ao arredondamento editorial.

O rodapé de cada página contém paginação, SHA-256 e a assinatura fornecida, ou a
declaração de documento não assinado. Os dados entram como literais, sem executar
resultados como comandos Typst/LaTeX. Os templates Typst continuam sendo programas
confiáveis fornecidos pelo autor. Não existe garantia de diagramação perfeita
para qualquer template ou conteúdo arbitrário: os perfis padrão são verificados
com documentos concretos e testes de paginação.

```bash
python -m pip install -e '.[publishing,animation,federation,torch,formal]'
python examples/science/layers_pipeline.py .nabla/fluxo-editorial
python examples/science/editorial_showcase.py .nabla/relatorios-editoriais
python -m pytest -q tests/test_editorial_layout.py
```

A primeira demonstração gera um PDF assinado com gráfico, dados auditados e
metadados. A segunda produz o mesmo relatório sintético em Typst e LaTeX, com
71 linhas de resultados e comparação independente com `exp(-t)`. Os testes leem
os PDFs reais, verificam cabeçalhos repetidos, último resultado, rodapés em todas
as páginas e preservação dos valores originais. As imagens renderizadas foram
inspecionadas durante a entrega; o CI publica os PDFs como artefatos.

LaTeX é opcional e requer `pdflatex`, os pacotes recomendados de LaTeX e fontes
Latin Modern (`texlive-latex-recommended` e `lmodern` em Debian/Ubuntu). Typst usa
o binário quando disponível ou o binding Python em processo separado.
