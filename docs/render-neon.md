# Migração para Render gratuito + Neon

## Arquitetura escolhida

Render executa o container Python/Waitress e serve o calendário. Neon mantém os dados em PostgreSQL. `DATABASE_URL` seleciona os adaptadores PostgreSQL; SQLite continua disponível para desenvolvimento e como origem da migração. O frontend e os contratos do gerador permanecem iguais.

`GENERATION_MODE=on-access` verifica a semana vigente na consulta à API. Uma semana já publicada não chama o solver novamente. Na primeira consulta de uma semana ausente, carrega a versão anterior, gera, valida e publica transacionalmente. A aplicação não depende de cron ou workers permanentes. A suspensão do Render atrasa a primeira resposta, mas não apaga dados do Neon.

## O que foi adaptado

- Driver psycopg 3 e conexão TLS, com timeout e fechamento após cada operação. Não há pool local mantendo conexões ociosas; pode-se usar o endpoint pooled do Neon.
- Migração PostgreSQL versionada em `backend/migrations/0001_initial.sql`, com checksum e trava transacional para impedir aplicação concorrente.
- Datas nativas, timestamps com fuso, booleanos, JSONB e índices de integridade.
- Reserva de geração por UPSERT atômico com expiração usando o relógio do banco. Publicação serializada por semana usando advisory lock **da transação**, compatível com PgBouncer em transaction mode. Não são usados locks de sessão.
- Exportação consistente de SQLite/PostgreSQL e restauração transacional em PostgreSQL vazio, com verificação de todos os dados.
- `/healthz` verifica o processo sem consultar Neon a cada healthcheck; `/readyz` verifica acesso ao banco e configuração.
- `render.yaml` no plano free, sem disco, com `DATABASE_URL` como segredo e modo por acesso. Em Render, ausência de URL válida não faz fallback silencioso para SQLite.

## 1. Validar código e CI

Instalar `requirements-lock.txt`, executar testes e enviar o código ao GitHub. Há quatro jobs: backend Windows, frontend, container Linux e integração PostgreSQL. Os testes PostgreSQL só executam quando `TEST_DATABASE_URL` aponta para um banco local isolado; não usar Neon nesse parâmetro de teste.

Foram executados testes em Windows e na imagem Linux, incluindo concorrência, rollback e ensaio de migração. Alterações posteriores devem passar pelo CI antes de promover.

## 2. Criar o projeto Neon

Criar um projeto gratuito, escolher região próxima do Render e manter as cotas do plano gratuito. Não criar banco PostgreSQL no Render: o banco escolhido é o Neon. Guardar duas conexões em locais distintos:

- Conexão **direta administrativa** para migrações/restauração, usada em `DATABASE_MIGRATION_URL` apenas no computador do operador ou em execução administrativa controlada.
- Conexão **pooled da aplicação**, usada em `DATABASE_URL` no Render, mantendo os parâmetros TLS fornecidos pelo Neon (`sslmode=require`, ou verificação mais estrita).

URLs contêm senhas. Não colocar no Git, frontend, argumentos de comandos ou mensagens. O `.env.example` tem apenas placeholders; o programa lê o ambiente e não carrega `.env` automaticamente.

## 3. Exportar os dados SQLite atuais

Interromper gravações durante a troca definitiva. Exportação lê uma transação consistente e não altera a origem. O comando de backup SQLite anterior continua disponível para manter uma cópia adicional.

```powershell
.\.venv\Scripts\python.exe -m backend.transfer exportar --origem data/igreja.sqlite3 --arquivo data/migration/igreja.json.gz
```

O arquivo contém configuração, pessoas, participações realizadas, versões e alocações, além de checksum SHA-256. Não inclui credenciais ou travas transitórias. IDs, versões, nomes históricos e assinaturas são preservados. A saída não sobrescreve arquivo existente: escolher outro nome para um novo snapshot.

## 4. Restaurar em Neon vazio

Definir `DATABASE_MIGRATION_URL` no ambiente com a conexão direta administrativa. Depois:

```powershell
.\.venv\Scripts\python.exe -m backend.transfer restaurar --arquivo data/migration/igreja.json.gz
```

O comando aplica o schema versionado e importa todos os dados em uma transação. Se houver dados em qualquer tabela de negócio, ele recusa a importação. Conflitos de integridade ou diferença na comparação pós-importação revertem a carga, preservando o destino anterior. Nunca há TRUNCATE ou substituição automática de escalas existentes.

**Não executar `--seed` antes de importar**, pois isso preenche o destino e a restauração será recusada. Para começar uma instalação vazia sem dados antigos, usar alternativamente:

```powershell
.\.venv\Scripts\python.exe -m backend.migrate --seed
```

