# Gerador procedural de trajetórias matemáticas

O gerador produz exercícios resolvidos, candidatos deliberadamente incorretos,
diagnósticos e correções sem inferência neural. Usa o catálogo matemático do
Nabla e registra os cálculos em recibos reexecutáveis. Não requer Torch ou GPU.

São **120 famílias autoradas**, incluindo seis trajetórias especiais, 94 receitas
do catálogo e 20 desafios compostos. A cobertura inclui álgebra, análise, cálculo, geometria, topologia,
teoria dos números, probabilidade, estatística, otimização, grafos, lógica,
transformadas e mecânica estatística. Uma receita é um perfil limitado de uma
área; não significa cobertura integral dessa área ou de todas as funções Python.

## Gerar e verificar

Na raiz do checkout, usando o Python do projeto:

```sh
python -m pip install -e '.[advanced]'
python gerar_raciocinio_longo.py --count 100 --difficulty 6 --depth 32 --error-rate 0.65 --output .nabla/synthetic_100
python gerar_raciocinio_longo.py --verify .nabla/synthetic_100
python gerar_raciocinio_longo.py --list-families
```

Depois de instalar o pacote, `nabla-synthetic` oferece os mesmos argumentos.
Também é possível executar
`python -m nablamath.superintelligence.synthetic_cot_unroller`.
O extra `advanced` instala bibliotecas matemáticas convencionais. Não instala
redes neurais. Receitas do núcleo, como `lyapunov`, `matrix_inverse` e
`matrix_noncommutativity`, funcionam sem esses extras:

```sh
python gerar_raciocinio_longo.py --count 10 --families lyapunov matrix_inverse matrix_noncommutativity --depth 16 --output dados_cpu
```

O destino deve ser novo. A geração usa staging e publica o diretório somente ao
terminar; uma falha remove a saída parcial. JSONL é escrito progressivamente e a
deduplicação exata usa SQLite, mantendo o conjunto de identificadores em disco.
Até 100 milhões de registros podem ser solicitados, sujeito ao espaço real de
problemas das receitas, tempo e armazenamento; não é promessa de throughput ou
de petabytes viáveis. Nenhum benchmark de milhões de tokens/minuto foi realizado.

`--seed` fixa a geração. `--start-index` seleciona o ponto da sequência e o
`next_index` no cartão permite iniciar outro lote. Lotes separados precisam de
deduplicação conjunta se forem mesclados. O máximo de `--depth` é 256.

## O significado de comprimento

`chain_rule` diferencia sucessivamente uma composição polinomial e compara cada
resultado com uma expansão binomial calculada separadamente. A ordem termina
no grau do polinômio. `lyapunov` vetoriza uma equação matricial, resolve o sistema,
calcula cada entrada do resíduo e verifica menores principais de Sylvester.
`ito_stratonovich` verifica o sinal da conversão e calcula o gerador de Itô em
observáveis distintos. As outras trajetórias especiais tratam assinatura
lorentziana, comutadores e domínios parciais.

Nas receitas gerais, `depth` é o número desejado de **subproblemas distintos**
de uma suíte, não o número de passos de uma única prova. Instâncias repetidas
são removidas; construtores com poucas instâncias podem terminar antes. O texto
explica essa diferença. Aumentar o parâmetro não transforma exercícios finitos
em descobertas científicas nem em pensamento neural mais fiel.

## Arquivos

| Arquivo | Conteúdo |
| --- | --- |
| `amostras.txt`, `amostras.md` | Todas as amostras, cálculos, erros rotulados, diagnósticos e correções |
| `amostras_traduzidas.txt` | Tradução determinística em português, sem JSON bruto e com mutações, diagnóstico e correção explicados |
| `narration.jsonl` | Eventos da máquina de estados, regras escolhidas pela gramática e recibos que sustentam cada etapa |
| `dataset.jsonl` | Registros completos, configuração, respostas, passos e recibos |
| `sft.jsonl` | Mensagens user/assistant com resultados aceitos; candidatos corrompidos ficam fora desse texto |
| `dpo.jsonl` | Pares locais prompt/chosen/rejected para cada mutação detectada |
| `sft_natural.jsonl` | Mensagens em português com tentativas sintéticas explicitamente rotuladas e correções |
| `dpo_natural.jsonl` | Preferências locais em português entre os campos divergentes, sem apagar a diferença na tradução |
| `train.jsonl`, `validation.jsonl`, `test.jsonl` | Partições determinísticas agrupadas pela família construtora |
| `coverage.json` | Todas as operações e ações avançadas registradas, com receitas disponíveis e lacunas |
| `card.json` | Configuração, contagens, versões, hashes das fontes do gerador e limitações |
| `manifest.json` | SHA-256 dos arquivos; integridade de bytes, não assinatura nem prova |

As partições impedem que a mesma família construtora apareça em treino e teste.
Não garantem novidade semântica entre famílias matematicamente relacionadas.
Lotes pequenos podem ter partições vazias. O tamanho é deduplicado por tarefa,
sem alegar um problema matemático novo para cada registro.

## Verificação e mutações

