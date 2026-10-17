# OMNI_ENGINE: implementação monolítica e execução CUDA

Toda a infraestrutura está em `src/nablamath/superintelligence/omni_engine.py`,
com mais de 23 mil linhas de código. As 13 seções numeradas de 0 a 12 incluem
480 kernels de diferenças finitas especializados, com coeficientes racionais
que satisfazem os momentos polinomiais. Esses kernels são executáveis em
NumPy e Torch CPU/CUDA e preservam autograd. Eles atendem derivadas de ordens
1 a 4, precisão de ordens 2 a 20 e condições periódicas, reflexão e exterior zero.

O catálogo inclui `omni_superintelligence`, totalizando 134 operações canônicas.

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install '.[superintelligence]'
```

O wheel CUDA deve corresponder ao driver do equipamento. `device="auto"` escolhe
CUDA quando disponível. `device="cuda"` exige uma GPU real e um build CUDA do
Torch; a execução falha explicitamente quando indisponíveis. `device="cpu"`
seleciona CPU. Não existe fallback silencioso de uma solicitação CUDA.

```python
import torch
from nablamath.superintelligence import OmniEngine

engine = OmniEngine(device="cuda:0", seed=42)
x = torch.randn(16, 1, 32, 32, device="cuda:0")
y = torch.zeros_like(x)
execution = engine.execute(
    "train_surrogate_fno", capture_values=False,
    inputs=x, targets=y, epochs=20, batch_size=4,
    physics_weight=0.01, viscosity=0.01,
)
assert next(engine.neural.model.parameters()).is_cuda
print(execution["receipt"]["metadata"]["gpu_seconds"])
prediction = engine.neural.predict(x)
```

`capture_values=False` mantém entradas e resultados como tensores nativos.
O recibo armazena forma, dtype, dispositivo e SHA-256 dos bytes, lidos em blocos
limitados. A captura padrão por valores serve a JSON, CLI e replay do catálogo.
A telemetria fica separada do resultado reproduzível. Eventos CUDA medem tempo
decorrido no stream; valores `None` e `not_used` identificam execuções sem GPU.
Cada chamada limpa sua telemetria para não atribuir GPU de uma ação anterior.

```python
from nablamath.calc import CalculationSession

with CalculationSession() as session:
    result = session.execute(
        "omni_superintelligence", action="verify_chain_of_thought",
        parameters={"reasoning": "x+x=2*x\nx=x", "seed": 42},
    )
    print(result.to_data())

