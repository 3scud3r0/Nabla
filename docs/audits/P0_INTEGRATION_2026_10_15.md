# Fundamentos P0 e integração — 15/10/2026

Escopo selecionado: fundamentos P0 e integração do roteiro recebido com 213
requisitos, sobre o baseline `494172023cb97ada45133a7a868344fc2215c53c`.
O roteiro completo é preservado em `docs/strategy/NABLA_2056_ROTEIRO_MESTRE.md`;
`tools/check_roadmap.py` verifica seu hash, os 213 IDs e referências locais.

## Alterações verificadas

- Contrato imutável `ScientificArtifact` com DAG por conteúdo, versão explícita,
  licença/origem declaradas, serialização canônica e limites de entrada.
- Perfil `exact-rational-cycle-v1`: Forge → solver → verificador separado →
  dataset/cena SVG → relatório HTML. CLI `artifact` e `check-artifact`.
- Replay rejeita adulteração em cada um dos sete nós, inclusive após reconstruir
  os hashes de todos os descendentes. Verificação independente de resíduos e
  coeficientes testa a matemática além dos hashes.
- Persistência de artefato em blob atômico, validado antes da escrita e na leitura.
- Cache publica índices completos sem sobrescrever o vencedor concorrente;
  teste com 12 escritores conflitantes e leitura de blob corrompido.
- Registro explícito de migração N→N+1; contratos para tipos de evidência e
  separação declarada de atores, sem afirmar autenticação ou revisão externa.
- CI instala `.[test]`, roda pytest além do unittest e verifica bundle/matriz.
  O workflow já continha testes/build do site, que foram preservados.

## Validação local

Ambiente: Linux x86_64, Python 3.12.14, Node 24.19.0, CPU.

| Verificação | Resultado |
|---|---|
| Baseline `pytest` | 465 passaram, 3 ignorados, 309 subtestes passaram |
| Suíte após alterações `pytest` | 515 passaram, 3 ignorados, 309 subtestes passaram |
| Novos testes de contratos, integração, cache e matriz | 50 passaram |
| Perfil mínimo de CI (wheel + pytest, sem extras científicos) | 496 passaram, 22 ignorados, 300 subtestes passaram |
| `unittest discover -s tests -v` | 340 executados, sucesso, 3 ignorados |
| Site `npm test` | 5 passaram |
| Site `npm run build` | passou |
| `pip check` | sem dependências quebradas |
| Reexecução do script de instalação salvo | passou, sem alterar dependências declaradas |
| Build do wheel sem dependências | passou |
| Instalação isolada do wheel e geração/replay pela CLI | passou, sem extras |
| `tools/build_math_bundle.py --check` | passou; bundle regenerado pelo gerador |
| `tools/check_roadmap.py` | 213 requisitos; 24 parciais, 189 planejados, 0 validados integralmente |

Os três testes ignorados exigem o build opcional fixado de Lean/Mathlib.
Não houve avaliação de GPU, validação empírica, revisão externa, rede entre
hosts ou execução da matriz de CI em outros sistemas. Esta é evidência local;
status remoto de Actions e release devem ser verificados no respectivo commit.

Os 24 requisitos parciais referenciam o perfil finito entregue. A contagem
não mede progresso científico e não significa que 24 requisitos amplos estejam
concluídos. F7–F13 e outras frentes do roteiro permanecem fora desta entrega.
