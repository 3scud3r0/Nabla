# NablaMath — status verificável de publicação (24/09/2026)

**Scripts históricos publicados integralmente.** O branch `main` tem 134 arquivos, sendo 120 Python; dos quais **79 `.py` estão sob [`legacy/current_scripts/`](../legacy/current_scripts/README.md)**, exatamente com os 79 nomes e blobs Git do ZIP original (50 conteúdos distintos). A versão anterior do acervo permanece em `legacy/`, junto à documentação e fontes LaTeX.

**O ZIP original completo, os PDFs e as imagens do acervo permanecem pendentes:** a organização dos arquivos Python não implica upload dos 177 membros do ZIP de referência. Ver [instruções de transferência binária](UPLOAD_REMAINING_ARCHIVE.md).

- [Visão](../description.md)
- [Handoff para outra IA](AI_HANDOFF.md)
- [Histórico recuperável da conversa](CONVERSATION_FOR_NEXT_AI.md)
- [Inventário dos 177 itens](CONTENT_INDEX.md)
- [Pasta de 79 scripts Python](../legacy/current_scripts/README.md)
- [Importador dos arquivos restantes](../scripts/import_archive.py)

CI atual faz checagem de sintaxe e verificará o ZIP original quando transferido; não é validação científica.

## Organização de desenvolvimento (14/10/2026)

O acervo foi reunido em `legacy/current_scripts/`; os 79 scripts mantêm seus bytes originais. As contagens acima descrevem a publicação histórica de setembro, não o tamanho atual do projeto. A API ativa fica em `src/nablamath/`, com testes em `tests/`.