engine.execute(
    "synthesize_synthetic_dataset", count=1000000,
    kind="polynomial", difficulty=3, filename="training.jsonl",
)
```

O arquivo é gravado em streaming; arquivos existentes são protegidos por criação
exclusiva. Efeitos externos usam a API direta. O catálogo aceita ações em memória.
Checkpoints FNO têm SHA-256 esperado e são carregados com `weights_only=True`.

## Algoritmos e contratos

- **Operadores e física:** FNO treinável em minibatches e DeepONet; resíduos
  por autograd ou diferenças finitas nativas; Navier–Stokes exige pressão e
  inclui divergência. O treinamento oferece uma penalidade física estacionária
  de difusão e não afirma resolver toda PDE. A auditoria de Hamiltonianos recusa
  deriva relativa acima de `1e-4` e exige o fallback exato declarado pelo chamador.
- **Inferência:** intervenções racionais por fatorização truncada de DAGs
  discretos; NOTEARS SciPy ou Torch com exponencial matricial diferenciável,
  Lagrangiano aumentado e diagnóstico de convergência; GP Nyström com acumulação
  de estatísticas suficientes em chunks, predição em streaming, EI e UCB nativos.
  Incerteza é condicional ao modelo, sem certificação universal da função real.
- **Radiometria:** 32 bandas entre 380 e 780 nm, GGX/Smith/Fresnel com IOR complexo,
  esferas e triângulos, emissores e ambiente. O backend wavefront Torch implementa
  múltiplo espalhamento Henyey–Greenstein em um meio homogêneo limitado por esfera,
  com ponderação espectral da proposta majorante. MIS combina ambiente e BSDF;
  emissores de geometria são amostrados pelos caminhos BSDF. A profundidade finita
  trunca caminhos. Welford acumula a variância da média por pixel. OpenEXR float32
  contém o recibo e o hash no cabeçalho; integridade não comprova convergência física.
- **Gaussianas:** projeção de covariâncias, cores SH e alpha-blending em profundidade,
  autograd Torch e inferência NumPy. Hooke/J2 atualiza tensões, plasticidade,
  posições e covariâncias em batches nativos. Velocidades/gradientes são entradas
  do acoplamento; equilíbrio global e colisões exigem um modelo externo.
- **Dados:** Arrow primitivo sem nulos e Zarr hierárquico com chunks/shards
  decodificados de até 64 MiB; buffers contíguos compartilham memória quando seguro.
  `iter_device_chunks` oferece staging CUDA fixado em memória. Zarr comprimido
  aloca memória. Merkle usa uma fronteira logarítmica; finalizar não relê dados,
  enquanto ler e hashear 1 TB continua linear nos bytes e depende do hardware.
- **Provas:** PUCT sobre operações canônicas para metas racionais e PUCT Horn
  com expansão, rollout e retropropagação de deduções verificadas por unificação.
  Horn prova consequências dos axiomas declarados. A ponte assíncrona reconhece
  o Lean no PATH ou a instalação oficial fixada do checkout. SMT estruturado usa
  `AIVerifier`, com replay racional de contraexemplos. Código Lean/SMT-LIB direto
  é código local confiável, sem sandbox de sistema operacional.
- **Síntese e PRM:** integrais polinomiais, espectros triangulares, fatoração por
  raízes inteiras e circuitos CNOT em estados computacionais; cada cálculo tem
  recibo reexecutável. O PRM verifica igualdades atômicas ou implicações racionais
  estruturadas e produz pares DPO. Prosa livre sem suporte é recusada.
- **Conjecturas e currículo:** busca limitada em frações contínuas e PSLQ com
  precisão arbitrária e rechecagem duplicada, sem promover candidatos a teoremas;
  fuzzing de fronteiras e negação SMT; Elo e retenção de falhas para dados reflexivos.
- **RLVR:** JSONL e Parquet em streaming com validação de recibos, enunciado e
  vínculo da resposta ao cálculo. Campos estruturados Parquet usam JSON canônico.
  `verifier_signature` declara escopo e não é assinatura criptográfica nem garantia
  geral de ausência de alucinação.

## Dispatcher

Além das seis ações da especificação, são expostas `fit_sparse_gp`, `pde_residual`,
`rasterize_physical_gaussians`, `advance_gaussian_mechanics`, `run_horn_proof_search`,
`search_ramanujan_high_precision`, `hash_tensor_stream` e `search_ramanujan_conjecture`.
Ferramentas de IA usam schemas fechados com tipos aninhados e limites explícitos.

## Verificação

```bash
python -m pytest -q tests/test_omni_engine.py tests/test_omni_engine_devices.py
NABLA_REQUIRE_CUDA=1 python -m pytest -q tests/test_omni_engine_devices.py
python tools/vision_readiness.py
```

O workflow manual `.github/workflows/omni-engine-gpu.yml` exige runner
`[self-hosted, linux, x64, gpu]`, verifica hardware com `nvidia-smi` e falha se CUDA
não estiver disponível. A suíte cobre gradientes, kernels analíticos, paridade CPU,
checkpoints, volumes, recibos e execução CUDA real quando há equipamento.
Os testes CUDA são pulados explicitamente em hosts sem GPU; isso não constitui
validação de GPU. O painel de visão permanece separado do aceite científico.

A branch `feat/omni-engine-cuda` também tem um job restrito de regeneração dos
bundles. Ele reconstrói e verifica `math.txt` e `NABLA.TXT` antes de publicar
somente esses dois artefatos, sem force-push. O job CUDA continua manual e
exige o runner físico; a regeneração não afirma validar hardware.
