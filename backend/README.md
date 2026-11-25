# Dados da igreja

O armazenamento agora suporta PostgreSQL via `DATABASE_URL` e SQLite local. Para hospedagem e migrações explícitas no Neon, use [render-neon.md](../docs/render-neon.md). Inicialização automática de schema no startup é exclusiva do modo SQLite.

## Histórico unificado e contratos de geração

O armazenamento atual é `participacoes`: data, pessoa e função (`palavra` ou `louvor`). `Participacao` representa um fato realizado; `Alocacao` representa um planejamento futuro. A função aceita uma pessoa por data e a mesma pessoa não pode ocupar duas funções na mesma data. Restrições semanais serão aplicadas pelo gerador, não pelo registro de fatos históricos.

Use `registrar_participacao` e `listar_participacoes_ultimas_duas_semanas`. Os métodos anteriores de pregação continuam funcionando e filtram apenas palavra. A janela permanece como as duas semanas completas anteriores à semana da referência.

`python -m backend` migra automaticamente a tabela antiga `pregacoes`, copiando os registros como palavra e removendo a tabela legada após a cópia, em transação. Conflitos preservam o legado e interrompem a migração. Não há escrita dupla nem criação de histórico fictício.

As estruturas de geração estão em [generation/README.md](generation/README.md). O solver de restrições obrigatórias está implementado; instale requirements-lock.txt no ambiente virtual antes dos testes. Execute todos os testes com:

```sh
python -m unittest discover -s backend -t . -v
```

## Cultos e histórico de pregações

Domingo agora é um culto somente à noite, com palavra e louvor. `periodos_culto` armazena o período; os demais dias permanecem sem horário informado. `python -m backend --exportar-cultos frontend/cultos.json` atualiza o banco existente de forma aditiva e exporta a programação pública para o frontend.

A função palavra em `participacoes` armazena data e ID da pessoa que efetivamente pregou, com chave estrangeira e um registro por data. A consulta considera as duas semanas completas anteriores à semana de referência (segunda a domingo); não exclui registros antigos. O histórico inicia vazio e não contém pregações fictícias. Essa consulta específica filtra palavra; a consulta unificada também retorna louvor. O histórico não representa escala futura.

```python
from datetime import date
from backend.database import BancoIgreja
from backend.models import Pregacao

with BancoIgreja('data/igreja.sqlite3') as banco:
    banco.registrar_pregacao(Pregacao(date(2026, 11, 23), 'daniel'))
    historico = banco.listar_pregacoes_ultimas_duas_semanas(date(2026, 11, 30))
```

Repetir o mesmo registro é idempotente. Outro pregador na mesma data gera erro, sem substituição silenciosa. A operação verifica a existência do dia de culto e da pessoa, mas não aplica regras de geração a fatos históricos.

Persistência local em SQLite, usando somente a biblioteca padrão do Python 3.10 ou superior. Não gera escalas e não depende do frontend.

## Uso

Na raiz do projeto:

```sh
python -m backend
python -m unittest backend.test_database -v
```

O primeiro comando cria `data/igreja.sqlite3` e insere os dados do documento de negócio. Pode receber outro caminho como argumento. Reexecuções inserem apenas registros ausentes e não sobrescrevem alterações; editar o documento não sincroniza o banco automaticamente. Mudanças futuras de esquema precisarão de migrações explícitas.

`models.py` representa cada pessoa por uma dataclass imutável `Pessoa`, com ID estável, nome, grupo, cargo e peso. O peso é obtido do cargo por consulta, evitando duplicação no banco. `database.py` concentra o acesso ao SQLite e devolve estruturas sem expor conexões à interface.

```python
from backend.database import BancoIgreja

with BancoIgreja('data/igreja.sqlite3') as banco:
    pessoas = banco.listar_pessoas()
    cultos = banco.listar_cultos()
    regras = banco.obter_regras()
```

São armazenados dez participantes, pesos dos cargos, grupos, cinco dias de culto, funções necessárias, pesos relativos dos grupos e regras de participação. Terça, sábado e domingo têm uma vaga de louvor e uma de palavra. Segunda e quinta mantêm uma vaga de palavra, conforme a interface anterior. Domingo é um único culto à noite. A interface recebe a configuração por uma exportação JSON do banco.

As regras são armazenadas aqui e aplicadas pelo módulo generation, com verificação independente do resultado. Os pesos não são sorteados nem multiplicados aqui. Banco local e dados pessoais não devem ser publicados no Git; o arquivo foi incluído no `.gitignore`. SQLite é a escolha deste incremento local, substituindo temporariamente o planejamento de PostgreSQL para hospedagem futura.
# PostgreSQL e hospedagem

`storage.py` seleciona PostgreSQL por `DATABASE_URL` ou SQLite local. Os adaptadores mantêm os mesmos modelos e contratos. A carga inicial está em `seed.py`; o schema PostgreSQL é versionado em `migrations/`. Migração e restauração usam credencial administrativa separada do runtime. Consulte [o guia atual](../docs/render-neon.md).

