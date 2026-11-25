# Execução contínua e hospedagem

**Procedimento vigente:** [Render gratuito + Neon](render-neon.md). O Blueprint atual usa PostgreSQL externo, sem disco e sem workers permanentes. As instruções de SQLite, volume e agendamento contínuo abaixo descrevem a alternativa local anterior.

## Estado da preparação

A aplicação dispõe de um entrypoint de produção (`python -m backend.production`) com Waitress, geração semanal e backups no mesmo processo. A API WSGI é compartilhada com o servidor local, evitando duas implementações das regras de consulta. Somente arquivos públicos explicitamente permitidos são servidos.

O runtime inicia um banco novo com os dados da igreja, migra bancos existentes e preserva suas configurações. Um banco existente inválido/incompleto causa falha explícita. Não substitui banco existente por um vazio.

SIGTERM/SIGINT solicitam encerramento. Os workers param antes do fim do processo; o supervisor tem 60 segundos de tolerância. Se uma thread essencial morrer, o processo termina com erro para permitir reinício pelo provedor. Falhas de tarefas são registradas e tentadas novamente sem derrubar o worker.

## Docker Compose: máquina ou servidor próprio

Pré-requisito: Docker com motor Linux iniciado. A imagem roda com UID/GID 10001, usa Python 3.13 e dependências fixadas.

```sh
docker compose config --quiet
docker compose up --build --detach --wait
docker compose logs --follow
```

Página: http://localhost:8080. O bind externo está limitado ao loopback. Em servidor próprio, colocar um proxy HTTPS na frente dessa porta, sem expor diretamente o container à internet.

O volume nomeado `igreja-data` conserva banco e backups. `restart: unless-stopped` reinicia o processo após falhas e quando o Docker reinicia, desde que não tenha sido parado manualmente. O Docker precisa iniciar junto com o sistema operacional. Um healthcheck unhealthy, sozinho, não aciona essa política; a aplicação encerra se detectar uma thread essencial morta.

```sh
docker compose restart
docker compose down
```

`down` mantém o volume. **Não usar `down -v` para atualizar o serviço**, pois isso remove o volume de dados. Antes de atualizar imagem, criar um backup e manter uma cópia externa. Para atualização: obter o código aprovado, executar `docker compose up --build --detach --wait` e verificar logs e `/healthz`.

## Render: configuração preparada, ainda não provisionada

`render.yaml` configura um web service Docker, plano pago `starter`, uma instância, disco persistente de 1 GB em `/var/data`, healthcheck `/healthz` e até 60 segundos para encerramento. Deploy automático está desativado para permitir validação e promoção manual. O plano e o disco geram cobrança quando provisionados; este trabalho não criou recursos remotos.

Sequência de homologação:

1. Enviar o código para o GitHub e exigir os três jobs de CI aprovados, incluindo construção e testes Linux.
2. Validar o Blueprint no Render e revisar plano, preço, região e acesso antes de criar o serviço.
3. Confirmar que o volume permite escrita pelo UID 10001. Se o provedor montar o disco com outro proprietário, ajustar a propriedade do diretório pelo mecanismo suportado do provedor antes de iniciar; não executar a aplicação inteira como root nem tornar os dados públicos.
4. Conferir a criação inicial, logs de agendamento e backup, `/healthz`, nomes no calendário e API.
5. Reiniciar o serviço e confirmar que o ID da escala e os backups permanecem.
6. Simular uma semana faltante em ambiente isolado, validar restauração e só então promover o domínio de produção.

O SQLite exige uma instância e o mesmo volume entre reinícios. Não usar discos efêmeros ou réplicas com bancos locais independentes. Em um redeploy com disco há uma janela de indisponibilidade; não há alta disponibilidade neste MVP.

## Transferir dados atuais

A imagem não contém o banco local e não o publica. Em um volume novo, será criada uma instalação nova. Para preservar as escalas atuais, criar backup com `backend.backup`, transferi-lo explicitamente para armazenamento privado no volume e restaurar em caminho novo. Configurar `DATABASE_PATH` para o arquivo restaurado antes de reiniciar. Conferir registros e preservar o original até a validação. Nenhuma transferência remota foi feita nesta preparação.

## Continuidade da geração

O processo ativo verifica a semana atual imediatamente e dispara a próxima na segunda-feira às 00h de America/Sao_Paulo. Ele carrega a versão publicada anterior como parâmetro do algoritmo. Semanas já publicadas não são substituídas automaticamente. O frontend é só consumidor e não precisa estar aberto para a geração acontecer.

Caso o processo fique parado na virada, a geração ocorrerá ao reiniciar. Isso exige um serviço sem suspensão por inatividade e volume persistente. A execução não depende do cron do computador local.

## Evidência e pendências

- 50 testes Python e 5 JavaScript aprovados localmente; inclui Waitress real, workers sem tráfego HTTP, reinício, preservação e encerramento.
- `docker compose config --quiet` validado.
- Docker Engine local estava desligado: imagem Linux e restart do container ainda não foram executados nesta máquina. O CI recebeu um job de build, testes na imagem e smoke test com volume/reinício; ele só executará após push.
- Nenhuma publicação no GitHub ou no Render foi realizada.
- Cópia externa dos backups, alertas externos e regras obrigatórias da branch ainda precisam ser configurados. Backups no mesmo disco não cobrem perda total do volume.

Referências: [Waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/), [Blueprint Render](https://render.com/docs/blueprint-spec), [discos persistentes](https://render.com/docs/disks), [restart do Compose](https://docs.docker.com/reference/compose-file/services/#restart).

## Alternativa gratuita sem execução contínua

Para evitar processo permanente pago, usar a factory backend.hosted_wsgi em hospedagem WSGI com disco persistente e geração por acesso. Consulte [opção gratuita](free-hosting.md). Render free com SQLite efêmero não preserva os dados; o Blueprint deste documento permanece como alternativa paga.
# Hospedagem escolhida: Render + Neon

O procedimento vigente está em [render-neon.md](render-neon.md). O Blueprint agora usa plano gratuito, sem disco, e geração por acesso. As instruções abaixo sobre volume SQLite e workers contínuos descrevem a alternativa local/legada; não devem ser usadas na configuração do Render gratuito.

