# Backup e execução contínua

## Backup automático

`python -m backend.server` inicia dois workers independentes da página: geração semanal e backup SQLite. O backup executa ao iniciar e depois a cada 24 horas de execução. Reiniciar faz uma nova cópia. O padrão mantém os sete backups mais recentes na pasta `backups` ao lado do banco. Configure com `--backups`, variável `BACKUP_DIR` e `--reter-backups`. `--sem-backup` desativa o worker.

A cópia usa a API online `sqlite3.Connection.backup`, não a cópia bruta do arquivo. A origem é aberta somente para leitura. O arquivo temporário só recebe o nome final após passar em `integrity_check` e `foreign_key_check`. A retenção remove exclusivamente arquivos com nomes próprios desta aplicação na pasta de backup, após uma cópia válida. Falhas são registradas e geram nova tentativa após 60 segundos. Cada cópia tem orçamento cooperativo de 30 segundos; armazenamento lento pode atrasar operações do sistema além desse prazo.

## Comandos manuais

```powershell
.\.venv\Scripts\python.exe -m backend.backup criar --banco data/igreja.sqlite3 --diretorio data/backups --reter 7
.\.venv\Scripts\python.exe -m backend.backup restaurar CAMINHO_DO_BACKUP data/restaurado.sqlite3
```

A restauração exige um destino novo, nunca sobrescreve o banco ativo e verifica a integridade. Para assumir uma restauração, pare o servidor, valide os dados restaurados e inicie explicitamente com `--banco data/restaurado.sqlite3`. Preserve o original até confirmar a recuperação.

Um backup na mesma máquina permite recuperar erros lógicos e arquivos corrompidos, mas não a perda do volume inteiro. Cópia externa para outro armazenamento continua pendente; nenhum envio a serviços externos foi configurado.

## A geração automática funcionará hospedada?

Sim, quando `backend.server` estiver executando continuamente, sem `--sem-agendamento`, com banco gravável persistente. O worker independe de requisições HTTP, dispara segunda-feira às 00h em America/Sao_Paulo e passa a versão publicada da semana anterior para o algoritmo. Se o processo estiver desligado nessa hora, gera a semana faltante na retomada; não há execução enquanto a aplicação estiver suspensa.

Requisitos de operação:

1. Processo de longa duração, com reinício automático pelo provedor ou supervisor.
2. Volume persistente para o SQLite e backups. Deploy não pode apagar esse diretório.
3. Uma instância é a configuração recomendada para este SQLite local. Várias instâncias com arquivos diferentes não compartilham dados ou travas.
4. Bind HTTP em `0.0.0.0` e porta informada pelo provedor. O padrão local continua `127.0.0.1:8000`.
5. Monitorar `/healthz` e logs de geração/backup. O endpoint verifica banco e liveness das threads; não comprova que toda tarefa recente teve sucesso.

O servidor aceita `HOST`, `PORT`, `DATABASE_PATH` e `BACKUP_DIR`. Exemplo de configuração no painel da hospedagem:

```text
HOST=0.0.0.0
DATABASE_PATH=/var/data/igreja.sqlite3
BACKUP_DIR=/var/data/backups
```

`PORT` deve seguir a configuração do provedor. Inicialize o banco uma vez no volume persistente (`python -m backend /var/data/igreja.sqlite3`) e inicie com `python -m backend.server`. Instale as dependências e valide seu lock no sistema operacional escolhido antes do deploy; o ambiente atual validado é Windows/Python 3.13.

No Render, serviços gratuitos suspendem por inatividade e não aceitam disco persistente. Portanto, essa configuração não garante a transição na hora marcada nem a preservação do SQLite. Para manter esta arquitetura, usar um serviço contínuo com disco persistente. Fontes: [limitações dos serviços gratuitos](https://render.com/docs/free) e [discos persistentes](https://render.com/docs/disks).

O servidor atual usa HTTP da biblioteca padrão e atende o MVP local. Esta entrega não equivale a uma homologação pública de produção. Configuração do provedor, TLS, supervisão real, cópia externa e testes no ambiente hospedado ainda precisam ser concluídos. Nenhum recurso foi provisionado remotamente.

## Atualização: entrada de produção

O entrypoint para hospedagem agora é `python -m backend.production`, com Waitress, inicialização do volume novo, geração, backups e tratamento de sinais. `backend.server` permanece como opção local. Consulte [preparação de deploy](deployment.md).
# Operação atual com PostgreSQL

Para Render + Neon, siga [render-neon.md](render-neon.md). Backups externos cifrados estão preparados em `.github/workflows/database-backup.yml` e exigem configuração explícita de segredos e variável de ativação. O disco do Render gratuito não é persistente. As rotinas SQLite descritas abaixo continuam disponíveis para desenvolvimento local.

