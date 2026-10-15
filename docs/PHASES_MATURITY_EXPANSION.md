# Expansão integrada das fases científicas

Esta entrega amplia implementações delimitadas; os resultados científicos ainda
não demonstrados continuam explícitos no relatório de progresso e nas evidências.

## APIs novas

- `calc.catalog.catalog`: 33 operações, áreas, argumentos e contratos. A sessão e
  o CLI `nabla calc` executam regressão ponderada multivariada, Bayes, distribuições,
  séries temporais, grafos, fluxo, SAT, matrizes e comparação racional com domínio.
- `math.calculus.rational_functions`: formas racionais limitadas com identidade
  no domínio comum separada de equivalência dos domínios originais. O construtor
  `forge.constructors.rational_integration` escolhe primitivas racionais e recusa
  candidatos que introduzam novos polos, mesmo removíveis.
- `formal.bundle`: pergunta, enunciado, certificado, revisão declarada e toolchains
  fixadas em pacote reconferível. Uma revisão automática pendente não vira revisão
  humana aceita. O verificador reexecuta Lean/SMT.
- `worlds.pde.diffusion`: FTCS, Euler implícito e Crank–Nicolson, condições iniciais
  finitas arbitrárias e contornos de Dirichlet constantes; residual e estabilidade
  declarados. Crank–Nicolson pode oscilar em passos grandes.
- `datasets.research_record`, `datasets.store`: seis perfis de artefatos, replay
  computacional, metadados obrigatórios, lotes transacionais e isolamento semântico
  entre splits. JSONL e Parquet em fluxo suportam registros mistos. Observações
  verificam formato e metadados, sem autenticar fatos físicos.
- `agents.run_store`: checkpoints SQLite CAS. O planner pausa/retoma e reconfere o
  prefixo por ferramentas científicas conhecidas. Não promete exatamente uma
  execução de efeitos externos; chamada pura pode ser repetida após um crash.
- `training.multimodal_network`: treinamento real com pixels e equações, ablações,
  corpus reservado, pesos abertos e reconferência de inferência. Não é um LLM.
- `discovery.basis_search`: busca exata em bases racionais finitas, com seleção
  apenas na calibração e avaliação em holdout disjunto. `knowledge.bibliography_import`
  importa snapshots CSL-JSON com hash, fonte, data e licença; não prova novidade global.
- `evolution.portfolio`: seleção de estratégias por família, reserva consumível,
  contrato do avaliador, efeito mínimo, significância, promoção CAS e rollback.
  Continua limitado a estratégias existentes, sem edição irrestrita de código.
- Novos modelos: elasticidade isotrópica 3D, fasores RLC, cinética A↔B e pressão
  em camadas. Todos têm unidades, limites, verificações e replay de evidências.
- `knowledge.storage`: snapshots assinados duráveis, delta paginado, confiança e
  revogação persistentes, quarentena e reconciliação. `peer_review` autentica
  assinaturas de revisões vinculadas à versão, conservando conflitos/papéis e a
  distinção entre chave configurada e identidade/expertise real.
- `documents.profiles`: artigo, relatório de engenharia e material didático no
  mesmo AST, exigindo evidências e limitações; todos usam HTML/LaTeX/Typst/PDF.

## Reprodução

```sh
python -m pip install -e '.[test,formal,graphics,documents,data,research,federation]'
OPENBLAS_NUM_THREADS=1 python -m pytest -q
python tools/validate_longley.py --output .nabla/longley-new.json
OPENBLAS_NUM_THREADS=1 python tools/reproduce_portfolio.py .nabla/portfolio-new
OPENBLAS_NUM_THREADS=1 python tools/reproduce_maturity.py .nabla/maturity-new --learning-directory benchmarks/results/maturity-expansion/multimodal
python tools/build_math_bundle.py --check
```

O laboratório integrado exige o projeto Lean/Mathlib fixado e um compilador PDF.
Use destinos novos; os comandos recusam sobrescrever os artefatos anteriores.
O workflow `Scientific maturity profiles` executa os perfis e suas falhas em Linux
 e Windows com os extras instalados. Estado aprovado depende da execução nativa,
 não da mera presença do arquivo de workflow.