O detector reexecuta a requisição fechada do catálogo e compara resultados.
Registra o campo divergente e, quando aplicável, a diferença racional. Uma
mutação genérica corrompe numerador, inteiro, booleano ou resultado numérico; não
é apresentada como um erro conceitual humano descoberto espontaneamente.
As trajetórias especiais contêm testes conceituais explícitos: fator da cadeia,
sinal da correção estocástica, assinatura, ordem matricial e domínio.

Para uma parte das operações há verificadores adicionais com `int`/`Fraction`,
independentes do algoritmo produtor: substituição em sistemas, produtos com
inversas, determinante por Leibniz, equações normais, enumeração de permutações e
cortes, matching/cobertura, normalizações e resíduos de Markov. Cada certificado
declara exatamente o que foi checado. Isso não valida toda a prosa nem substitui
revisão independente. Nas demais receitas há reexecução do mesmo motor; a
ausência de referência independente fica explícita.

O verificador do diretório regenera os registros, as mutações, as respostas e
todas as projeções, além de conferir hashes. Recalcular apenas um hash após
adulterar um resultado não basta para passar. A reprodução estrita requer as
mesmas fontes e versões; resultados numéricos podem diferir entre plataformas.
Registros numéricos são marcados `numerical_not_enclosed`; dígitos exibidos ou
resíduos pequenos não são inclusões rigorosas do erro.

Os rótulos positivos/negativos são supervisão procedural local. Não são
preferências humanas nem métricas empíricas de qualidade ou utilidade de treino.
Os dados precisam de avaliação externa antes de sustentar alegações de ganho de
capacidade em modelos.

`amostras_traduzidas.txt` usa uma voz conversacional em primeira pessoa para
explicar os registros: apresenta um palpite, descreve a checagem, localiza a
diferença observada e indica o ajuste. O fluxo evita rótulos de relatório como
“Tentativa sintética” e “Diagnóstico do verificador”; esses estados continuam
disponíveis nos metadados. Cada fala é gerada a partir dos valores, recibos e
certificados registrados. O cabeçalho identifica o texto como simulação
narrativa procedural, não como pensamento espontâneo ou privado de uma rede
neural. A gramática não inventa surpresa, causa ou justificativa que os dados
não sustentem.

A versão atual evita duplicar os objetos completos de resultado na fala: a
correção aponta os campos alterados, enquanto a resposta integral permanece na
projeção matemática e nos recibos. A checagem é descrita como comparação com o
cálculo registrado; ela só é chamada de independente quando há certificado de
referência adicional.

## Gramática procedural com proveniência

A versão 2 substitui a tradução plana por uma gramática ponderada de
não terminais e slots fechados, combinada com uma máquina de estados finita.
Cada etapa com candidato rejeitado segue `plan → attempt → check → diagnose →
correct → confirm`. Sem erro registrado, segue `plan → execute → confirm`.
Não são inventadas falhas para preencher a narrativa. Os estados organizam uma
demonstração algorítmica; a apresentação em primeira pessoa melhora a leitura,
sem transformar a demonstração em deliberação neural.

As palavras variam com `--wording-seed`, separadamente da semente matemática
`--seed`. Cada escolha é derivada da versão da gramática, identificador do
registro, índice da etapa e estado. Alterar a semente de redação não altera o
problema, as respostas ou as mutações. As escolhas de produção ficam em
`narration.jsonl`, com referência ao recibo e às dependências reais da etapa.

Os perfis semânticos vinculam o plano à operação executada: BBᵀ e a Hessiana
em Itô, fatores invariantes em Smith, sinais orientados em formas, domínio
em funções racionais, dualidade em otimização e assim por diante. Precauções
conceituais são apresentadas como precauções, não como causas supostamente
descobertas de uma alteração numérica. Um inteiro modificado não é chamado de
erro de dimensão sem evidência sobre esse papel.

O narrador recusa diagnósticos que não correspondam aos valores efetivamente
diferentes entre candidato e recibo, bem como correções sem rejeição ou
dependências futuras. Slots não aceitam acesso a atributos; a expansão tem
orçamento de profundidade e número de produções. Fórmulas são inseridas como
dados depois da expansão, sem execução de código ou expansão recursiva do texto
matemático.

A detecção distingue reexecução, referência adicional que rejeita o candidato,
referência que continua válida apenas em suas afirmações limitadas e ausência
de referência. Assim, um teste do determinante não é apresentado como validação
do posto. A narração é reconstituída durante `--verify`; recalcular o hash de
uma história adulterada não basta para aprová-la.

`dpo_natural.jsonl` compara propostas nos mesmos campos do mesmo passo. Pares
que perdessem sua distinção ao renderizar não são publicados. São preferências
locais computacionais, sem ranking de soluções completas. O SFT natural contém
erros rotulados como sintéticos e sua correção; o SFT técnico original mantém a
projeção só com resultados aceitos. Nenhum formato tem utilidade de treino
demonstrada por esses testes.

## Lote de vinte desafios compostos

