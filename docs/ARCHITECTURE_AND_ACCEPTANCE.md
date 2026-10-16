# Arquitetura-alvo, modelos matemáticos, qualidade e testes

## Contratos e arquitetura

- `nablamath.symbolic`: AST tipada, parser seguro sem `eval`, aritmética exata/racional quando possível, simplificador com domínio explícito, `to_latex`, derivação com regra e check de identidade. Erros com proveniência.
- `nablamath.numeric`: floats/complex/arrays, integração numérica, solvers de IVP, álgebra linear, tolerâncias relativas/absolutas e análise de erro.
- `nablamath.autodiff`: diferenciadores forward/reverse, jacobiano/hessiana, comparação contra diferenças finitas e simbólico, broadcasting e graph detach documentado.
- `nablamath.calculator`: `Calculation`, `Step`, `ProofObligation`, `Unit`, `Domain`, `Assumption`, JSON e Markdown/LaTeX renderizável; templates separados da lógica.
- `nablamath.physics.relativity`: SR e GR por escopo; evitar alegar GR genérica quando só há Schwarzschild e plots.
- `nablamath.physics.orbital`: estados com referências de coordenadas e SI, dinâmica por componentes, atmosfera e parâmetros com intervalos de validade, geofísica opcional, eventos e limites físicos.
- `nablamath.render`: scene graph neutro; nativo raster/pathtrace; web; Blender export opcional; mapas térmicos/IR/Xray rotulados como proxy quando apropriado.
- `nablamath.reports`: documentos LaTeX por capítulos únicos, fórmulas numeradas, derivação por inferência, glossário, tabelas de unidades, figuras com legenda e referências; `.tex`+`.pdf`+manifesto.
- `nablamath.singlefile`: empacotador com teste de equivalência, não fonte de verdade independente.

## Requisitos para relatórios de derivação

Cada seção técnica deve apresentar objetivo, hipóteses, definições/unidades, equação inicial, transformação algébrica justificada por passo, substituição numérica com precisão, resultado e sanity checks/limites. Cada figura precisa declarar **de onde vem o dado**, banda física versus surrogate e qual equação reproduz. Seções novas exigem entradas e raciocínio novos; nunca acrescentar `\newpage` até bater contador arbitrário. Registro de passos deve ter IDs e deduplicação por hash de conteúdo.

Compilação: tentar `pdflatex`/`lualatex` com timeout; detectar `returncode != 0`, ausência de PDF, `undefined references`, overfull boxes significativos e falha da segunda passagem. Inspecionar pages via PyMuPDF/pdfinfo, extrair texto para checar equações numeradas e renderizar amostras de todas as seções. Declinar PDF quando não houver compilador, mas sempre salvar `.tex` e log.

## Relatividade — suíte mínima

Testar invariância do intervalo Minkowski para boosts; limite `v << c`; γ monotônico para 0≤|v|<c; composição velocidade <c; `E²−(pc)²=(mc²)²`; simetria da métrica; geodésica livre plana; símbolos de Christoffel nulos em Minkowski cartesiana; tensor Riemann com simetrias; limite newtoniano e periélio Schwarzschild nas hipóteses. Derivações GR válidas somente se passos algébricos e dependências estiverem explicitados.

## Orbital — suíte mínima

Circular: `v_c=√(μ/r)` e `T=2π√(r³/μ)`. Elíptica: `v²=μ(2/r−1/a)`; energia e momento angular conservados no problema 2 corpos. Deorbit: verificar perigeu/apogeu e Δv por vis-viva, sinal e altitude de interface. Reentrada: ODEs e integração com unidades, transição de atmosfera, Mach vs modelo de som, força/carga; volatilidade de Cd/Cl. Aquecimento Sutton–Graves deve ter **coeficiente SI verificado e explicitamente dimensional**, sem fator arbitrário ×10⁴; comparar ordens de grandeza e faixas de validade. Parede térmica exige balanço transiente ou declarar equilíbrio radiativo simplificado; não `clip` escondido. Pressão de estagnação exige condições de choque para hipersônico, não aplicar expressão isentrópica como resultado final. Ionização, frequência plasma/blackout e X-ray devem declarar proxy, composição química e banda/sensor; sem MHD/CFD não rotular como solução. Captura exige dinâmica lateral, geometria de torre, massa/propelente e limites de empuxo, não apenas aproximação de frenagem vertical.

## Renderer — critério de verdade

Rasterizador: clipping homogêneo, z-buffer, interpolação perspectiva-correta, normais com inversa transposta, sombras e teste de triângulos cruzados. BVH: interseção AABB e triângulo validada contra força bruta, casos tangentes e rays paralelos. Path tracer: contagem SPP e bounces realmente executada, sampling cosine/BRDF + PDF, direct light, shadow rays, roulette e convergência Monte Carlo; se só reflexo screen-space chamar de reflection pass. LOD meshlets deve evitar duplicação de faces e lacunas; Nanite é marca/implementação da Unreal, não equivalência. Performance medida no Windows RTX 4060/16GB, com fallback CPU. Blender exportado só é visualmente verificado após rodar Blender/Cycles.

## Estado dos artefatos legados

Os PDFs existentes são **referências visuais/históricas**, não provas independentes de correção física. O executável single-file atual é amostra funcional por partes, não implementação exaustiva de todos os objetivos. Não declarar v0.7 como engine completo. Preserve notas de limitação em cada saída e assegure assertivas testáveis.

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
