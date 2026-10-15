# Política de revisão independente — versão 1

Estado: proposta operacional para revisão no PR; não registra aprovação de uma
pessoa, vínculo institucional ou avaliação externa já realizada. Aplica-se a
cada revisão de alegação e a cada versão de documento separadamente.

## Condições de uma revisão

1. O proponente fornece revisão da alegação, autores, domínio, escopo, limitações
   e artefatos identificados por conteúdo. Um identificador sem conteúdo
   recuperável não satisfaz a condição de evidência.
2. O responsável pelo processo registra quem designou os revisores e verifica
   identidade, competência no domínio e conflitos: autoria, vínculo financeiro,
   colaboração recente e responsabilidade pelo sistema avaliado. Ausência de
   conflito declarado não prova independência. Não há responsável nomeado nesta
   política; designação e aceite devem constar do registro de execução.
3. Pelo menos dois revisores distintos emitem aceitar, rejeitar ou revisar, com
   justificativa e evidências. Uma objeção aberta impede recomendação favorável.
   Recurso exige uma nova revisão encadeada; preservar decisões anteriores.
4. Mudanças no documento, hipótese, dados ou protocolo invalidam a aplicabilidade
   da decisão anterior à nova versão. Solicitar revisão da versão alterada.

## Implementação disponível e limite

[ReviewBoard](../../src/nablamath/knowledge/peer_review.py) verifica conflitos
**declarados**, especialidade declarada e encadeamento; não promove o estado da
alegação. `sign_review` e `submit_signed_review` verificam assinatura contra uma
chave fixada em `PeerTrust`; a chave não autentica competência, vínculo ou
independência no mundo real. Registrar a origem da verificação da chave fora do
próprio envelope assinado.

[Revisão editorial](../../src/nablamath/documents/editorial_review.py) resolve
conteúdo e vincula o parecer ao documento. Compilar HTML/PDF, inspecionar páginas
e validar ciência são atividades diferentes. Inspeção visual deve identificar
artefato, páginas, notas e defeitos; a API registra a declaração, não executa a
inspeção humana. `local_checks_passed` não significa revisão externa concluída.

Aceite externo: pareceres reais, conflitos verificados, identidade documentada,
artefatos recuperáveis e replay por terceiro. Na ausência deles, manter
"implementado localmente; revisão externa pendente".
