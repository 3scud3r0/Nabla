# NABLA ∇ — Visão de 2026 a 2056 e além

> **Plano mestre de arquitetura, pesquisa científica, geração de conhecimento e evolução tecnológica.**  
> **Estado:** visão e arquitetura propostas, **não** funcionalidades já implementadas.  
> **Data:** 14 de outubro de 2026.  
> **Documento complementar:** [Plano mestre técnico e roteiro detalhado](docs/PLANO_MESTRE_2026_2056.md).

## Declaração da visão

O **Nabla** não deve ser apenas uma calculadora avançada, um gerador de datasets ou um conjunto de scripts para pesquisadores.

A visão é construir, progressivamente, uma **infraestrutura científica computacional universal**, utilizável inicialmente em um computador doméstico, capaz de **representar, calcular, construir, demonstrar, refutar, simular, visualizar, documentar e aperfeiçoar modelos de conhecimento**.

E, sobretudo, produzir dados de treinamento científico cuja qualidade venha da estrutura matemática, dos mecanismos de verificação, da diversidade de problemas e da procedência das evidências — não simplesmente da quantidade de exemplos.

O sistema terá duas finalidades simultâneas:

- **Para seres humanos:** um ambiente científico completo, com matemática simbólica, computação numérica, gráficos profissionais, modelagem, simulações, documentos LaTeX/Typst/PDF, programação científica e experimentos reproduzíveis.
- **Para inteligências artificiais:** uma fábrica de problemas, soluções, tentativas, demonstrações, contraexemplos, experimentos, simulações e representações multimodais verificáveis, potencialmente úteis para treinar e avaliar sistemas de raciocínio cada vez mais avançados.

> **Nabla não gera apenas respostas. Gera problemas, caminhos de descoberta, soluções, evidências, representações e novos métodos para produzir e verificar conhecimento.**

Esta é uma visão suficientemente ampla para atravessar décadas. Não é possível antecipar quais descobertas ocorrerão, quando ocorrerão ou se o sistema contribuirá para uma superinteligência. A arquitetura deverá ser preparada para incorporar avanços científicos sem reconstruir tudo do zero.

## 1. A arquitetura fundamental

O Nabla não terá dois programas separados chamados Data e Calc. Terá **um núcleo científico compartilhado** e vários modos de operação.

```text
                                  ∇ NABLA
            Núcleo semântico, matemático e de evidências
                                      |
          +---------------------------+---------------------------+
          |                           |                           |
        CALC                        FORGE                       PROVE
  Álgebra e cálculo          Geração inversa               Prova e refutação
          |                           |                           |
        STUDIO                     WORLDS                    DISCOVERY
 PDF, LaTeX, Typst          Simulações e modelos        Hipóteses e pesquisa
          |                           |                           |
      KNOWLEDGE                     EVOLVE                      AGENTS
 Grafo científico             RSI controlado            Pesquisadores de IA
          +---------------------------+---------------------------+
                                      |
                           NABLA EVIDENCE LAYER
           Identidade de conteúdo | Linhagem | Certificados
              Testes | Metadados | Versões | Reprodução
```

A **camada de evidências** atravessará todos os modos. Um resultado calculado, um teorema, uma imagem geométrica e um vídeo de simulação não podem representar quatro verdades contraditórias: todos devem apontar para o mesmo modelo e para evidências apropriadas ao respectivo domínio.

### O componente de maior prioridade: geração e resolução científica bidirecional

O fluxo tradicional é:

```text
Problema → Método → Solução
```

O Nabla também explorará a direção inversa:

```text
Solução conhecida → Construção inversa → Problema não trivial
```

O aspecto decisivo será **fechar ambos os caminhos por verificação independente**, não confiar apenas na resposta fornecida pelo gerador.

```text
Objeto matemático, solução ou estrutura conhecida
    ↓ Construção inversa, restrições e parametrização
Problema gerado + premissas
    ↓ Solver independente, IA exploradora e busca
Soluções candidatas e trajetórias de raciocínio
    ↓ Prova · Testes · Refutação · Validação
Evidências e classificação de dificuldade
    ↓ Curadoria, formatos e controle de qualidade
Dataset + gráfico + documento + experimento reproduzível
```

