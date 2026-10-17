# Camadas de execução, verificação e publicação

Esta entrega implementa as duas especificações sobre recibos em background,
PyTorch/CUDA, MCP/SMT, matemática adicional, GLTF/Manim e Typst. Os módulos do
[ecossistema anterior](SCIENTIFIC_ECOSYSTEM.md), incluindo Pandas, XLA, MPI,
Jupyter, VS Code e federação, continuam disponíveis. O catálogo compartilhado
tem **102 operações**. Os novos nomes são `spectral`, `complex_analysis`,
`differential_geometry` e `abstract_algebra`, cada um com suboperações explícitas.
Os 22 perfis adicionais estão no [inventário MSC 2020](MSC2020_COVERAGE.md).

Implementação e aceitação científica são contratos distintos. Não existe
completude matemática universal, garantia de ausência de alucinações ou
certificação de produção por quantidade de arquivos. A matriz dos 213 critérios
continua sendo a referência de aceitação; este trabalho não promove seus estados.

## Instalação e demonstração completa

```bash
python -m pip install -e '.[test,research,torch,mcp,formal,federation,publishing,animation]'
python examples/science/layers_pipeline.py .nabla/meu-fluxo
```

Manim requer Cairo/Pango, fontes e FFmpeg; em Debian/Ubuntu, instale
`libcairo2-dev libpango1.0-dev pkg-config ffmpeg fonts-dejavu-core` antes do pip.
O diretório de saída precisa ser novo. `--cuda` exige uma GPU real;
`--skip-video` exporta o script sem produzir MP4. O padrão usa CPU explicitamente.
A demonstração cria recibos, bundle, GLB, script Manim, MP4, SVG, assinatura
ECDSA, PDF e manifesto verificável. A chave privada é efêmera, permanece em
memória e não serve como identidade institucional confiável fora da demonstração.

## Camada 0: resultados e recibos

O modo síncrono de `CalculationSession` preserva os recibos e o replay anteriores.
O hash e a serialização final ficam em cache imutável, com cópias independentes
em `to_data()`. Argumentos mutáveis são congelados antes do cálculo.

```python
from nablamath.calc import CalculationSession

records = []  # Em execuções longas, prefira um sink em arquivo/banco.
with CalculationSession(background_receipts=True, receipt_sink=records.append) as session:
    pending = session.execute('binomial', n=20, k=4)
    result = pending.result  # Matemática já concluída; resultado independente.
    audited = pending.to_data()  # Aguarda o recibo quando necessário.
```

Um único worker empacota os recibos; a fila é limitada por `max_pending` (128 por
padrão). Fila cheia causa `BufferError`, sem descartar silenciosamente registros.
`flush()` aguarda o trabalho aceito e propaga erros do sink; `close()`/`with`
também encerram o worker. O conjunto interno guarda apenas futuros pendentes,
sem acumular um histórico infinito. Um sink que guarda todos os recibos, como
`list.append`, naturalmente continua consumindo memória. Não bloqueie o sink
aguardando o mesmo worker. A sessão não garante transações de armazenamento ou
uso concorrente de seus bindings mutáveis.

Capturar argumentos, criar metadados e proteger snapshots tem custo. Threads
Python não eliminam o GIL; background e buffer retiram o empacotamento do caminho
imediato, sem prometer velocidade máxima, ganho em qualquer carga ou custo zero.
Uma campanha local de 4.000 chamadas escalares (`tools/benchmark_receipts.py`)
mediu 0,213 s no modo síncrono e 0,566 s no modo background incluindo `flush`.
É um resultado negativo para essa carga pequena, preservado em
`.nabla/receipt-benchmark.json`; não foi selecionado por repetição de benchmarks.

## Camada 1: tensores nativos e aceleração

```python
import torch
from nablamath.compat.pytorch_bridge import TorchTrace

x = torch.ones((2, 2), requires_grad=True)
with TorchTrace(sink=print, batch_size=128) as trace:
    y = x @ x.T
    y.sum().backward()
```

`TorchDispatchMode` intercepta os operadores ATen dinâmicos. A ponte devolve os
tensores originais e preserva views, aliasing e autograd. Registra nome, shapes,
dtypes, strides e dispositivos em lotes; usa referências fracas e não chama
`cpu`, `numpy`, `tolist` ou `item`. `from_dlpack`/`to_dlpack` compartilham storage
quando o produtor e consumidor cumprem o protocolo DLPack. O decorator anterior
`trace_execution` mantém seu contrato de captura de valores com leitura para CPU;
use `TorchTrace` para a captura sem leitura dos conteúdos.

