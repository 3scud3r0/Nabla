# ADR 0002 — AST existente e contratos científicos versionados

Estado: implementado para duas famílias racionais.

`expression.py` continua sendo a AST canônica (`Number`, `Symbol`, `Binary`).
`core/semantic_ir.py` adiciona contratos imutáveis de problemas, não um segundo
parser. Polinômios usam coeficientes racionais em potências crescentes, sem zeros
finais. Sistemas lineares usam matriz quadrada e vetor exatos. Conversões para
AST permitem usar cálculo simbólico existente e gerar equações nos documentos.

`ScientificTask` versão 1 inclui família, domínio, variável, coeficientes ou
matriz/vetor. JSON canônico com racionais normalizados determina SHA-256. Semente,
solução, renderização e metadados de licença não alteram a identidade do problema.
Versões desconhecidas e campos inesperados são rejeitados na desserialização.

Limites: grau até 32 no contrato, até 8 na geração; sistemas de até 8 incógnitas;
racionais de até 256 bits. Floats e booleanos são rejeitados neste contrato exato.
Novas famílias e migrações precisam de contratos e testes explícitos. Não se
presume compatibilidade com qualquer representação ou hardware futuro.
