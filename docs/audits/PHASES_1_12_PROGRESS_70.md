# Atualização das fases F1–F12 — estimativa de 70.32%

Registro: 2026-10-15T00:52:43.536015+00:00. Código auditado: `805a75102534f34cc90e2ad10a32ea4aa324d398` na branch
`feat/scientific-maturity-profiles`. A atualização é do código dessa branch, sem
alegar integração à main. Um commit posterior apenas deste relatório não muda o
snapshot de código testado.

**Estimativa ponderada: 70.32%**, ante 48.21%.
Média simples: 70.00%. Mesma rubrica da
[avaliação anterior](PHASES_1_12_PROGRESS_2026_10_15.md): cobertura C/30,
integração I/20, verificação V/20, evidência externa E/20 e operação O/10.
Mantidos os pesos originais de F1–F12, normalizados pela soma 95. F0 e F13 ficam
fora. Não houve substituição do denominador por uma lista menor de fases.

Os valores são **estimativas técnicas por julgamento**, em degraus de cinco pontos,
com margem prudente de aproximadamente ±10 pontos no agregado. Não são medida
objetiva de conclusão científica, fração de tempo restante, contagem de arquivos
ou certificação de que 70% das ambições de décadas foram realizadas. A casa decimal
vem da média ponderada, não de precisão experimental do julgamento.

## Lista atualizada

| Fase | Antes | Agora | C/30 | I/20 | V/20 | E/20 | O/10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| F1 — Calculadora científica | 50% | **80%** | 25 | 20 | 15 | 10 | 10 |
| F2 — Forge e geração inversa | 50% | **70%** | 20 | 15 | 20 | 5 | 10 |
| F3 — Prove e Falsifier | 55% | **70%** | 20 | 20 | 15 | 5 | 10 |
| F4 — Geometria e imagens científicas | 60% | **75%** | 25 | 20 | 15 | 5 | 10 |
| F5 — Studio e publicação | 65% | **75%** | 25 | 20 | 15 | 5 | 10 |
| F6 — Datasets científicos | 55% | **75%** | 25 | 20 | 15 | 5 | 10 |
| F7 — Worlds e simulações | 50% | **70%** | 25 | 15 | 20 | 0 | 10 |
| F8 — Multimodalidade e agentes | 35% | **60%** | 20 | 15 | 15 | 0 | 10 |
| F9 — Discovery | 35% | **65%** | 20 | 20 | 15 | 0 | 10 |
| F10 — RSI controlado | 40% | **70%** | 20 | 20 | 15 | 5 | 10 |
| F11 — Outras disciplinas | 30% | **60%** | 20 | 15 | 15 | 0 | 10 |
| F12 — Conhecimento científico vivo | 45% | **70%** | 25 | 20 | 15 | 0 | 10 |

Fórmula: `soma(peso × nota da fase) / 95`. As notas avaliam maturidade de componentes,
não a porcentagem de tickets encerrados no backlog. Não transformam um exemplo
validado em cobertura universal de uma disciplina.

## Entregas e pendências por fase

### F1 — 80%

**Entregue/verificado:** 33 operações públicas e replay; matrizes, grafos, Bayes, séries, SAT e regressão ponderada. NIST Longley confere sete coeficientes e SSE.

**Ainda falta:** IR vetorial/matricial mais uniforme, cálculo não polinomial mais amplo, corpus por toda operação e revisão matemática.

### F2 — 70%

**Entregue/verificado:** Oito famílias originais e construção inversa de integrais racionais; conferência de derivada por polinômios e SymPy, recusando novos polos.

**Ainda falta:** Diversidade/complexidade avançadas, templates/composições mais amplos e dificuldade demonstrada contra novos solvers.

### F3 — 70%

**Entregue/verificado:** Bundle pergunta–enunciado–certificado–revisão com toolchain fixada e replay; prova Lean real e testes contra troca de pergunta.

**Ainda falta:** Revisão independente da correspondência linguística, fragmentos adicionais e falsificação/minimização mais amplas.

### F4 — 75%

**Entregue/verificado:** Cenas verificadas atravessam registros, formatos SVG/PNG e os três perfis de publicação; erro racional por segmento e seis cenas reproduzidas.

**Ainda falta:** Corpus visual amplo, fontes/layout adicionais, curvas e construções mais gerais e revisão externa.

### F5 — 75%

**Entregue/verificado:** Artigo, relatório de engenharia e material didático no AST comum; seis PDFs compilados via Typst/LaTeX e evidências vinculadas às tabelas/figuras.

**Ainda falta:** Blocos editoriais e referências cruzadas mais completos, revisão editorial independente e vínculo semântico de todas as alegações.

### F6 — 75%

**Entregue/verificado:** Sete perfis de registro, SQLite transacional, split semântico, JSONL/Parquet em fluxo, release misto com ficha reconstruída e preparo Hub.

