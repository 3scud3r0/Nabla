# Mapa dos módulos canônicos

| Camada | Implementação e ligação |
|---|---|
| Expressões | `expression.py`: AST racional, parser restrito e avaliação exata |
| Cálculo simbólico | `symbolic/`: derivação, primitivas polinomiais, séries, e-graph e certificados |
| Matemática | `math/`: álgebra, matrizes, grafos, probabilidade, lógica e integradores |
| Matemática exata avançada | `math/exact/`: laboratório original mais cinco módulos de teoria dos números, corpos finitos, análise rigorosa, grafos/otimização e probabilidade com 29 operações no catálogo; [referência detalhada](../math/ADVANCED_EXACT_EXPANSION.md) |
| Contratos | `core/semantic_ir.py`: problemas racionais versionados e identidade semântica |
| Construção inversa | `forge/reverse_builder.py`: primitivas/soluções escolhidas antes do problema |
| Solução/verificação | `verify/certificate.py`: solver sem testemunho; derivação independente e resíduos/determinante |
| Ciclo completo | `forge/pipeline.py`: geração, verificação, partições, figuras, relatório e manifesto |
| Dados | `dataset/`: contratos existentes; `scientific.py` e `alignments.py` revalidam matemática, família e modalidades |
| Apresentação | `graphics/`: cena com coordenadas exatas, SVG/PNG; `documents/`: texto/equações/figuras em HTML, LaTeX e Typst |
| Simulação | `worlds/validation.py`: usa `math/equations/ode.py`, compara com referências analíticas |
| Refutação | `falsifier/search.py`: grade inteira limitada, testemunho mínimo em norma L1 nesse domínio |
| Evolução | `evolution/evaluator.py`: escolha fixa de políticas, comparação pareada e orçamento explícito |
| Engenharia | `domains/circuits/`: análise nodal CC, leis de Kirchhoff e balanço de potência |
| Conhecimento | `knowledge/graph.py` existente; `versioned_claims.py` adiciona revisões imutáveis e impacto de dependências |
| Persistência e UI | `storage.py`, `store/`, `desktop/`: SQLite, backup, painel HTTP local |
| Integrações | `formal/`, `gpu/`, `publisher/`, `network/`: capacidades existentes e dependências opcionais |

Exemplos executáveis e limites: [Ciclo científico](../SCIENTIFIC_CYCLE.md).
A preservação da API pública é exercitada em `tests/regression/test_public_api.py`.
