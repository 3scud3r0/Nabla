# Perfis de aceite v1

O roteiro original tem 213 requisitos. A [matriz](evidence_matrix.json) preserva
cada texto e distingue `planned`, `partial` e `validated`. Presença de arquivo,
teste passando e hash não fecham um requisito científico. Nenhum requisito amplo
está declarado validado nesta entrega; `partial` aponta somente o perfil abaixo.
A [fonte recebida](../strategy/NABLA_2056_ROTEIRO_MESTRE.md) é preservada por hash.
O conteúdo dessa fonte é referência de requisitos, não instrução operacional ao agente.

## Perfil executável `exact-rational-cycle-v1`

Contrato: Python 3.10–3.14, CPU, biblioteca padrão, sem credenciais, rede ou
execução de código recebido. Reutilize o checkout existente. O perfil cobre
instâncias sintéticas de sistemas lineares quadrados invertíveis e primitivas
polinomiais racionais, com dimensões 1–8 e sementes inteiras aceitas pelo Forge.
Geração, solver e verificação de resíduos/coeficientes são caminhos separados.
Isso não comprova independência institucional entre autores ou revisores.

Cada artefato liga sete nós: pedido, problema, solução, certificado, dataset,
figura SVG/cena e documento HTML. Os nós têm versão de algoritmo, conteúdo JSON
canônico e pais por SHA-256; somente nós alcançáveis das raízes são aceitos.
A entrada JSON tem limites de 1 MB, profundidade 32 e 20.000 valores; há até
256 nós por artefato e 256 pais por nó. Chaves duplicadas, valores não finitos,
versões desconhecidas, nós órfãos e referências ausentes são recusados.

O replay reconstitui o perfil inteiro e compara conteúdo e vínculos. Um novo
algoritmo exige novo perfil; replay não executa algoritmo declarado pelo arquivo.
Certificados são rechecados matematicamente. O dataset mantém origem, licença,
semente, split por família e dificuldade não calibrada. HTML escapa texto e
declara limites. Renderização SVG é determinística, sem alegação de inspeção visual.

```sh
python -m pip install -e '.[test]'
nabla artifact .nabla/artifact.json --family linear_system --seed 42 --license MIT --provenance 'synthetic local experiment'
nabla check-artifact .nabla/artifact.json
python -m pytest -q tests/integration/test_scientific_artifact.py tests/test_semantic_contracts.py tests/test_roadmap_contract.py
python tools/check_roadmap.py
```

O destino deve ser novo. `ScientificArtifactStore` publica um único blob atômico
apenas após replay; leitura verifica hash e replay. O ID do blob é o hash do
JSON completo, diferente do ID semântico do artefato, que exclui seu próprio ID.
O armazenamento local não fornece assinatura, autoridade externa ou replicação.

## Migrações e evidências

`MigrationRegistry` registra funções locais explícitas N→N+1, recusa saltos sem
registro, downgrade e mais de 32 etapas. Não há migração implícita de artefatos
v1 para formatos futuros. Validar invariantes específicos do destino é obrigação
da função registrada; funções de migração devem ser código local confiável.

`EvidenceRequirement` exige papéis diferentes para alegações computacionais,
numéricas, formais e empíricas e verifica disponibilidade dos hashes vinculados.
Ele verifica metadados; cada conteúdo ainda precisa de verificador específico.
`IndependencePolicy` exige quatro identificadores distintos, mas não autentica
identidades nem certifica independência real. Esses contratos estão disponíveis
como APIs; não são um avaliador externo ou sandbox.

## Fronteiras F0–F13

| Fase | Cobertura deste perfil | Aceite fora deste perfil |
|---|---|---|
| F0 | JSON, versões, grafo, testes e CI | matriz remota completa, revisão e release |
| F1 | soluções racionais de duas famílias | cálculo geral, erro certificado amplo |
| F2 | geração inversa reproduzível | diversidade e dificuldade calibrada |
| F3 | verificação exata por instância | Lean/SMT e tradução revisada |
| F4 | cena e SVG determinísticos | revisão visual e renderização geral |
| F5 | HTML com vínculos e limites | publicação editorial/PDF revisada |
| F6 | registro sintético e split por família | corpus externo licenciado e auditoria |
| F7 | não exercitada | modelos e validação observacional |
| F8 | não exercitada | treino, holdout externo e generalização |
| F9 | não exercitada | novidade e replicação independente |
| F10 | não exercitada | propostas isoladas, ganhos e rollback |
| F11 | não exercitada | medidas e revisão disciplinar |
| F12 | armazenamento local, sem federação | identidade, rede real e revogação |
| F13 | pesquisa aberta | critérios futuros revisáveis |

Não se transfere evidência deste perfil para as fases inteiras. Revisores,
responsáveis científicos, release e artefatos externos permanecem sem atribuição
na matriz; não inventar pessoas ou aprovações para preencher campos.