Para futuras migrações de esquema sem seed: `python -m backend.migrate`. Uma migração aplicada não deve ser editada; criar um novo arquivo numerado. O runtime HTTP não aplica DDL nem faz seed no PostgreSQL ao iniciar.

## 5. Separar os papéis de acesso

Como proprietário, criar papéis normais `escala_runtime` e `escala_backup` com LOGIN/NOINHERIT e definir senhas privadamente. Não lhes conceder papéis administrativos. Executar os GRANTs de `deploy/postgres_roles.sql` após a criação das tabelas.

O runtime lê configuração e histórico e só escreve escalas/alocações/travas. O backup tem SELECT nas tabelas de negócio. Migração e restauração continuam exclusivas da conexão administrativa. As permissões foram testadas com papéis PostgreSQL reais de acesso restrito.

## 6. Publicar no Render

Usar o Blueprint `render.yaml` depois de aprovar o CI e conferir as condições vigentes do plano. Ele não cria Neon automaticamente. Configurar `DATABASE_URL` com a conexão pooled do papel runtime.

Valores preparados:

```text
HOST=0.0.0.0
PORT=10000
GENERATION_MODE=on-access
DATABASE_URL=<segredo configurado no painel>
```

O Dockerfile já usa `python -m backend.production`. Não definir `DATABASE_PATH`, não anexar disco, não ativar os workers contínuos e não executar importação/seed no startup. A primeira inicialização exige schema e regras já carregados.

## 7. Homologar e promover

1. `/healthz` responde 200 sem acordar o banco; `/readyz` valida conexão/regras.
2. Calendário mostra as escalas migradas e os mesmos nomes/versões.
3. Vários acessos e reinícios não criam outra versão da semana.
4. Consulta futura não gera semanas futuras.
5. Uma semana ausente é gerada no primeiro acesso, usando a anterior.
6. Verificar falhas de conexão e restauração numa branch/banco separado, nunca sobre a produção.

Até essa validação, manter o SQLite original preservado. Após a troca, somente Neon deve receber gravações. Um retorno ao SQLite antigo perderia mudanças feitas depois da migração; nesse caso, preparar uma recuperação atualizada, em vez de simplesmente voltar ao arquivo antigo.

## Backups PostgreSQL

Não há backup persistente no disco do Render gratuito. O módulo SQLite `backend.backup` continua somente para arquivos locais; a exportação PostgreSQL é:

```powershell
.\.venv\Scripts\python.exe -m backend.transfer exportar --arquivo data/backups/neon.json.gz
```

Nesse comando, `DATABASE_URL` deve apontar para a conexão direta do papel backup. A restauração usa `DATABASE_MIGRATION_URL` e um destino vazio, seguindo o mesmo procedimento acima. O formato é uma exportação de dados da aplicação com checksum; não é um `pg_dump` genérico de objetos PostgreSQL.

Foi preparado `.github/workflows/database-backup.yml`: execução diária às 06:23 UTC e manual, exportação consistente, cifragem AES-256 via GPG e artefato com retenção de 30 dias. Apenas o arquivo cifrado é enviado. Para ativar, configurar:

- Secret `DATABASE_BACKUP_URL`: conexão direta do papel de leitura.
- Secret `BACKUP_PASSPHRASE`: chave forte com pelo menos 20 caracteres, sem quebras de linha; guardar também fora do GitHub.
- Variável `ENABLE_DATABASE_BACKUP=true`.

Sem a variável, o job permanece desativado. Descarregar um artefato e testar sua recuperação antes de depender dessa rotina. Para decifrar: `gpg --output snapshot.json.gz --decrypt snapshot.json.gz.gpg`, informando a chave no prompt. Sem a chave não há recuperação do arquivo cifrado.

Horários de GitHub Actions podem atrasar; workflows agendados em repositórios públicos também podem ser suspensos por inatividade. Monitorar execuções e conservar cópias independentes. A janela de recuperação do plano Neon não substitui uma política própria de backup. Nenhum segredo real foi configurado nem backup enviado remotamente nesta adaptação.

## Limites gratuitos

Render pode suspender o serviço sem tráfego. O Neon também pode suspender o compute, preservando dados. O primeiro acesso pode esperar pelos dois despertares e pela geração. Cotas de processamento, tráfego e armazenamento precisam ser acompanhadas; uma aba aberta atualizando frequentemente também conta como atividade. Não há garantia de custo zero fora das condições dos planos.

Referências: [Render free](https://render.com/docs/free), [Neon Python](https://neon.com/docs/guides/python), [pooling](https://neon.com/docs/connect/connection-pooling), [conexão segura](https://neon.com/docs/connect/connect-securely).
