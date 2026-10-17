# Exemplos

Execute da raiz, após instalar o pacote no ambiente:

```sh
python examples/first_problem.py
```

| Arquivo | Finalidade |
|---|---|
| `first_problem.py` | Primeiro cálculo e recibo rastreável |
| `orbit_report.py` | Modelo orbital ideal e relatório |
| `scientific_phases_5_8.py` | Fluxo científico das fases 5–8; requer extras |
| `math/advanced_exact_workflow.py` | Fluxo integrado de álgebra exata, corpos finitos, análise, fluxos e probabilidade com replay de notebook |
| `math/exact_laboratory.py` | Operações avançadas de aritmética racional exata, raízes, matrizes e otimização |
| `scientific_plan.json` | Plano declarativo para ferramentas registradas |

Consulte os argumentos e destinos no próprio exemplo antes de executá-lo.
Para campanhas reexecutáveis com manifestos e resultados reservados, use as
[ferramentas de reprodução](../tools/README.md). Exemplos ilustram modelos
delimitados; não constituem validação física experimental.

## Consolidação 1.0

`python examples/v1/reproduce.py .nabla/v1-demo` gera três referências auditadas, HTML 3D, GLB e uma publicação PDF/HTML com dados anexados. Use um destino novo e instale os extras `advanced,publishing`.

`python examples/v1/scientific_publication.py NOVO_DIRETORIO` gera um artigo
com equações nativas, referências, tabela e figura, recompila a fonte Typst,
inspeciona o PDF e cria Three.js offline e GLB animado/texturizado. O campo
3D é identificado como ilustrativo. Os extras `advanced,scipy,publishing,graphics,editorial`
são necessários. O validador Khronos pode conferir `textured-animated.glb`.