Por padrão, os lotes são enviados ao sink e não retidos. `collect=True` habilita
histórico em memória para experimentos pequenos. Capturar shapes não autentica
conteúdos, resultados ou conclusão assíncrona dos kernels: o recibo declara
`metadata_only`, `tensor_contents_hashed=False`, `formal_proof=False`.

```python
from nablamath.backends.cuda_dispatcher import CudaDispatcher
from nablamath.calc import CalculationSession

dispatcher = CudaDispatcher(backend='torch', require_cuda=False)  # CPU explícita
with CalculationSession(background_receipts=True) as session:
    device_result = session.execute_accelerated(
        'least_squares', dispatcher=dispatcher,
        predictors=[[0], [1], [2]], response=[1, 3, 5], capture_values=True)
    audited = device_result.to_data()
```

O despachante detecta CuPy/PyTorch e GPU NVIDIA acessível. Suporta multiplicação
matricial, mínimos quadrados de posto completo (intercepto/pesos positivos), RK4
vetorizado para decaimento/oscilador e difusão FTCS 1D com fronteiras zero e razão
estável. O padrão exige CUDA; `require_cuda=False` permite CPU. Tensores PyTorch
nativos mantêm autograd. Somente falta de memória CUDA dispara recuperação para
CPU, quando autorizada por `allow_cpu_fallback`; erros matemáticos são propagados.
O recibo informa o backend efetivamente usado e o motivo da recuperação.

O resultado permanece nativo. `capture_values=True` faz leitura explícita para
auditar valores. A execução acelerada é uma observação numérica aproximada e tem
API própria: não substitui silenciosamente os mínimos quadrados racionais exatos
do catálogo. CUDA pode diferir da CPU em arredondamento e reprodutibilidade.

## Camada 2: MCP e juiz algorítmico

```bash
nabla-mcp                 # 102 ferramentas do catálogo
nabla-mcp --verify-claims # Acrescenta verify_conjecture
```

O servidor usa o SDK oficial MCP e transporte stdio. Os esquemas Draft 2020-12
validam também os conteúdos de matrizes, grafos, circuitos, tensores e
certificados, recusando campos desconhecidos. O servidor retorna o recibo JSON
em conteúdo textual e em `structuredContent.audit_receipt`, junto de `data` e
`content_id`. A matemática roda em processo separado, com limites de bytes,
prazo, permissões, chamadas e concorrência (quatro por conexão por padrão).

```python
from nablamath.ai.sandbox_verifier import AIVerifier

# Execute em um programa com guarda if __name__ == '__main__'.
verifier = AIVerifier()  # Prazo total máximo de cinco segundos.
proved = verifier.verify('x*x >= 0')
refuted = verifier.verify({'goal': 'x+1 = x', 'assumptions': []})
```

Conjecturas usam relações controladas e álgebra racional/polinomial, sem `eval`
ou execução de código da IA. O fragmento QF_NRA aceita multiplicações e potências
inteiras limitadas; QF_LRA preserva a API linear anterior. Domínios de divisões
são hipóteses explícitas. Hipóteses inconsistentes são recusadas. Contraexemplos
racionais exigem replay exato independente; modelos exclusivamente algébricos
não são inventados como testemunhas racionais.

O supervisor usa processo `spawn`, timeout nativo Z3 e prazo de parede que inclui
tradução e importação. Reserva parte do orçamento para terminar e recolher o
processo; não usa apenas uma thread que continuaria presa. Há limites de entrada
(64 KiB), estrutura e resposta. O escalonamento do sistema operacional ainda
impede garantias de tempo real rígido sob qualquer carga.

Os estados são `PROVEN`, `COUNTEREXAMPLE_FOUND`, `TIMEOUT_REJECTED`, e recusas
distintas `UNSUPPORTED`, `UNAVAILABLE`, `REJECTED`. `PROVEN` é resultado SMT no
fragmento declarado; não é certificado Lean, avaliação de prosa, validação de
modelo físico nem proteção universal contra alucinações. O módulo não é um
sandbox de segurança do sistema operacional para executar código arbitrário.

## Matemática adicional

| Operação | Implementação e contrato |
|---|---|
| `spectral` | FFT radix-2/Bluestein e inversa, Haar ortonormal/inversa, convolução, espectro, filtro passa-baixa e STFT Hann. Dados complexos como `[real, imaginário]`; aritmética flutuante com orçamentos de amostras/saída. |
| `complex_analysis` | Integração adaptativa de Simpson em contornos poligonais complexos e mapas de Möbius com derivada. Erro estimado, sem certificado automático de analiticidade, polos ou univalência global. |
| `differential_geometry` | Métrica exata e suas derivadas até ordem dois, ou expressões simbólicas SymPy em AST restrita; inversa, Christoffel, Riemann, Ricci e curvatura escalar. Até quatro dimensões, incluindo assinatura de Lorentz não degenerada; sem validação global de variedade. |
| `abstract_algebra` | Potência/inversa modular até 4096 bits, operações em corpos finitos existentes, primalidade determinística abaixo de 2⁶⁴, campanhas Miller–Rabin reprodutíveis acima disso e verificação exata de certificados Pocklington. Primos prováveis não são promovidos a certificados ou geração de chaves. |

