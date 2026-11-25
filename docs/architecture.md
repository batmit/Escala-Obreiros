# Arquitetura atual

O MVP atende uma igreja de teste, sem seção de cadastro. A hospedagem escolhida usa Render gratuito, PostgreSQL no Neon e geração por acesso. SQLite permanece para desenvolvimento e origem da migração. Consulte [o procedimento atual](render-neon.md).

```text
Calendário web -> Waitress / WSGI -> API -> PostgreSQL (Neon)
                                     |
                                     +-> Semana ausente -> CP-SAT -> Validador -> Publicação
GitHub Actions -> Exportação consistente -> GPG -> Backup cifrado
```

## Componentes e dependências

- `models.py` e `generation/contracts.py`: estruturas sem acesso a rede, banco ou solver.
- `generation/slots.py`: expansão dos cultos recorrentes para oito vagas datadas.
- `generation/weighted_selection.py`: sorteio em dois níveis, grupo e pessoa.
- `generation/cp_sat.py`: restrições obrigatórias, minimização de repetição e sondagem de candidatos viáveis.
- `generation/validator.py`: verificação independente do resultado.
- `database.py`: configuração e histórico realizado.
- `schedule_repository.py`: versões e publicação transacional das escalas planejadas.
- `scheduler.py`: manutenção da semana vigente, sem depender de requisições.
- `backup.py`: cópia consistente, retenção e restauração para banco novo.
- `webapp.py`: API compartilhada e aplicação WSGI; no modo por acesso, consulta e gera somente a semana vigente ausente.
- `production.py`: composição dos workers e servidor Waitress, com tratamento de sinais.
- `server.py`: servidor de desenvolvimento usando a mesma API de consulta.
- `frontend/api.js`: adaptador HTTP; `calendar.js`: relógio, navegação e renderização.

## Operação

A renovação ocorre na segunda-feira às 00h de America/Sao_Paulo. A escala anterior é passada ao algoritmo; semanas já publicadas são preservadas. Reiniciar verifica a semana atual e recupera a geração ausente. Não se alteram participações realizadas ao publicar uma escala.

A publicação é transacional, com uma versão ativa por semana. A trava temporária coordena gerações usando o mesmo arquivo SQLite. A publicação condicional impede substituição automática de uma semana existente. Não há alta disponibilidade ou replicação do banco neste MVP.

## Hospedagem preparada

Docker com usuário sem privilégios e dados em `/var/data`; Compose com volume e política de reinício; Blueprint Render para uma instância contínua com disco persistente e healthcheck. A configuração está no repositório local, não foi provisionada. Consulte [deploy e homologação](deployment.md).

O banco não é incluído na imagem. O primeiro início em um volume novo cria dados iniciais; transferência de dados atuais exige backup/restauração explícitos. Dados, versões e backups só sobrevivem se o volume for preservado.

## Pendências

Executar build Linux e smoke test do container, homologar no provedor, configurar cópia externa de backups, alertas e regras de branch. As migrações ainda precisam ser formalmente versionadas. Formatação, lint e análise de tipos continuam pendentes. Uma migração para PostgreSQL será avaliada apenas se houver necessidade de múltiplas instâncias ou maior disponibilidade.
