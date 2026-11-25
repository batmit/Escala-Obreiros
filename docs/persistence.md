# Persistência e calendário integrado

## Execução local

```powershell
.\.venv\Scripts\python.exe -m backend
.\.venv\Scripts\python.exe -m backend.generation 2026-11-23 --semente 42 --salvar-banco
.\.venv\Scripts\python.exe -m backend.generation 2026-11-30 --semente 43 --salvar-banco
.\.venv\Scripts\python.exe -m backend.server --porta 8000
```

Abra http://localhost:8000. Foram geradas duas semanas para cobrir a janela móvel de 24 a 30 de novembro de 2026. Para outros períodos, informe a segunda-feira correspondente. O servidor agora verifica automaticamente a semana vigente e a renova na virada semanal; veja scheduling.md.

## Armazenamento

`escalas` guarda ID, semana, versão, timestamp UTC, semente, configuração de entrada, avisos e assinatura. `alocacoes_escala` guarda vagas datadas, funções, referências às pessoas e uma cópia dos seus nomes para preservar a apresentação histórica.

O resultado é verificado pelo validador independente antes da persistência. Uma transação `BEGIN IMMEDIATE` engloba a versão, suas alocações e a troca da publicação. Falhas revertem a gravação e preservam a última versão publicada. Um índice único garante apenas uma publicação por semana.

Entrada e resultado idênticos reutilizam o registro sem duplicação ou republicação de versão antiga. Neste incremento, salvar também publica para exibição imediata. Ainda não há aprovação de rascunhos ou rollback pela interface. Nenhuma participação realizada é criada: `participacoes` permanece separada das escalas planejadas.

Com `--salvar-banco`, o gerador consulta automaticamente a versão publicada da semana anterior. O JSON explícito `--escala-anterior` tem precedência. Sem versão anterior, utiliza o histórico realizado.

## API e calendário

- `GET /api/escalas?inicio=2026-11-24&fim=2026-11-30`: consulta inclusiva de até 31 dias, somente versões publicadas, com nomes por função e última atualização.
- `GET /cultos.json`: lê a configuração pública diretamente do banco.
- `/`: serve o frontend na mesma origem.

`frontend/api.js` consulta a escala no carregamento inicial, na navegação, ao voltar à aba e a cada minuto enquanto visível. Respostas fora de ordem são descartadas. Erros preservam dados já exibidos com aviso; a navegação limpa as atribuições do período anterior.

O servidor é local, usa a biblioteca padrão e fica limitado a `127.0.0.1`. Não expõe operações remotas de geração ou escrita nem serve o arquivo do banco. Não deve ser exposto diretamente em produção. O servidor genérico `http.server` não fornece a API; use `backend.server`.

## Verificações

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend -t .
node --test frontend/calendar.test.cjs frontend/api.test.cjs
```

34 testes Python e 5 JavaScript aprovados, incluindo publicação, reabertura do banco, idempotência, rollback, consulta entre semanas, HTTP real e respostas fora de ordem. O teste HTTP requer acesso à conexão local.
