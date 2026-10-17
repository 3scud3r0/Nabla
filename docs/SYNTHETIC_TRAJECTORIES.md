# Gerador procedural de trajetórias matemáticas

O gerador produz exercícios resolvidos, candidatos deliberadamente incorretos,
diagnósticos e correções sem inferência neural. Usa o catálogo matemático do
Nabla e registra os cálculos em recibos reexecutáveis. Não requer Torch ou GPU.

São **100 famílias autoradas**, incluindo seis trajetórias especiais e 94 receitas
do catálogo. A cobertura inclui álgebra, análise, cálculo, geometria, topologia,
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
| `dataset.jsonl` | Registros completos, configuração, respostas, passos e recibos |
| `sft.jsonl` | Mensagens user/assistant com resultados aceitos; candidatos corrompidos ficam fora desse texto |
| `dpo.jsonl` | Pares locais prompt/chosen/rejected para cada mutação detectada |
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

`amostras_traduzidas.txt` usa modelos de frase e renderização de expressões
fechadas para explicar os registros em português natural. O tradutor não infere
intenções, não acrescenta justificativas ausentes e não representa pensamento
interno de uma rede neural.

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
