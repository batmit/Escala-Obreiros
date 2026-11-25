# Integração contínua

O quarto job provisiona PostgreSQL 17 isolado e executa os testes com `TEST_DATABASE_URL`, incluindo migração, concorrência, rollback e permissões restritas. Também constrói a imagem e verifica geração por acesso e persistência após reinício sem volume. Nos jobs sem PostgreSQL, os oito testes específicos desse banco são ignorados explicitamente. Nenhum teste usa Neon de produção.

O workflow `.github/workflows/ci.yml` executa em pushes, pull requests e manualmente pela aba Actions do GitHub. São quatro jobs: backend Windows, frontend, container Linux e integração PostgreSQL.

## Backend

Runner Windows x64 com Python 3.13, correspondendo ao ambiente validado. Instala `requirements-lock.txt`, verifica dependências com pip check, compila a sintaxe e executa todos os testes unittest. O cache guarda downloads do pip; não substitui a instalação.

Os testes usam bancos temporários e uma porta HTTP local temporária, sem depender de `data/igreja.sqlite3` ou de servidor permanente. O pipeline não publica escalas reais.

## Frontend

Runner Linux com Node 24. Não precisa de npm, pois os testes usam apenas recursos nativos do Node. Verifica a sintaxe dos dois scripts e executa os testes do calendário e do adaptador HTTP. Isso não substitui testes em navegador real.

## Operação

O workflow tem somente permissão de leitura, não usa segredos e não faz deploy. Execuções antigas da mesma referência são canceladas. Limites: 15 minutos para backend e 5 para frontend.

A primeira execução no GitHub ocorrerá depois do envio dos arquivos ao repositório. Regras de branch exigindo os dois checks para merge ainda não foram configuradas. Formatação, lint, análise de tipos e medição de cobertura continuam pendentes; os checks de sintaxe não substituem essas ferramentas.

## Reproduzir localmente

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q backend
.\.venv\Scripts\python.exe -m unittest discover -s backend -t . -v
node --check frontend/calendar.js
node --check frontend/api.js
node --test frontend/calendar.test.cjs frontend/api.test.cjs
```

O teste HTTP exige permissão para conexão local.

## Container Linux

O terceiro job valida Compose, constrói a imagem, executa a suíte Python dentro dela e roda scripts/container_smoke.py. O smoke test verifica API, geração sem tráfego, workers e manutenção da mesma escala no volume após reinício do container. Logs são mostrados e o serviço é encerrado mesmo em caso de falha. A execução desse job requer o envio dos arquivos ao GitHub.
