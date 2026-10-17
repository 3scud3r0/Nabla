# Validação da entrega Nabla 1.0

A entrega amplia o contrato local; não estabelece completude matemática universal
nem encerra automaticamente a matriz científica de 213 requisitos.

## Escopo executado

- Cinco módulos canônicos com mais de 2.000 linhas cada; 30 operações novas,
  totalizando 133 operações de catálogo e 156 ações aninhadas especializadas.
- Testes de identidades geométricas, aritmética exata, referência CAS, simulações
  com sementes, schemas fechados, recibos e replay das 30 operações novas.
- PDFs reais Typst, anexos/XMP, equações nativas, extração por CLI, fontes
  portáveis recompiladas, medições de layout e inspeção visual de duas páginas.
- Chromium real com Three.js/OrbitControls incorporados, colormap e slider;
  vídeos Manim 3D sem MathTex renderizados para MP4.
- Exemplo `examples/v1/scientific_publication.py`: geração e verificação de
  publicação e cena offline, mais GLB animado e texturizado. Validador Khronos
  `2.0.0-dev.3.10`: **zero erros, avisos, informações ou sugestões**.

## Bloqueios conhecidos do ambiente

- Mathlib: o checkout da dependência fixada foi restaurado, mas o download dos
  binários de cache falhou com HTTP 403 da política de rede. Não há aprovação
  Lean dos novos algoritmos nem encerramento da aceitação formal integral.
- MathTex em vídeo: `dvisvgm` ausente. A instalação global não tem permissão e
  o índice Debian fixado retornou HTTP 403. O teste que exige esse binário é
  pulado com motivo explícito; a CI instala o pacote. Os outros vídeos reais
  foram renderizados. A falha original de renderização foi preservada.
- Chromium gerenciado bloqueia navegação `file://`. Os testes usam os mesmos
  bytes HTML por uma rota HTTPS interceptada, sem buscar assets externos.
  Abertura direta de arquivos não foi validada nessa política do navegador.
- GPU NVIDIA, TPU e cluster acadêmico não foram certificados pela suíte CPU.

## Falhas corrigidas e evidência preservada

As execuções originais ficam em `.nabla/vision-readiness/` e logs locais de
preparação. A primeira auditoria completa, `20261017T134108600926Z`, encontrou
3 falhas: dois bundles ficaram desatualizados durante implementação e faltava
um caso `advanced_math` no teste anterior de maturidade. O teste da expansão
anterior também revelou índice incorreto de geradores de grupo fundamental;
o algoritmo foi corrigido e recebeu teste de regressão.

Testes novos detectaram colisão do argumento `operation` na API da sessão,
compatibilidade com NumPy sem `trapz`, fontes matemáticas pequenas no PDF,
e dependência externa ausente para MathTex. Os contratos foram corrigidos,
a tipografia matemática ampliada e a ausência do binário ficou explícita.
Erros de montagem dos próprios testes e exemplos foram corrigidos, mantendo
os logs das execuções anteriores.

A auditoria completa final é executada com as fontes congeladas. Seus resultados
identificados e a verificação do wheel serão registrados abaixo antes do PR.
