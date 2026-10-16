# Painel pessoal NablaMath

## Iniciar

- Windows: abrir a [versão alpha](https://github.com/3scud3r0/Nabla/releases), baixar e executar `NablaMath-Setup-Windows.exe` depois que a CI Windows tiver aprovado e publicado esse release. O instalador usa a conta do usuário, sem privilégios de administrador. O projeto não declara o instalador disponível até essa execução terminar com sucesso. Ele ainda não possui assinatura de código; confira a origem no repositório e o hash publicado pelo GitHub.
- Linux/macOS ou desenvolvimento: instalar Python 3.10+; `python -m pip install .` no repositório (`python -m pip install ".[cloud]"` para habilitar o upload); executar `nabla desktop`. Em modo de desenvolvimento: `PYTHONPATH=src python -m nablamath.desktop.app`.

O botão executável abre `http://127.0.0.1:<porta>/`. Só é acessível neste computador. O SQLite e arquivos ficam em `~/NablaMath` (no Windows, a pasta `NablaMath` do usuário). A desinstalação não apaga o banco pessoal.

## Catálogo matemático integrado

O cartão **06 · Catálogo científico integrado** descobre as operações usando `GET /api/catalog` e executa JSON via `POST /api/calculate`. O servidor utiliza exatamente `CalculationSession.execute`, assim como `nabla calc` e o replay dos notebooks. O recibo inclui `content_id`, argumentos e limitações. A UI não executa código Python enviado pelo usuário e continua sujeita ao token local, Host e Origin; tentativas com domínios inválidos retornam erro sem cálculo silencioso. O navegador pode interromper a espera após 30 segundos; isso não representa cancelamento garantido da computação no servidor.

Os recibos multidomínio **não** são inseridos no banco legado `results.sqlite3`, pois aquela tabela é reexecutável exclusivamente para expressões. Para persistência, use `nabla calc ... --notebook arquivo-novo.json` e `nabla replay-notebook arquivo-novo.json`. Não é seguro forçar formatos distintos sob o mesmo ID de registro.

Use `nabla catalog` no terminal para consultar os campos obrigatórios e o domínio de cada operação. O [guia da primeira versão coesa](acceptance/COHESIVE_LOCAL_ALPHA.md) explica os gates ainda pendentes.

## Botões e arquivos

- **Calcular** avalia uma instância racional e salva cada etapa e a hipótese de denominador não nulo no banco.
- **Gerar LaTeX** grava `<identificador>.tex` na pasta pessoal. Para PDF, é preciso compilar o `.tex` com LaTeX instalado.
- **Iniciar loop / Parar** produz até 1.000 instâncias por sessão, a intervalos entre 0,1 e 60 segundos. O loop percorre quatro expressões conhecidas com valores racionais; são exemplos de teste, não resultados originais. O mesmo registro não é gravado duas vezes.
- **Órbita / fluxo** mostram, respectivamente, órbita terrestre circular ideal e solução analítica de fluxo laminar. A viscosidade e densidade da demonstração são fixadas em 1 Pa·s e 1000 kg/m³; a interface não resolve CFD geral.
- **Exportar** cria `verified.jsonl` e `verified.jsonl.manifest.json`. **Importar** lê `incoming.jsonl` e `incoming.jsonl.manifest.json` copiados manualmente para a pasta pessoal. A importação reexecuta e preserva duplicatas idênticas.
- **Criar lote curado** produz `curated.jsonl`, manifesto e cartão na pasta pessoal, separados por expressão.
- **Publicar** pede dataset Hugging Face `conta/nome`, token com escrita, licença, origem, responsável e confirmação de direitos. O sistema confere o hash e reexecuta o lote antes de enviar os três arquivos em um commit. O token é usado nesta requisição, sem ser salvo em disco. O envio pode ser repetido; verificar o destino antes de clicar.

**O loop do aplicativo é local.** Ele não submete execuções para uma fila NablaMath global em tempo real. O botão “Publicar” envia um lote curado diretamente ao dataset Hugging Face que você indicar, após confirmação; isso não conecta o computador a workers ou coordenadores do projeto.

Os registros são aritmética exata para entradas específicas: `formal_proof: false`. Provas Lean opcionais usam `nabla formal ID` no terminal com Lake instalado. Consulte [publicação](PUBLISHING.md), [limites técnicos](IMPLEMENTATION_STATUS.md) e [roteiro](ROADMAP_GLOBAL_RESEARCH.md).

## Operação do candidato local

Erros da interface permanecem visíveis no status. Os pedidos principais têm
timeout de 30 segundos no navegador; interromper a espera não desfaz um efeito
já concluído no servidor. Consulte histórico/arquivos antes de repetir. O botão
Parar cancela o loop local. Operações de publicação exigem a confirmação e seus
metadados; o campo de token é limpo também quando o envio falha.

O instalador candidato usa a versão do pacote. A CI Windows instala, calcula,
exporta, reinstala e desinstala esse artefato preservando banco e arquivos fora
da pasta de instalação. Esse teste precisa executar no SHA do candidato; ele
não substitui um ensaio de upgrade a partir de uma versão anterior publicada.
