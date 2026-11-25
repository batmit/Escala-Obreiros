# Hospedagem gratuita e geração por acesso

## Opção que preserva o SQLite atual

PythonAnywhere gratuito é a opção preparada para homologação sem trocar o banco por PostgreSQL. A aplicação usa o disco da conta e o servidor WSGI do provedor; não precisa de Docker, Waitress em processo próprio, cron ou threads em background.

Condições atuais publicadas pelo provedor: uma aplicação com um worker, expiração de um mês e quota de 512 MiB. É necessário renovar a aplicação no painel antes de expirar e acompanhar uso de disco/CPU. O ambiente `innit` oferece Python 3.13. A instalação do OR-Tools e os testes devem ser confirmados na conta escolhida; esta preparação não equivale a homologação nesse provedor.

Referências: [contas gratuitas](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [quota](https://help.pythonanywhere.com/pages/DiskQuota/), [versões Python](https://help.pythonanywhere.com/pages/PythonVersions/), [restrições de background](https://help.pythonanywhere.com/pages/AsyncInWebApps/).

Render gratuito não preserva SQLite local: arquivos são perdidos ao suspender/reiniciar. Não basta mudar o plano do Blueprint pago para free. Para usar Render grátis com dados duráveis, seria necessário outro banco persistente externo e adaptar o repositório. [Limitações do Render](https://render.com/docs/free).

## Comportamento implementado

1. O navegador abre a página e consulta `/api/escalas`.
2. O backend calcula a semana vigente em America/Sao_Paulo e consulta o banco.
3. Se já houver uma escala publicada dessa semana, o algoritmo não é chamado.
4. Se faltar, gera, valida e publica usando a escala anterior persistida como parâmetro. Trava e publicação condicional protegem acessos concorrentes.
5. A API devolve as alocações salvas para o calendário.

O controle semanal é persistente, não uma variável em memória. Reiniciar ou recarregar não altera a escala. A navegação futura não provoca geração de semanas futuras; ela verifica somente a semana vigente. `/healthz`, HEAD, arquivos estáticos e consultas inválidas não disparam geração. Sem visitas, não há geração na virada: ela ocorre na primeira consulta da nova semana, conforme a estratégia escolhida.

Em uma falha, a API retorna 503 e permite outra tentativa; não apaga escalas anteriores nem publica uma proposta inválida. Se outro processo estiver gerando, a escala pode ficar temporariamente indisponível até a conclusão. O limite de geração atual é de 10 segundos, compartilhado entre as consultas do solver.

Backups ocorrem no primeiro acesso após 24 horas sem cópia recente, mantendo três arquivos para economizar disco. Não são backups diários garantidos sem acessos. Falha de backup é registrada e não oculta uma escala já publicada. Cópia externa continua pendente.

## Configuração PythonAnywhere

1. Criar uma conta gratuita e selecionar Python 3.13 numa aplicação Web de configuração manual.
2. Colocar o código em `/home/USUARIO/Escala-Obreiros` via Git ou upload. Não expor a pasta do banco como arquivos estáticos.
3. Criar o virtualenv e instalar dependências na consola Bash:

```sh
python3.13 -m venv /home/USUARIO/venv-escala
/home/USUARIO/venv-escala/bin/python -m pip install --no-cache-dir --only-binary=:all: -r /home/USUARIO/Escala-Obreiros/requirements-lock.txt
```

4. Configurar esse virtualenv na aba Web. Adaptar `deploy/pythonanywhere_wsgi.py.example` com o nome de usuário e copiar o conteúdo para o arquivo WSGI do provedor.
5. O arquivo cria `application = criar_wsgi('/home/USUARIO/dados-igreja/igreja.sqlite3')`. Não executar `backend.production`, `backend.server` ou seus agendadores no WSGI do provedor.
6. Rodar `python -m unittest backend.test_on_access -v` na pasta do projeto com o virtualenv. Confirmar instalação, disco disponível e duração antes de recarregar a aplicação.
7. Acessar a página, verificar os nomes e repetir a consulta para confirmar que o ID/versão da escala não muda. Recarregar o app e conferir persistência. Renovar a aplicação mensalmente no painel.

As dependências numéricas podem consumir parte significativa dos 512 MiB. Instalação sem cache e ausência de venvs duplicados ajudam; conferir o espaço real da conta. Se não couber ou o CP-SAT não funcionar nas restrições WSGI, essa opção não deve ser promovida; considerar outro provedor ou separar o solver do armazenamento.

## Preservar o banco local

Um arquivo ausente inicia uma base nova com a configuração da igreja. Para manter as escalas já geradas, fazer backup local e transferir explicitamente para a conta; restaurar em um caminho novo e apontar o arquivo WSGI para ele. Não sobrescrever banco em uso. Esta tarefa não enviou dados, não criou conta e não publicou recursos.

## Testar com Waitress localmente

```powershell
$env:GENERATION_MODE = 'on-access'
.\.venv\Scripts\python.exe -m backend.production
```

Esse modo não inicia workers de geração ou backup; executa a manutenção na consulta. `continuous` mantém a alternativa de processo permanente, usada na configuração Docker/Render paga. O frontend é o mesmo nos dois modos.
# Decisão atual

Escolhemos Render gratuito + Neon PostgreSQL. Consulte [render-neon.md](render-neon.md) para implementação, migração e operação. Comparações e instruções de outros provedores abaixo são histórico da avaliação.

