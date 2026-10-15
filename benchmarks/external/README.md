# Catálogo e comparação externa

Estado: catálogo ainda sem conjuntos externos certificados. Fixtures e baselines
executados localmente não são grupos de replicação externa.

Para cadastrar uma fonte, registrar nome, versão, URL oficial, data de obtenção,
hash dos bytes originais, licença e restrições de redistribuição, população,
proveniência, autoria, transformações e condições de acesso. Não colocar dados
sem licença, credenciais ou conteúdo restrito neste diretório. Ausência de licença
bloqueia uso e redistribuição até esclarecer a autorização.

Cada comparação deve ligar fonte e revisão a um [protocolo](../protocols/README.md),
registrar versões dos sistemas, hardware, orçamento equivalente, métricas por
subgrupo e falhas. Resultado sem baseline comparável deve informar a limitação;
não agregar domínios incompatíveis apenas para melhorar a média. Preservar
artefatos negativos e incerteza estatística conforme o protocolo.

Os adaptadores [SymPy/Z3](../../src/nablamath/benchmarks/independent.py) exercitam
implementações distintas e verificação exata nos domínios suportados. Isso oferece
comparação de software, sem comprovar independência de dados, pesquisadores ou
instituições. Uma avaliação externa requer avaliador real com conflitos e
identidade verificados, execução em ambiente documentado e acesso independente
aos dados sob a licença aplicável.

Aceite de uma entrada: aquisição autorizada, replay recuperável, auditoria de
[contaminação](../contamination/README.md), parecer registrado e limites publicados.
Enquanto faltarem essas evidências, a entrada deve permanecer candidata.
