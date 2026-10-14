# Fases 9–12: investigação, evolução controlada e conhecimento versionado

Implementações delimitadas dos caminhos prioritários de `vision.md`, com
integração às fases anteriores. Isso não equivale a descoberta científica geral,
RSI irrestrito ou conclusão do horizonte 2026–2056. Os critérios e resultados da
[auditoria executável](audits/SCIENTIFIC_ACCEPTANCE_2026_10.md) distinguem essas coisas.

## Executar

```sh
python -m pip install -e '.[test,formal,graphics,documents,data,research]'
nabla research-laboratory .nabla/research-912
```

O laboratório cria um diretório novo com investigação de uma hipótese, estudos de
políticas, banco de holdouts, histórico de liberações/reversão, resultados de dez
modelos disciplinares, equipe local, evidências reexecutáveis, histórico de claims,
consulta bibliográfica, revisão declarada, federação com versões concorrentes e
artigo HTML/LaTeX/Typst/PDF com fontes anexadas. O PDF usa Typst. Não publica dados
na rede nem contata pesquisadores ou instrumentos.

## Fase 9 — Discovery

| Arquivo | Comportamento executável |
| --- | --- |
| `discovery/hypothesis.py` | Expressões univariadas limitadas, domínio, unidades, observações exatas, incertezas e procedência |
| `discovery/symbolic_regression.py` | Mínimos quadrados racionais, gramática polinomial até grau seis, penalidade de complexidade e escolha somente na calibração |
| `discovery/experimental_design.py` | Classifica pontos não observados por discordância normalizada entre hipóteses; não executa o experimento |
| `discovery/theorem_search.py` | Normalização polinomial preservando obrigações de domínio, ou chamada explícita a Lean/SMT |
| `discovery/novelty_screen.py` | Busca no corpus declarado e equivalentes locais; ausência de ocorrência não é novidade mundial |
| `knowledge/claim_graph.py` | Dependências acíclicas e relações explícitas de suporte/contradição entre revisões |
| `knowledge/literature.py` | Snapshot bibliográfico, consultas e recibos com identidade do corpus |
| `falsifier/counterexample_miner.py` | Conserva tentativas, testemunhos, reduções e resultados negativos da busca finita |

`discovery/research_program.py` conecta ajuste, holdout, planejamento, consulta e
refutação, com reexecução do relatório completo. O exemplo usa dados sintéticos de
x² e metadados locais do artigo de Brunton, Proctor e Kutz (2016,
DOI 10.1073/pnas.1517384113). Não baixa o artigo nem declara uma revisão exaustiva da
literatura. O normalizador exato não é marcado como prova Lean. Uma hipótese que
combina com observações finitas continua sendo hipótese sobre o fenômeno.

```sh
nabla discover .nabla/discovery.json
```

## Fase 10 — Evolution

`policy_genome.py` admite somente políticas declarativas Euler/RK4, orçamento de
passos e linhagem. `proposal_validator.py` fixa contrato, tolerância, custos e
identidade dos arquivos do avaliador. A digest usa texto UTF-8 normalizado para
ser independente de CRLF. Alterações exigem um novo contrato revisado.

`search.py` seleciona descendentes apenas na calibração. `holdout_manager.py`
reserva casos persistentes em SQLite, impede duplicatas entre suites no mesmo
vault, verifica contaminação e consome o holdout **antes** da avaliação. Falhas não
restauram o direito de reutilizar os casos. Os dados podem aparecer no recibo após
o consumo para permitir rechecagem; o vault não é um mecanismo de segredo contra
código hostil com acesso ao mesmo sistema de arquivos.

`evaluator.py` mantém a API anterior. `statistical_tests.py` acrescenta teste exato
pareado; o novo contrato usa alpha/max_generations como correção conservadora
entre tentativas. Casos sintéticos relacionados não garantem independência
estatística. `release_gate.py` exige recibo do gerenciador confiável e reexecuta a
avaliação; não confia em `accepted=true`. Verificação matemática de um recibo
exportado e autorização de liberação são operações distintas.

`lineage.py` conserva eventos encadeados. `rollback.py` mantém estado persistente,
promoção com comparação da política ativa, propostas rejeitadas e reversão apenas
para ancestrais aceitos. O exemplo completou duas gerações aceitas, conservou uma
proposta ruim rejeitada e demonstrou rollback para o baseline.

```sh
nabla evolve .nabla/evolution --generations 2
```

Esta é evolução recursiva de um espaço pequeno de políticas numéricas. Não gera
patches arbitrários nem altera os próprios testes. O orquestrador, o contrato e o
filesystem são a fronteira de confiança; não se promete isolamento contra um
administrador malicioso ou autoaperfeiçoamento científico geral.

## Fase 11 — Disciplinas

