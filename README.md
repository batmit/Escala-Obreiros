# Escala de Obreiros

Calendário móvel com geração automática de escalas para a Igreja Cristã Maranata em Mariana.

## Arquitetura

```text
Navegador -> Render / Waitress -> API -> PostgreSQL / Neon
                                  |
                 Primeiro acesso da semana -> CP-SAT -> Validação -> Publicação
```

O gerador aplica as restrições obrigatórias, minimiza repetição da semana anterior e sorteia entre candidatos viáveis usando pesos de grupos e pessoas. Todos podem atuar em palavra e louvor. Escalas planejadas e participações realizadas são armazenadas separadamente.

A hospedagem escolhida é Render gratuito com Neon. Os adaptadores PostgreSQL, migrações versionadas, migração de dados e backups portáveis estão preparados. SQLite permanece compatível para desenvolvimento e como origem dos dados atuais.

## Migração e hospedagem

Siga [Render + Neon](docs/render-neon.md). O Blueprint usa plano gratuito sem disco, `DATABASE_URL` como segredo e `GENERATION_MODE=on-access`. A escala já publicada é preservada em acessos e reinícios. O banco atual não foi transferido para serviços remotos.

## Desenvolvimento local com SQLite

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m backend
.\.venv\Scripts\python.exe -m backend.server
```

Abra http://localhost:8000. Para o modo de produção local, use `python -m backend.production`. Quando `DATABASE_URL` estiver definida, os repositórios PostgreSQL serão utilizados e a inicialização exige banco previamente migrado. Em Render, URL ausente ou inválida não permite fallback para SQLite efêmero.

## Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -t . -v
node --test frontend/calendar.test.cjs frontend/api.test.cjs
```

A integração PostgreSQL exige `TEST_DATABASE_URL` apontando para um servidor local isolado. Não usar uma conexão Neon/produção nessa variável. O CI possui jobs Windows, frontend, container Linux e PostgreSQL real.

## Documentação

- [Regras da igreja](docs/adr/Lógicas%20de%20Negócio%20-%20Igreja.txt)
- [Arquitetura](docs/architecture.md)
- [Geração e contratos](backend/generation/README.md)
- [Dados e persistência](backend/README.md)
- [Calendário](frontend/README.md)
- [Engenharia e testes](docs/engineering.md)
- [CI](docs/ci.md)
- [Render + Neon: migração, permissões e backups](docs/render-neon.md)

As instruções antigas de Docker/SQLite e PythonAnywhere continuam como alternativas locais/históricas. O plano pago com disco não é mais a configuração principal de Render.