Todos entram no mesmo catálogo, CLI, HTTP, notebooks, replay e MCP. Os módulos
oferecem `calculate(...)` para produzir recibos diretamente. Wavelets gerais,
mapas conformes arbitrários, otimização de toda expressão simbólica e todos os
ramos da matemática permanecem fora desses contratos explícitos.

## Camada 3: visualização e publicação

`WebGLExporter.heightfield` transforma matrizes retangulares em malhas. As saídas
GLB e GLTF 2.0 incluem posições float32, normais, índices uint32, cores opcionais,
limites dos accessors, recibo e SHA-256 do buffer. Coordenadas seguem metros,
sistema destro e Y para cima. Malhas degeneradas são recusadas, inclusive após
quantização float32. Arquivos existentes são preservados. O formato pode ser
consumido por Three.js, mas exportação não garante 60 fps no dispositivo leitor.

`ManimAnimator` exporta scripts nativos a partir dos resultados auditados de
integrais e trajetórias EDO, com transições e hash completo visível. Não inventa
passos de uma demonstração que o recibo não contém. Renderiza MP4 com timeout,
controle de log e encerramento do grupo de processos; registra hashes do script
e vídeo. Usa texto seguro em vez de interpolar código TeX ou Python do usuário.

`TypstCompiler` recebe bundle verificado e template Typst confiável. Bindings
RFC 6901 substituem `{{variavel}}` por dados literais, sem executá-los como
código. Figuras precisam estar em `asset_root` explícito e ficam copiadas com
hash no histórico. O template padrão oferece grade equilibrada em resumos curtos
e fluxo amplo em relatórios extensos; não é um template oficial da revista Nature.
Os detalhes tipográficos estão no [guia editorial](EDITORIAL_DESIGN.md).

O rodapé de cada página contém o hash do experimento e a assinatura fornecida,
ou a declaração de ausência de assinatura. O compilador verifica a presença
real dos identificadores em todas as páginas com pypdf. Assinaturas exigem
chaves pinadas em `CryptoRegistry`; `require_signature=True` recusa ausência ou
revogação. O escopo assinado identifica bundle inteiro ou recibo específico:
isso não equivale a uma assinatura digital do próprio PDF.

`watch` observa alterações no bundle; alterações de dados/template/figuras
invalidam o cache. Builds criam snapshots históricos imutáveis, manifesto e
publicação por substituição de arquivo. Um lock do SO impede escritores
concorrentes; PDF estrangeiro ou adulterado não é sobrescrito, e falhas de
compilação preservam a última versão válida. PDF e manifesto são dois arquivos:
uma queda entre suas substituições é detectável por `verify_publication`, mas
não há transação de filesystem entre ambos. O histórico mantém os builds.
Se o bundle assinado mudar, sua nova assinatura deve ser fornecida pelo
responsável pela chave; uma assinatura antiga não autentica os novos resultados.

## Verificação e limites de prontidão

Os testes `test_production_*.py` cobrem referências DFT/NumPy/PyWavelets,
resíduos, curvatura da esfera, corpos finitos, replay, preservação de autograd,
ausência de materialização CPU no trace, buffers, timeout com solver travado,
MCP real, recuperação de OOM injetada, GLB binário, MP4 real, PDF real,
assinaturas, revogação e atualização do documento. Os extras ausentes produzem
skips explícitos. O workflow `scientific-ecosystem.yml` instala os renderizadores,
executa a demonstração e valida o GLB com o validador independente Khronos.

```bash
python -m pytest -q tests/test_production_*.py
npm install --prefix .nabla/gltf-validator --ignore-scripts gltf-validator@2.0.0-dev.3.10
node tools/validate_gltf.cjs .nabla/meu-fluxo/decay.glb .nabla/gltf-validator
python tools/vision_readiness.py
```

Os perfis executados podem sustentar programas satélites dentro desses limites.
A certificação de produção geral ainda exige campanha no hardware GPU real,
carga e falhas no ambiente de implantação, dependências formais compiladas,
reprodução e revisão científica independente. Esses requisitos não desaparecem
ao implementar as interfaces editoriais ou obter testes verdes.