Os parâmetros físicos usam `Quantity` e conversão SI; unidades incompatíveis e
regimes fora dos limites são rejeitados. Os resultados contêm entradas, unidades,
resíduos/checks, limitações e identidade. Os modelos são reexecutados na auditoria.

| Pasta | Modelo e referência |
| --- | --- |
| `domains/engineering/` | Barra axial e viga em balanço Euler–Bernoulli, pequenas deformações |
| `domains/circuits/` | Rede CC racional existente, Kirchhoff e balanço de potência preservados |
| `domains/materials/` | Termoelasticidade linear unidimensional e decomposição de deformações |
| `domains/chemistry/` | Fórmulas neutras com elementos conhecidos/parênteses, balanceamento estequiométrico primitivo e equilíbrio ideal A⇌B |
| `domains/control/` | Sistemas SISO normalizados de dimensão 1–2, Hurwitz, controlabilidade, observabilidade e resposta RK4 |
| `domains/earth/` | Hidrostática com densidade/gravidade constantes e balanço de pressão |
| `domains/biology/` | Crescimento logístico comparado à solução analítica e SIR fechado com conservação/população positiva |
| `worlds/multiphysics/` | Acoplamento eletrotérmico com resistência dependente da temperatura, referência analítica e balanço energético |
| `adapters/instruments/` | CSV offline, calibração ganho/offset, propagação de incerteza e tempo crescente |

```sh
nabla domain-suite .nabla/domains.json
```

Esses modelos não significam domínio universal de engenharia, química, materiais,
geociências ou biologia. Não há validação experimental autenticada. O adaptador
não abre conexões com dispositivos; calibração, identidade e origem são declaradas.

## Fase 12 — Conhecimento vivo

`versioned_claims.py` preserva formato/IDs e API do ledger anterior e acrescenta
importação/exportação estrita em memória. Revisões referem dependências imutáveis;
refutações não apagam resultados históricos. `dependency_impact.py` marca versões
obsoletas/refutadas e resultados que precisam de nova revisão, sem editar status
científico silenciosamente.

`provenance_audit.py` resolve referências e reexecuta traces, provas formais,
modelos disciplinares, consultas bibliográficas, refutações, programas de pesquisa
e avaliações de políticas. Observações externas só recebem integridade de
conteúdo; o software não autentica instrumentos ou implica que uma referência
prove automaticamente a prosa de uma claim.

`federation.py` troca snapshots por arquivos com hashes e, opcionalmente,
autenticação HMAC com chaves compartilhadas fornecidas pelo chamador. A assinatura
não comprova verdade científica ou identidade humana. Por padrão snapshots sem
origem autenticada são rejeitados; o exemplo local usa `allow_unsigned=True`
explicitamente e informa isso. Nenhuma chave é gerada/publicada para produção.

`semantic_reconciliation.py` propõe equivalência apenas para texto exato ou
polinômios com domínio, unidades, pressupostos e obrigações preservados. Revisões
sucessivas não são confundidas com forks. Histórias concorrentes são conservadas;
não há escolha automática de uma verdade única.

`peer_review.py` exige autoria declarada, revisores distintos, especialidade e
checagem de conflitos conhecidos; conserva versões e pareceres negativos. Uma
recomendação local não muda a claim nem comprova revisão externa independente.
`agents/scientific_teams.py` separa proponente e verificador, valida todas as
capacidades antes de executar e conserva recibos reexecutáveis. A execução de uma
verificação que rejeita um candidato é distinguida da aprovação desse candidato.
A equipe é composta por papéis locais declarados, não por cientistas externos.

```sh
nabla knowledge-audit .nabla/research-912/knowledge.json --allow-unsigned
```

## Validação e limites da entrega

Testes cobrem dados reservados, grau seis racional, domínios parciais, dimensões,
refutações, recibos adulterados, consumo único, orçamento, significância,
liberação/rejeição/rollback, balanços físicos, calibração, conflitos, autenticação,
forks, pares locais e auditoria reexecutável. A integração gera artigo compilado
e revisado visualmente. O [relatório de aceitação](../benchmarks/results/vision-acceptance-2026-10.json)
mantém os critérios ainda sem demonstração e não inventa um percentual de pesquisa.

Suíte local final: **406 testes e 295 subtestes aprovados**, sem falhas. Os cinco
testes do site e seu build também passaram. A reprodução de locale sem UTF-8
passou com a correção; os resultados nativos Windows são registrados separadamente.

O Python core passou nos seis jobs nativos Linux/Windows e o instalador Windows
foi construído e testado no commit de código `22bdf6c`; as evidências estão na
[auditoria](audits/SCIENTIFIC_ACCEPTANCE_2026_10.md#validação-nativa-observada-na-branch).