**Ainda falta:** Auditoria de templates/contaminação mais ampla, perfis de escala, migrações adicionais e utilidade externa demonstrada.

### F7 — 70%

**Entregue/verificado:** DOPRI54 e referências analíticas; difusão com FTCS/Euler implícito/Crank–Nicolson, contornos constantes e dados iniciais gerais no perfil.

**Ainda falta:** Eventos, rigidez, outras EDPs, calibração/validação observacional e estudos mais amplos de incerteza.

### F8 — 60%

**Entregue/verificado:** Rede neural real de pixels/equações, nove modelos/ablações, checkpoints reconferidos, controle de vazamento e agentes com pausa/retomada.

**Ainda falta:** Modelos e tarefas científicas mais capazes, benchmarks externos e planejamento mais amplo; nenhum ganho externo novo comprovado.

### F9 — 65%

**Entregue/verificado:** Busca de bases racionais, importação CSL-JSON fixada, holdout separado e replay até dataset, evidência, claims, federação e documento.

**Ainda falta:** Gramáticas mais ricas, recuperação bibliográfica ampla, experimentos realizados e descoberta/reprodução científica independente.

### F10 — 70%

**Entregue/verificado:** Evolução de portfólios em quatro famílias além das EDOs; contratos, holdouts consumíveis, significância/efeito, promoção e rollback.

**Ainda falta:** Regras e algoritmos novos, isolamento/autoridade independentes, inferência sequencial e ganhos amplos; o baseline alternativo positivo é explicitamente mais fraco.

### F11 — 60%

**Entregue/verificado:** Biblioteca idealizada ampliada com elasticidade 3D, RLC, cinética reversível e camadas hidrostáticas; unidades e replay por disciplina.

**Ainda falta:** Modelos mais amplos, dados observados, instrumentos/CAD/controle adicionais e validação por especialistas.

### F12 — 70%

**Entregue/verificado:** Armazenamento assinado durável, confiança/revogação, delta paginado, quarentena e revisões assinadas com conflito/papel por versão.

**Ainda falta:** Rede/federação operacional mais ampla, identidade e expertise reais, revisão independente e escala/recuperação adicionais.

## Por que a nota mudou

A cobertura e a integração receberam pontos por APIs executáveis e novos fluxos:
catálogo de cálculo, primitivas racionais, certificados portáveis, perfis editoriais,
registros mistos, métodos implícitos, treinamento multimodal, programas de descoberta
reexecutáveis, portfólios de solvers e federação durável. Os módulos se conectam em
artefatos verificáveis, em vez de apenas acrescentar pastas.

A operação passou de 5 para 10 após validar o código atual nas matrizes nativas,
empacotamento Windows, wheel isolado, limites de execução, publicação atômica e
reprodução de artefatos. É uma nota do perfil operacional declarado, não garantia
contra toda falha futura. A fase 1 recebeu evidência externa adicional pela
comparação com estatísticas certificadas do NIST. As demais evidências científicas
não demonstradas não receberam pontos novos.

Continuam **zero em E** F7, F8, F9, F11 e F12: faltam as validações externas
apropriadas à amplitude dessas fases. Aprender uma classificação sintética, assinar
um snapshot ou resolver um modelo ideal não equivale a validação científica externa.
F2 e F7 atingem V/20 no fragmento matemático declarado, por testemunhos, verificação
independente, referências analíticas e testes negativos; isso não concede pontos
por dificuldade avançada ou validade de fenômenos reais.

## Evidências executadas

- **443 testes e 312 subtestes aprovados**, sem falhas, erros ou skips locais. O JUnit contém 755 entradas, não 755 funções distintas.
- [CI nativo](../../benchmarks/results/maturity-expansion/ci.json): matriz Python Linux/Windows 3.10/3.12/3.14, perfis científicos com extras em Linux/Windows 3.12 e instalador Windows aprovados no código auditado. O arquivo conserva também os estados individuais dos outros workflows, inclusive eventuais execuções ainda em andamento; não chama pendência de sucesso.
- **Wheel construído e importado de destino isolado**, incluindo os módulos novos de release misto e Discovery; SHA-256 no relatório estruturado.
- **NIST StRD Longley:** sete coeficientes e SSE comparados com referências certificadas; erro relativo máximo nos coeficientes de 2,432568075499757 × 10⁻¹⁵. São dados observados históricos para validação numérica, não prova causal ou física.
- **Multimodalidade:** 256 exemplos de treino, 128 reservados, nove modelos, três seeds e ablações. Acertos equação/imagem/combinação: 86/99/97, 78/99/96 e 88/101/100. Imagem sozinha supera a combinação nas três seeds. Nenhuma das seis comparações pareadas é significativa após a correção aplicada. Nenhum ganho externo novo foi alegado.
- Pesos NPZ sem pickle, protocolo, corpus, previsões e perdas estão [versionados](../../benchmarks/results/maturity-expansion/README.md). O verificador reconstrói pixels, respostas e métricas; aceita diferença de arredondamento float64 até 1e-12 e exige classificações/contagens idênticas. Isso é replay de inferência, não treinamento independente.
- **Portfólios:** baseline uniforme `exact` rejeitado pelo gate; baseline uniforme `alternate`, explicitamente mais fraco, permitiu 18 melhorias/seis empates, zero regressões e redução mediana de 36,2454% no trabalho Python medido. p=3,8147 × 10⁻⁶, alpha corrigido=0,00625. Promoção e rollback foram exercitados. Não é RSI geral ou ganho contra o melhor solver disponível.
- **Laboratório integrado:** 33 operações, três integrais racionais conferidas também por SymPy, quatro perfis de artefatos, JSONL/Parquet, release com ficha, pausa/retomada, busca racional, prova Lean e delta assinado entre armazenamentos locais.
- **Seis PDFs reais**, três perfis via Typst e LaTeX. Figuras e tabelas apontam para as evidências correspondentes. Páginas dos exemplos foram inspecionadas localmente; isso não é revisão editorial independente.
- `math.txt` regenerado e conferido; o projeto Lean não mudou desde o commit anteriormente validado, e a nova prova/bundle Lean foi reexecutada localmente.

