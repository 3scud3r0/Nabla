# Experimentos científicos com Nabla

Após instalar o pacote, execute a partir do checkout:

```sh
python examples/science/reproduce.py .nabla/meu-experimento
```

O destino deve ser novo. O programa não acessa serviços externos nem exige
bibliotecas opcionais. Usa o Nabla instalado, produz `REPORT.md`, `report.json`,
um notebook de 102 células, dois artefatos científicos com SVG/HTML, um banco
SQLite com backup e restore e os dados de uma hipótese sintética.

| Pergunta | Experimento e evidência |
|---|---|
| As 103 operações do catálogo são executáveis? | `catalog_cases.json` fixa os argumentos. Cada operação tem uma referência explícita em `reproduce.py`, comparada antes de salvar o recibo. O conjunto deve corresponder exatamente ao catálogo instalado. |
| É apenas um snapshot do próprio resultado? | Não. Referências são fórmulas e valores declarados no código: integração de x², determinante 2×2, PA=LU, ortogonalidade, distribuição binomial, limites racionais e solução analítica de decaimento. Não existe comando para regenerá-las a partir do Nabla. |
| As referências se sustentam em mais de um exemplo? | Campanha de 176 casos: primalidade por divisão tentativa para n=0…127, raízes modulares por enumeração em cinco corpos primos e nove leis binomiais por combinações. |
| Podemos formular e testar uma hipótese? | Lei conhecida y=1+2x: oito pontos de treino, ajuste exato e oito pontos reservados. Uma lei errada é rejeitada nos pontos reservados. Dados sintéticos não demonstram descoberta inédita. |
| Podemos construir problemas e verificar soluções? | As oito famílias Forge executam duas estratégias de solução e seu verificador. Duas famílias também produzem um artefato encadeado com dados, figura, documento e replay. |
| Há simulação física com referência analítica? | Dezesseis casos idealizados de elasticidade, RLC, cinética e hidrostática, com unidades SI e replay. Difusão em duas malhas é comparada à solução senoidal da equação do calor, exigindo convergência de segunda ordem. Não utiliza dados medidos. |
| O notebook preserva os cálculos? | As 102 células são persistidas e reexecutadas. Uma cópia com resultado adulterado deve ser rejeitada. |
| CLI e desktop usam a mesma matemática? | Todas as 103 operações retornam recibos idênticos pela CLI instalada e pelo servidor HTTP real, com referências matemáticas conferidas. O desktop salva e reexecuta um notebook e rejeita token inválido. |
| Dados sobrevivem ao backup? | Uma expressão é gravada em SQLite, copiada, restaurada e comparada byte a byte no payload. |
| O programa rejeita uso inválido? | Nove controles negativos: singularidade, divisão por zero, domínio de primalidade, polinômio redutível, massa incompleta, orçamento de atribuição, argumento desconhecido, unidades incompatíveis e notebook adulterado. |

Os resultados aproximados de EDO são comparados a exp(−1) com tolerâncias
explícitas. A certificação racional de exp(1) é comparada com outra soma de Taylor
e uma cota geométrica. Provas Lean e a auditoria de 30 mil instâncias são uma
etapa separada (`tools/rational_proof_corpus.py`); o relatório geral de testes e
benchmarks é gerado por `tools/vision_readiness.py`.

Estes experimentos verificam casos finitos e identidades nos domínios exibidos.
Não constituem uma prova de correção para todas as entradas, validação física com
dados reais, descoberta científica nova, certificação de GPU, federação pública
ou suporte Windows executado neste host. Os 213 requisitos da visão mantêm seus
critérios e suas lacunas. Os artefatos registram essas limitações.

Para exigir provas reais no mesmo experimento, prepare a toolchain fixada e execute:

```sh
bash scripts/setup_formal.sh
python examples/science/reproduce.py .nabla/experimento-com-provas --formal-project lean
```

Essa opção só passa se três proposições racionais forem verificadas pelo Lean, com auditoria dos axiomas, e uma proposição falsa for efetivamente rejeitada. Sem pré-requisitos, falha explicitamente. O relatório padrão informa `not_requested`, sem alegar prova formal. Para reproduzir a campanha ampliada de fases e benchmarks, execute também `python tools/vision_readiness.py`; para o corpus, `python tools/rational_proof_corpus.py --verify .nabla/corpus-novo --workers 4 --timeout 600`.
# Demonstrações adicionais de matemática e publicação

`layers_pipeline.py` gera GLB, Manim/MP4 e Living Paper assinado.
`editorial_showcase.py` produz PDFs Typst/LaTeX com tabelas multipágina.
O [inventário MSC](../../docs/MSC2020_COVERAGE.md) lista os 22 módulos adicionais.
