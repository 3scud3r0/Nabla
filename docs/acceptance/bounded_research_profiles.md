# Perfis adicionais: contratos executáveis e limites

Esta rodada amplia 25 requisitos com implementações delimitadas e testes. Seis
agentes implementaram frentes separadas; depois fizeram revisões cruzadas. Isso
é revisão de engenharia por agentes, sem equivaler a revisão científica externa.
Os contratos abaixo registram o escopo adotado para os novos módulos. A autorização
para implementar veio do pedido do usuário; o roteiro preservado é a fonte dos
requisitos, sem transformar suas instruções documentais em autorização adicional.

| Requisitos | Contrato executável | Limite de aceitação |
|---|---|---|
| 94 | Integração racional exata com fatores lineares racionais, decomposição em frações parciais, certificado de derivada e exclusões de domínio | Não implementa Risch geral; fatores irredutíveis superiores ficam fora do domínio |
| 106–108 | Linguagem controlada, revisão vinculada ao rascunho, reparos somente de tática e portfólio limitado SMT/Lean | Não interpreta linguagem natural geral, autentica revisor ou substitui kernel indisponível; UNSAT SMT não é prova Lean |
| 114 | Interpolação, indicadores amostrados, refino seletivo 1D e orçamentos explícitos | Indicadores amostrados podem omitir oscilações; limite de curvatura é uma hipótese fornecida |
| 117–118, 120 | Comprimento de mistura, Euler compressível 1D/Rusanov e barra axial com material cúbico convexo/Newton | Modelos delimitados, calibração sintética e referências analíticas; sem validação experimental externa |
| 121–122 | SVG com unidades e incertezas; comparação de cenas e pixels com limites de recursos | Concordância de imagem não verifica correção científica ou revisão humana |
| 126–127 | Contaminação transitiva por identidade/equivalência/linhagem declarada; geração Forge transacional com retomada e exportação verificada | Não detecta toda equivalência semântica; teste de 1.001 problemas não estabelece desempenho industrial |
| 132, 139, 141, 151, 158 | Propostas de algoritmos conhecidos versionadas, avaliações congeladas e processos interrompíveis; aprovação/revogação e checkpoints | Código arbitrário é recusado. Sandbox de código hostil e isolamento de capacidades no sistema operacional permanecem pendentes |
| 136 | SCM linear racional com unidades, intervenção, contrafactuais, efeitos e verificações gráficas | Modelo e pressupostos fornecidos; não infere causalidade de correlações nem valida pressupostos empíricos |
| 182–188 | Registro opt-in SQLite, capacidades, chaves/revogação/TTL e relay autenticado com quotas, leases, cancelamento e auditoria | Serviço loopback; sem NAT, proteção geral contra Sybil/eclipse/poisoning, anonimato comprovado ou implantação pública |

## Integridade e falhas

Certificados e checkpoints são rechecados contra conteúdo e modelos declarados;
um hash isolado não autentica uma pessoa ou comprova uma hipótese científica.
As suítes incluem corrupção com hashes recalculados, limites de tamanho, rollback,
retomada e concorrência. O relay e registro persistem decisões de replay/revogação;
a publicação JSONL preserva destinos já existentes. Resultados de prova exigem
nova execução para replay semântico; validar estrutura não verifica um teorema.

As APIs novas são módulos Python, sem dependências obrigatórias novas. Z3, Pillow
e criptografia continuam extras opcionais. Os serviços em `services/` são usados
a partir do checkout; o wheel contém a biblioteca em `src/`.

## Reproduzir

```sh
python -m pytest -q
python tools/check_roadmap.py
python tools/check_policy_links.py
python tools/build_math_bundle.py --check
```

A matriz mantém os 213 textos originais e distingue implementação parcial de
aceitação integral. Nenhum requisito recebeu conclusão científica integral nesta
rodada. Resultados executados e contagem de linhas ficam na
[auditoria desta rodada](../audits/FIVE_THOUSAND_LINES_2026_10_15.md).