## Correção Windows encontrada nesta entrega

O primeiro CI rejeitou a referência externa após conversão de fim de linha.
A transformação LF→CRLF reproduziu a falha de SHA-256. `.gitattributes` agora
preserva os bytes dos arquivos certificados; a verificação de hash não foi
relaxada. O teste usa checkout Git com `core.autocrlf=true` e confirma os bytes.
A validação nativa posterior passou. Os logs públicos inicialmente disponíveis
traziam erro genérico; o diagnóstico foi sustentado pela reprodução e pela
transição do CI após a correção.

## Backlog que continua valendo

O [backlog de 104 itens](PHASES_1_12_COMPLETION_BACKLOG.md) permanece como referência.
Houve entregas completas de componentes e avanço parcial em requisitos extensos;
não se marcou todo item amplo como encerrado por receber uma funcionalidade.

| Fase | Itens com avanço nesta rodada | Pendência principal preservada |
|---|---|---|
| F1 | F01-02/04/05/06/08 | Uniformidade de IR/unidades e abrangência matemática/revisão |
| F2 | F02-01/02/04/06 | Diversidade e dificuldade avançada medidas |
| F3 | F03-01/04/07/08 | Correspondência humana e fragmentos maiores |
| F4 | F04-03/05/06/07/08 | Corpus/revisão visual e geometria mais amplos |
| F5 | F05-01/03/04/06/07 | Blocos/referências completos e revisão externa |
| F6 | F06-01/03/04/05 | Contaminação mais ampla, escala e utilidade externa |
| F7 | F07-01/02/03/04 | Rigidez, eventos, mais equações e dados observados |
| F8 | F08-01/02/03/05/06 | Benchmark externo, modelos mais capazes e planejamento |
| F9 | F09-01/02/03/05/07 | Busca ampla, antecedentes, experimentos e reprodução |
| F10 | F10-01/02/05/07/08 | Novas regras/código sob autoridade independente |
| F11 | F11-02/03/04/06/08 | Validação observacional e especialistas |
| F12 | F12-02/03/06/07/08 | Rede, identidades reais e revisão independente |

O código de assinatura registra chaves configuradas; não autentica por si só
identidade real, expertise ou independência. Dados observacionais validam formato,
unidades e metadados; não viram fatos físicos autenticados automaticamente.
A preparação Hub é local: nenhum dataset foi enviado a serviço externo.

## Reprodução e arquivos

- [Guia das APIs e comandos](../PHASES_MATURITY_EXPANSION.md).
- [Avaliação estruturada e hashes de fontes](../../benchmarks/results/maturity-expansion/assessment.json).
- [Experimentos, pesos e limitações](../../benchmarks/results/maturity-expansion/README.md).

```sh
python -m pip install -e '.[test,formal,graphics,documents,data,research,federation]'
OPENBLAS_NUM_THREADS=1 python -m pytest -q
python tools/validate_longley.py --output .nabla/nist-reproduction.json
OPENBLAS_NUM_THREADS=1 python tools/reproduce_portfolio.py .nabla/portfolio-reproduction
OPENBLAS_NUM_THREADS=1 python tools/reproduce_maturity.py .nabla/maturity-reproduction --learning-directory benchmarks/results/maturity-expansion/multimodal
python tools/build_math_bundle.py --check
```

Use destinos novos. O laboratório completo requer Lean/Mathlib fixados e o backend
PDF escolhido. O campo automático de conclusão da visão continua sem valor
cientificamente validado; esta porcentagem é a estimativa humana da rubrica
explicitada, e não um número produzido pela presença de arquivos.