A arquitetura começa com fatoração e integração e poderá ganhar geradores específicos para geometria, álgebra abstrata, combinatória, teoria dos números, EDOs, problemas inversos, programação verificada, otimização e outras disciplinas.

**Não existe uma técnica universal que automaticamente funcione em todas as ciências.** Cada área exige definições próprias de solução, validade e evidência.

### Antecedentes: AlphaGeometry e pesquisas da OpenAI

O Nabla pode buscar uma **aproximação independente de capacidades observáveis**, e não uma cópia de código privado inacessível:

- [AlphaGeometry (Google DeepMind)](https://github.com/google-deepmind/alphageometry): provas geométricas apoiadas por sistemas neurais e simbólicos.
- [AlphaGeometry2](https://github.com/google-deepmind/alphageometry2): componentes públicos de seu motor geométrico.
- [SymbolicMathematics (FAIR)](https://github.com/facebookresearch/SymbolicMathematics): construção sintética e inversa para problemas simbólicos, incluindo integração.
- [Sharing AI progress in mathematics (OpenAI, 6/10/2026)](https://openai.com/index/sharing-ai-progress-in-mathematics/): resultados e artefatos matemáticos publicados.
- [OpenAI math](https://github.com/openai/math): materiais abertos; não deve ser presumido como publicação do sistema interno de pesquisa que os produziu.

A integração proposta combina construção inversa, busca neuro-simbólica, geração de hipóteses, falsificação, verificação e documentação científica em uma ferramenta pessoal.

---

## 2. Evolução prevista durante três décadas

Os anos abaixo são **horizontes de planejamento, não garantias de entrega**. As fases dependem de resultados anteriores, hardware, colaboradores, financiamento e validação independente.

| Horizonte | Evolução pretendida | Capacidade central |
|---|---|---|
| **2026–2027** | Fundação científica | Núcleo matemático, calculadora e contratos de evidência |
| **2027–2028** | Forja matemática | Construção inversa, provas e datasets exigentes |
| **2028–2030** | Ciência multimodal | Geometria, imagens, LaTeX, Typst, PDF e documentos |
| **2030–2033** | Mundos computacionais | Simulação, análise numérica e modelos físicos |
| **2033–2037** | Laboratório de descoberta | Hipóteses, experimentos, contraexemplos, agentes |
| **2037–2042** | RSI científico avançado | Melhoria controlada de algoritmos e métodos |
| **2042–2048** | Integração de disciplinas | Engenharia, materiais, química, física e conhecimento |
| **2048–2056+** | Infraestrutura epistemológica | Pesquisa assistida e conhecimento científico versionado |

A evolução é **cumulativa**. A calculadora continua importante quando a forja começa; a forja continua quando surgem simulações; o Studio não substitui os verificadores.

---

## 3. Arquitetura completa de pastas e arquivos

A árvore a seguir é uma **arquitetura-alvo**, não um conjunto de arquivos existentes. Antes de criar qualquer caminho, o repositório deve ser auditado. Componentes atuais de `nablamath`, CLI, SQLite, Lean e site serão preservados até que uma migração com testes justifique mudanças.

```text
Nabla/
├── src/nablamath/
│   ├── core/          # Linguagem científica interna
│   ├── symbolic/      # Álgebra simbólica e e-graphs
│   ├── math/          # Motores matemáticos
│   ├── calc/          # Calculadora e sessões
│   ├── forge/         # Geração inversa de problemas
│   ├── verify/        # Conferência de resultados
│   ├── falsifier/     # Refutação e contraexemplos
│   ├── formal/        # Lean, SMT e certificados
│   ├── datasets/      # Curadoria e treinamento
│   ├── graphics/      # Gráficos, imagens e geometria
│   ├── documents/     # LaTeX, Typst, PDF e relatórios
│   ├── worlds/        # Simulação física e numérica
│   ├── discovery/     # Novos modelos e conjecturas
│   ├── knowledge/     # Grafo de conhecimento
│   ├── evolution/     # RSI e otimização
│   ├── agents/        # Agentes científicos
│   ├── runtime/       # Execução e limites de recursos
│   ├── adapters/      # Bibliotecas externas
│   ├── export/        # Formatos e publicação
│   └── desktop/       # Interface científica local
├── lean/Nabla/         # Provas formais
├── schemas/            # Contratos de dados
├── benchmarks/         # Desafios e comparações
├── tests/              # Testes independentes
├── templates/          # Modelos gráficos e editoriais
├── examples/           # Experimentos completos
├── configs/            # Perfis e recursos
├── packages/           # Componentes opcionais Rust/C++
├── docs/               # Engenharia e ciência
├── datasets/           # Amostras e manifestos
├── tools/              # Desenvolvimento
├── legacy/             # Histórico preservado
├── services/           # Rede opcional futura
└── website/            # Documentação pública
```

A nomenclatura é uma intenção arquitetural. Não é uma instrução de criar automaticamente pastas vazias, duplicar módulos existentes ou renomear o pacote Python.

---

## 4. Etapas de construção, uma por uma

### Fase 0 — Auditoria, recuperação e arquitetura (2026)

Estabelecer a verdade sobre o Nabla atual: capacidades executáveis, erros, compatibilidade, testes e histórico. **Não adicionar funcionalidades antes da estabilização.**

| Arquivo prioritário | Responsabilidade |
|---|---|
| `docs/audits/BASELINE_2026_10.md` | Commit, ambiente e resultados da auditoria |
| `docs/architecture/current-modules.md` | Mapa de módulos existentes |
| `docs/adr/0001-product-scope.md` | Escopo local-first e papéis do produto |
| `docs/adr/0002-canonical-ast.md` | Representação matemática canônica |
| `tests/regression/test_public_api.py` | Compatibilidade da API pública |
| `.github/workflows/ci.yml` | Testes multiplataforma |

Inspecionar expressão, álgebra, e-graph, diferenciação, integração, Markov, proveniência, SQLite, Lean e interface local. **Saída:** núcleo importável e instalável, erros corrigidos e testes registrados.

### Fase 1 — Calculadora científica de alto nível (2026–2027)

Estabelecer a linguagem científica que sustentará todas as próximas fases.

| Área | Cobertura pretendida |
|---|---|
| Álgebra | Polinômios, fatoração, sistemas, simplificação sob condições |
| Álgebra linear | Matrizes, espaços vetoriais, sistemas, decomposições |
| Cálculo | Limites, derivadas, integrais, séries, EDOs delimitadas |
| Matemática discreta | Combinatória, grafos, recorrências, lógica |
| Probabilidade | Distribuições, Markov, processos discretos |
| Estatística | Estimação, testes, intervalos, séries temporais |
| Matemática numérica | Precisão, condicionamento, erro |
| Otimização | Restrições e condições de otimalidade |
| Geometria | Coordenadas, cônicas, transformações, construções |

**Arquivos propostos:** `core/semantic_ir.py`, `core/types.py`, `core/units.py`, `core/precision.py`, `core/obligations.py`, `calc/session.py`, `calc/notebook.py`, `math/linear_algebra/`, `math/calculus/`.

`semantic_ir.py` representaria o **significado** de uma expressão independentemente da notação na tela. LaTeX seria uma apresentação do objeto, não a fonte canônica da matemática.

**Saída:** resultados reprodutíveis, domínio declarado, restrições explícitas, limitação identificada. Não supor cobertura de toda a matemática em um ano.

### Fase 2 — Nabla Forge: fábrica científica inversa (2027–2028)

Construir problemas a partir de soluções, testemunhos, invariantes e estruturas previamente conhecidos.

| Problema desejado | Construção inversa |
|---|---|
| Integral difícil | Escolher primitiva e derivar |
| Polinômio fatorável | Escolher fatores e multiplicar |
| Sistema linear | Escolher solução e construir coeficientes compatíveis |
| Matriz com espectro | Escolher decomposição e reconstruir |
| Otimização | Escolher ótimo e construir condições de otimalidade |
| Cadeia de Markov | Escolher propriedades estacionárias e construir transições |
| Identidade algébrica | Aplicar reescritas semanticamente válidas |
| Contraexemplo | Construir violação de conjectura delimitada |

**Arquivos:** `forge/task_spec.py`, `forge/reverse_builder.py`, `forge/sampling.py`, `forge/difficulty.py`, `forge/deduplicate.py`, `forge/constructors/integration.py`, `forge/constructors/polynomial.py`, `forge/constructors/linear_systems.py`, `verify/trace.py`, `datasets/splits.py`.

A dificuldade precisa ser calibrada por solvers, estratégias, recursos e benchmarks — **não** somente por tamanho da expressão ou duração isolada de Z3.

**Saída:** problemas reproduzíveis, soluções verificadas por método independente, diversidade comprovada, deduplicação e dificuldade calibrada.

### Fase 3 — Nabla Prove e Falsifier (2028–2029)

De calculadora rastreável para um ambiente que também tenta demonstrar e refutar.

- Traduzir classes delimitadas de problemas para Lean 4.
- Conferir certificados e provas no sistema adequado.
- Tornar hipóteses e obrigações explícitas.
- Usar SMT em fragmentos apropriados.
- Buscar contraexemplos, reduzir exemplos mínimos e registrar falhas.

**Arquivos:** `formal/lean_bridge.py`, `formal/lean_checker.py`, `formal/smt_bridge.py`, `formal/translation_review.py`, `falsifier/search.py`, `falsifier/shrink.py`, `verify/certificate.py`, `lean/Nabla/`.

**Saída:** certificados reproduzíveis e enunciados formalizados correspondentes às perguntas originais. **Igualdade exata não equivale automaticamente a teorema formal.**

### Fase 4 — Geometria, imagens científicas e visualizações (2028–2030)

Gerar diagramas de geometria euclidiana, construções coordenadas, campos vetoriais, retratos de fase e outros elementos visuais que estejam ligados ao modelo matemático.

**Arquivos:** `graphics/scene_graph.py`, `graphics/geometry_constraints.py`, `graphics/coordinate_system.py`, `graphics/svg_renderer.py`, `graphics/raster_renderer.py`, `graphics/layout.py`, `forge/constructors/geometry.py`, `verify/geometry.py`.

O sistema de cena conhece pontos, curvas, relações e equações. A imagem é uma **representação** desses objetos, não uma fonte independente de verdade. Renderização artística por IA será opcional e não substituirá a matemática quando precisão geométrica for exigida.

**Saída:** diagramas editáveis e reprodutíveis, exportação vetorial/raster, testes visuais, metadados e conferência das propriedades geométricas.

### Fase 5 — Nabla Studio: LaTeX, Typst, PDF e publicação (2029–2030)

Gerar artigos matemáticos, relatórios de engenharia, apostilas, gráficos e demonstrações profissionais a partir de experimentos rastreáveis.

**Arquivos:** `documents/document_model.py`, `documents/equation_blocks.py`, `documents/citations.py`, `documents/figures.py`, `documents/latex_exporter.py`, `documents/typst_exporter.py`, `documents/pdf_builder.py`, `documents/html_exporter.py`, `templates/research_paper/`.

Um modelo de documento independente deverá produzir LaTeX, Typst, PDF e outros formatos. Relatórios poderão incluir hipótese, método, resultados, gráficos, provas, limitações e referências. Documentos sintéticos serão **marcados explicitamente** como sintéticos.

**Saída:** documentos compiláveis, visualmente revisados, com dados e equações rastreáveis, sem alegações científicas inventadas.

### Fase 6 — Nabla Dataset: dados científicos de treinamento (2029–2031)

Armazenar não só perguntas e respostas, mas problemas, soluções, tentativas, certificados, figuras, séries, provas, limitações e manifestos.

**Arquivos:** `datasets/schema.py`, `datasets/serializer.py`, `datasets/semantic_fingerprint.py`, `datasets/split_policy.py`, `datasets/curation.py`, `datasets/quality_gate.py`, `datasets/model_card.py`, `export/parquet.py`, `export/jsonl.py`, `export/bundle.py`, `export/huggingface.py`.

Licença, origem, escopo, limitações, dificuldades, defeitos, partições reservadas e versão dos verificadores serão obrigatórios conforme o perfil do dataset. **Quantidade não é sinônimo de utilidade.** Mesmo dados corretos podem ser redundantes, triviais ou inadequados para generalização.

**Saída:** qualidade demonstrada em avaliações externas e problemas inéditos, e não apenas gigabytes gerados.

### Fase 7 — Nabla Worlds: simulações científicas (2030–2033)

Transformar equações em fenômenos computacionais com modelos, parâmetros, unidades, métodos numéricos e tolerâncias identificáveis.

**Arquivos:** `worlds/model_spec.py`, `worlds/ode/`, `worlds/pde/`, `worlds/integrators/`, `worlds/mesh/`, `worlds/conservation.py`, `worlds/convergence.py`, `worlds/validation.py`, `worlds/sensitivity.py`, `worlds/animation.py`.

Evoluir de problemas com solução analítica conhecida para integrações numéricas, EDOs e EDPs selecionadas, malhas, análise de erro e confronto com dados observados.

**Saída:** simulações com convergência, condições e limites de modelo, além de validação experimental quando possível. Uma figura realista não comprova um fenômeno real.

### Fase 8 — Aprendizado multimodal e agentes científicos (2032–2035)

Produzir dados e experiências que conectem diagramas, equações, texto, estados de simulação, provas e raciocínio de agentes.

**Arquivos:** `agents/tool_registry.py`, `agents/planner.py`, `agents/proposals.py`, `agents/permissions.py`, `datasets/multimodal.py`, `datasets/alignments.py`, `training/curriculum.py`, `training/evaluation.py`, `training/contamination.py`, `training/ablation.py`.

**Saída:** medir, em avaliações externas e problemas inéditos, se modelos treinados com os dados realmente melhoram. Resultados negativos também devem ser publicados.

### Fase 9 — Nabla Discovery: investigação de hipóteses (2033–2037)

Investigar regularidades, propor modelos, buscar contraexemplos, conectar teoremas e planejar experimentos que discriminem hipóteses concorrentes.

**Arquivos:** `discovery/hypothesis.py`, `discovery/symbolic_regression.py`, `discovery/experimental_design.py`, `discovery/theorem_search.py`, `discovery/novelty_screen.py`, `knowledge/claim_graph.py`, `knowledge/literature.py`, `falsifier/counterexample_miner.py`.

**Saída:** hipóteses avaliadas, antecedência bibliográfica consultada, evidência, refutação e reprodução independente quando pertinente. Uma expressão inédita para o software não é automaticamente uma descoberta científica nova.

### Fase 10 — Nabla Evolution: recursive self-improvement (2037–2042)

Implementar RSI **científico e controlado**: melhorar algoritmos, estratégias, sequências de regras, seleção de problemas e geração de candidatos sob avaliadores independentes.

**Arquivos:** `evolution/policy_genome.py`, `evolution/search.py`, `evolution/proposal_validator.py`, `evolution/evaluator.py`, `evolution/holdout_manager.py`, `evolution/statistical_tests.py`, `evolution/lineage.py`, `evolution/rollback.py`, `evolution/release_gate.py`.

O proponente não poderá alterar silenciosamente as avaliações que julgam suas melhorias. Propostas de código exigirão isolamento, testes, revisão e reversão. O protótipo `nabla_improve.py` fornecido pelo mantenedor é um antecedente **limitado a políticas de ajuste de curvas**, não demonstra autoaperfeiçoamento geral.

**Saída:** ganhos de capacidade ou eficiência sobre baselines, com holdouts inéditos, testes estatísticos e regressões controladas. Não prometer progresso irrestrito.

### Fase 11 — Engenharia e novas disciplinas (2042–2048)

Ampliar a infraestrutura para domínios com bibliotecas, modelos, especialistas e validação específica.

**Pastas:** `domains/engineering/`, `domains/circuits/`, `domains/materials/`, `domains/chemistry/`, `domains/control/`, `domains/earth/`, `domains/biology/`, `worlds/multiphysics/`, `adapters/instruments/`.

Possíveis aplicações: circuitos, materiais, química computacional, CAD paramétrico, controle e física multifásica. A incorporação de um domínio não significa domínio universal nem validade experimental automática.

### Fase 12 — Conhecimento científico vivo (2048–2056+)

Construir um conhecimento científico versionado: dependências, evidências, revisões, refutações, proveniência e colaboração entre pesquisadores.

**Arquivos:** `knowledge/federation.py`, `knowledge/semantic_reconciliation.py`, `knowledge/versioned_claims.py`, `knowledge/dependency_impact.py`, `knowledge/peer_review.py`, `knowledge/provenance_audit.py`, `discovery/research_program.py`, `agents/scientific_teams.py`.

**Saída:** rastrear de que um resultado depende, como foi testado e quais evidências o contradizem. Ciência incorpora incerteza e modelos concorrentes; não é um banco de dados infalível de verdades.

### Fase 13 — Além de 2056: horizonte aberto

A arquitetura deverá suportar motores matemáticos novos, novas teorias, hardware ainda inexistente, outras representações e IA de gerações futuras. O que deve sobreviver são **contratos científicos, proveniência, compatibilidade e mecanismos de verificação** — não uma tecnologia específica.

---

## 5. O verdadeiro dataset extraordinário do Nabla

A unidade central não será simplesmente `pergunta → resposta`. Será um **artefato científico completo**, conectando problema, domínio, solução, verificações, tentativas, visualizações, simulações, dados de treino e publicações.

Exemplo conceitual de um problema de geometria orbital:

```text
artifacts/orbit-experiment-0001/
├── problem.json             # Enunciado estruturado
├── assumptions.json         # Hipóteses e domínio
├── model.json               # Modelo semântico
├── solution.json            # Solução de referência
├── solver_trace.jsonl       # Processo de cálculo
├── verification.json        # Evidências e resultados
├── counterexamples.jsonl    # Falhas e casos-limite
├── geometry/
│   ├── orbit.svg
│   └── orbit.png
├── simulation/
│   ├── trajectory.parquet
│   └── convergence.json
├── formal/
│   └── obligations.lean
├── document/
│   ├── article.tex
│   ├── article.typ
│   └── article.pdf
├── dataset/
│   ├── examples.parquet
│   └── dataset_card.md
└── manifest.json            # Versões, hashes e origens
```

Um `.lean` só é uma prova depois de estar completo e ser verificado pelo sistema formal apropriado. Uma simulação requer sua própria análise de convergência, precisão e validade do modelo. O mesmo padrão, com perfis específicos, pode servir para álgebra, combinatória, geometria, programação, física e outras áreas.

## 6. Como computadores comuns contribuiriam

A viabilidade local depende de **algoritmos especializados e verificadores baratos**, e não apenas de modelos gigantes.

| Recurso | Trabalho compatível com o perfil |
|---|---|
| CPU moderna, 16–32 GB RAM | Matemática exata, geração inversa, verificadores, provas delimitadas, PDFs e pequenas simulações |
| CPU + GPU de 8–16 GB | Alguns modelos locais quantizados, cálculos acelerados, renderização e exploração guiada por IA |
| Estação com 64–128 GB RAM e GPU forte | Lotes maiores, modelos mais exigentes, simulações e treino especializado |
| Cluster/HPC opcional | Treinamento extenso, simulações grandes, tarefas acima dos limites pessoais |

Um PC doméstico **pode produzir dados cientificamente valiosos**, mas não substitui datacenters universalmente: certos problemas requerem memória, tempo, precisão, dados experimentais ou escala que não cabem na máquina pessoal.

Perfis de execução deverão limitar RAM, CPU, GPU, disco, tempo, energia, pausas e checkpoints, com consentimento do usuário.

## 7. O papel do RSI desde a fundação

Mesmo que a automação mais avançada venha muito depois, sua arquitetura deve estar prevista:

```text
Nabla identifica um gargalo
    ↓
Gera uma proposta de melhoria
    ↓
Valida o contrato; executa em ambiente isolado
    ↓
Compara contra baseline e testes reservados
    ↓
Aceita sob revisão, rejeita ou reverte
```

O arquivo `nabla_improve(1).py` anexado pelo mantenedor contém um exemplo delimitado da lógica de políticas sujeitas a avaliadores. A proposta é extrair contratos úteis sem presumir RSI geral ou ganhos ilimitados.

## 8. Por que Nabla é maior que PDFs ou datasets

PDF profissional demonstra capacidade editorial; prova formal sustenta uma proposição sob hipóteses; simulação descreve um modelo; descoberta científica depende de evidência e antecedentes. O Nabla deverá **integrar essas representações sem confundi-las**.

- Cálculo alimenta geração de problemas.
- Geração alimenta testes, modelos e agentes.
- Verificação aumenta a confiabilidade dos dados.
- Visualização acrescenta raciocínio e percepção multimodal.
- Documentos conectam resultados técnicos à comunicação humana.
- Simulações acrescentam comportamento temporal e incerteza.
- Descoberta reutiliza o conjunto de ferramentas anteriores.
- RSI procura melhorar eficiência e capacidade dos métodos.
- O grafo de conhecimento conserva relações entre resultados.

Essa combinação **não prova** que o Nabla produzirá dados suficientes para uma superinteligência. Pode torná-lo, porém, uma infraestrutura valiosa para desenvolver e avaliar raciocínio matemático e científico.

## 9. Critérios de aprovação para avançar

Uma fase não fecha porque muitos arquivos foram escritos.

| Dimensão | Pergunta central |
|---|---|
| Correção | Está correto no domínio declarado? |
| Independência | Um verificador ou método diferente confirma? |
| Reprodutibilidade | Outra instalação reconstrói ou confere a evidência? |
| Utilidade | A funcionalidade ajuda pessoas ou melhora avaliações relevantes? |
| Sustentabilidade | O projeto pode manter a capacidade sem comprometer o núcleo? |

Também serão exigidos testes de regressão, casos adversariais, dados inéditos, orçamento de recursos e revisão de segurança.

## 10. Ordem exata de codificação **após** aprovação da arquitetura

1. **Recuperar a base canônica:** auditar checkout/HEAD, estabilizar CLI, módulos simbólicos e histórico.
2. **Formalizar o objeto científico:** contratos de expressões, problemas, hipóteses, evidências, soluções, linhagem e representações.
3. **Construir o primeiro ciclo completo:** cálculo → construção inversa → solver independente → verificação → dataset → imagem matemática → LaTeX/Typst → PDF.
4. **Medir antes de ampliar:** benchmarks contra bibliotecas maduras, dificuldades, diversidade, contaminação, custo e generalização.
5. **Expandir sem perder garantias:** geometria, formalização, multimodalidade, simulação, agentes, descoberta, RSI e novos domínios.

O primeiro ciclo deve caber em uma máquina comum, ser reproduzível e servir de referência para novas disciplinas.

---

## Identidade final e limites

**Nabla é um ambiente científico no presente, uma infraestrutura de geração de conhecimento no médio prazo e uma potencial plataforma de pesquisa assistida cada vez mais autônoma no longo prazo.**

A arquitetura deve permitir a expansão **sem pressupor que ela acontecerá automaticamente**. Este documento formaliza a direção; **não implementa** as fases. A implementação começa pela auditoria e estabilização do código atual, mediante mudanças pequenas, reversíveis e testadas.

Para contratos, lista de arquivos por fase, matriz de áreas científicas, hardware, governança e critérios de fechamento, consultar [PLANO_MESTRE_2026_2056.md](docs/PLANO_MESTRE_2026_2056.md).
