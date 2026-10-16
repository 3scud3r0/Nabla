# Estabilidade do perfil local 1.0

O contrato normativo congelado está em `src/nablamath/public_api.json`, enviado
no wheel. `python tools/release_readiness.py` compara a implementação com esse
contrato e confere os schemas do protocolo. A comparação é uma barreira contra
mudanças acidentais; uma mudança intencional exige revisão do contrato e migração.

O perfil cobre os nomes de `nablamath.__all__`, as assinaturas e os domínios
publicados no catálogo de `CalculationSession`, `Notebook` e os comandos locais
listados no contrato. `nabla calc OP --arguments JSON` usa os campos obrigatórios
e opcionais do catálogo; argumentos desconhecidos e operações fora do perfil
são recusados. Integrações experimentais permanecem sujeitas a mudanças.

Os recibos de cálculo e notebooks usam schema inteiro 1. O SQLite aceita a base
vazia/alpha `user_version=0` e a tabela `results` do schema 1. Uma base marcada
com uma versão conhecida ainda precisa corresponder à estrutura real. O upgrade
é transacional; downgrade não existe. Backup copia sem alterar a origem; restore
confere recibo, bytes, integridade e estrutura, migra a cópia e publica sem
sobrescrever o destino. Escolha um nome novo para cada backup e seu manifesto.
Não remova o manifesto: um par incompleto é recusado.

Expressões racionais preservam as obrigações do domínio original, incluindo
polos removíveis. Resultados aproximados carregam suas limitações; nenhuma
igualdade de ponto flutuante é convertida em prova. Os dois tipos de intervalo
(`core.precision` e `math.analysis.intervals`) têm endpoints racionais exatos:
converta explicitamente por `lower` e `upper`; o segundo aplica limites adicionais
de grau e bits. Não há promessa de arredondamento binário nesses tipos.

CLI: status 0 indica sucesso; 1 indica falha da operação/ambiente; 2 indica erro
de sintaxe dos argumentos pelo argparse. O texto humano de diagnóstico pode ser
melhorado. Automação deve usar status e os dados JSON dos comandos documentados.
`doctor` distingue descoberta de teste: um executável encontrado fica
`unverified`; `doctor --probe` verifica a versão com timeout e retorna
`available`, `unavailable` ou `incompatible`. Isso não valida uma prova ou PDF.

Na linha estável 1.x, remover nomes/campos, mudar significado ou reduzir domínio
suportado exige nova major. Depreciações mantêm a alternativa por pelo menos uma
minor, emitem aviso e documentam a migração. A leitura de formatos antigos deve
migrar explicitamente ou recusar; hashes novos nunca autorizam reinterpretá-los.
A versão 1.0.0 de uso pessoal segue o aceite e as dispensas do proprietário em
[PERSONAL_USE_1_0.md](acceptance/PERSONAL_USE_1_0.md). A certificação do canal
público assinado continua condicionada aos gates próprios desse canal.

SDKs Python/TypeScript/Rust/C/C++, rede, GPU e pesquisa geral são experimentais.
A presença de módulos importáveis não amplia a superfície estável. Os recursos
CPU são admission control cooperativo, sem sandbox de código hostil nem garantia
de memória imposta pelo SO. Ferramentas opcionais precisam de seus testes reais.

## Ampliação experimental e aditiva de matemática exata

O perfil local registra nominalmente 29 operações novas no catálogo e no contrato do wheel, sem renomear comandos de CLI nem alterar formatos de recibo ou notebook. A implementação fica em `math/exact/`; a compatibilidade antiga foi preservada. A publicação de um novo contrato é mudança intencional, testada por igualdade com o catálogo em runtime. O aceite pessoal não constitui certificação independente da distribuição pública.

A operação CLI aditiva `nabla catalog` publica os metadados do mesmo catálogo utilizado por `nabla calc`, pelo desktop e pelos recibos de notebook. O comando é somente leitura e não altera o armazenamento do usuário.