```sh
python gerar_raciocinio_longo.py --suite advanced20 --difficulty 8 --error-rate 1 --wording-seed 42 --output .nabla/advanced20
python gerar_raciocinio_longo.py --verify .nabla/advanced20
```

Esse comando seleciona uma instância de cada um dos vinte perfis a seguir.
O TXT para leitura é `amostras_traduzidas.txt`. Os perfis têm cargas estruturais
autoradas e limitadas; `depth` não os transforma em provas maiores. Há
subáreas diferentes, incluindo especializações relacionadas entre si.
"Avançado" descreve o conteúdo; não existe classificação empírica de dificuldade
contra o1/o3, Opus ou matemáticos humanos. O catálogo não resolve problemas
abertos por aumentar números ou acrescentar frases.

| Subárea | Desafio e carga matemática |
| --- | --- |
| Controle e equações matriciais | Lyapunov 7×7 denso, 28 incógnitas simétricas, 49 resíduos e 7 menores |
| Teoria dos números diofantina | Pell para 61,109,181,661, com identidades inteiras de grandes soluções |
| Álgebra comutativa e módulos | Apresentação inteira densa 8×8, oito fatores invariantes e torção |
| Álgebra homológica | Complexo 6←12←6, bases densas e homotopia contrátil verificada por produtos racionais |
| Representações | Regular de S3, multiplicidades 1,1,2 e comutante com 36 incógnitas |
| Álgebras de Lie | Takiff sl2[ε]/ε², Killing degenerada, radical e redução PBW de comprimento dez |
| Geometria algébrica | Cúbica torcida por eliminação em seis variáveis, saturação e dimensão do cone |
| Topologia algébrica | Homologia e cohomologia de T²∨RP²∨S², incluindo a torção e sua mudança de grau |
| Geometria diferencial | Métrica densa em carta polinomial não ortogonal e derivada covariante |
| Cálculo exterior | Pullback de 2-forma em dimensão quatro, naturalidade de d e integral orientada |
| Cálculo estocástico | Itô tridimensional de polinômio de grau seis, ruído multiplicativo e jet de ordem quatro |
| Cálculo das variações | Dois campos, três coordenadas, cinética não linear, potencial sêxtico e Hessiana 6×6 |
| Análise complexa | Quatro polos de multiplicidades 4,3,2,2, Laurent e soma global de resíduos |
| Análise funcional | Projeção ponderada de dimensão cinco em Q^10, pertinência e ortogonalidade exatas |
| Distribuições | Doze derivadas de Dirac, dualidade de D³ e Fourier de função-teste de grau vinte |
| Processos de Markov | Oito estados, duas absorções, momentos condicionais e Bellman descontado |
| Grafos | Fluxo racional em doze vértices comparado a todos os 1.024 cortes possíveis |
| Otimização convexa | Dez variáveis, dezoito restrições, complementaridade e certificado primal-dual |
| Aproximação | Padé [10/10] de exp e 21 coeficientes de convolução racional verificados |
| Equações integrais | Fredholm com núcleo 8×8, solução de grau onze e cota de contração em C[0,1] |

Certificados informam se usam `int/Fraction` separadamente do algoritmo produtor
ou se compartilham o CAS. Por exemplo, a comparação simbólica da fórmula de Itô
usa o mesmo CAS e não é anunciada como referência independente. Em Pell, a
substituição verifica x²−Dy²=1, sem provar a minimalidade. Em Fredholm, a cota
racional menor que um justifica a unicidade em C[0,1] pela série de Neumann.

Os manifestos e cartões de exportação são versão 2. A reprodução estrita dos
artefatos antigos exige as fontes antigas; não há migração silenciosa para a
gramática nova. Milhares de linhas de software, fluência, comprimento e
checagens locais não estabelecem equivalência a um modelo de fronteira.

## API Python e integração

```python
from nablamath.superintelligence.synthetic_cot_unroller import (
    GenerationConfig, SimulatedReasoningTrace, export_dataset, verify_dataset,
)

config = GenerationConfig(seed=42, difficulty=5, depth=32, error_rate=0.5)
problem = SimulatedReasoningTrace(config).generate('lyapunov', index=0)
card = export_dataset('novo_dataset', count=100, config=config)
assert verify_dataset('novo_dataset')
```

O `SyntheticForgeModule` existente também oferece `procedural_stream()` e
`export_procedural()`. Esse caminho importa o `omni_engine`, que consulta backends
opcionais. Para não carregar Torch sequer quando instalado, use a API acima ou
`from nablamath.superintelligence import SimulatedReasoningTrace`: os exports do
pacote agora são lazy. O contrato congelado do catálogo da versão 1 é preservado.

## Limites da análise que motivou o recurso

Trajetórias procedurais podem servir como dados sintéticos verificáveis. Não há
evidência de que reproduzam com extrema fidelidade o pensamento privado de o1/o3
ou permitam cloná-los. Comprimento, erros roteirizados, hashes e pytest verde não
demonstram esse resultado. O gerador não atribui estados mentais a redes nem
fabrica monólogos introspectivos. A dificuldade é declarada não calibrada, a
utilidade de treino não foi avaliada e a cobertura matemática total não é alegada.
