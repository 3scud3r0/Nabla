# Segurança

Este é um protótipo local. Não conecte o coordenador SQLite à internet, não execute código de terceiros com credenciais e não publique arquivos de banco sem revisão. A API de agentes aceita apenas expressões da gramática restrita; a interface de execução de código arbitrário recusa solicitações. Identificadores de trabalhador do coordenador local **não** são autenticação.

Para vulnerabilidades, use a função privada **Report a vulnerability** do GitHub quando estiver habilitada; caso contrário, contate o mantenedor por canal privado antes de divulgar detalhes. Não inclua chaves, senhas, dados de participantes ou scripts de exploração em issues públicas. A política formal de resposta e o endereço de contato ainda precisam ser estabelecidos antes de operar um serviço público.

## Perfil local candidato a 1.0

O desktop deve permanecer em loopback, com sessão/origem verificadas. O token de
publicação é transitório e deve ser removido do campo após sucesso ou erro.
Nunca use o desktop como serviço compartilhado nem forneça credenciais a código
de terceiros. Os perfis de CPU limitam admissão cooperativa; não isolam código
hostil no sistema operacional. O comando de código arbitrário permanece recusado.

Backups e notebooks são publicados sem sobrescrita. SHA-256 e RECORD verificam
consistência de bytes; não autenticam um distribuidor que possa reescrever o
manifesto. Distribuição assinada requer uma autoridade realmente configurada e
chave pública obtida por canal independente. A revisão de segurança independente
e das dependências é um gate de release, não uma conclusão dos testes locais.
