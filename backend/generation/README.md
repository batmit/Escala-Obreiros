# Geração semanal

Contratos e expansão de vagas não dependem de SQLite, frontend ou OR-Tools. `cp_sat.py` é o adaptador do solver; `__main__.py` conecta a leitura do banco ao gerador sem gravar resultados.

## Execução no Windows

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m backend
.\.venv\Scripts\python.exe -m backend.generation 2026-11-30 --semente 42
.\.venv\Scripts\python.exe -m unittest discover -s backend -t . -v
```

O ambiente validado é Python 3.13 no Windows x64. `requirements.txt` fixa o OR-Tools; `requirements-lock.txt` inclui dependências transitivas.

## Contratos

- `Vaga`: ID estável, data concreta e função.
- `Alocacao`: vínculo planejado entre vaga e pessoa, distinto da participação realizada.
- `PedidoGeracao`: segunda-feira inicial, pessoas, cultos, vagas, regras, histórico, semente e limite de execução.
- `ResultadoGeracao`: status, alocações e avisos.

`criar_vagas_semanais` transforma os cultos configurados em vagas datadas; a configuração atual produz oito. O pedido valida cobertura exata das funções, datas, IDs únicos e referências do histórico.

## Restrições implementadas

Exatamente uma pessoa por vaga; limite de participações por semana (atualmente uma); apenas grupos permitidos pelo culto; uma pessoa não ocupa duas funções na mesma data. Domingo é restrito ao grupo 2 conforme a configuração. Todos podem atuar em palavra e louvor.

O primeiro objetivo é minimizar o número de pessoas da semana anterior. Depois o sorteio ocorre entre escolhas que preservam o melhor limite encontrado. A solução é exposta como `viavel`: não representa uma escala globalmente ótima em termos de probabilidades. Inviabilidade comprovada, ausência de solução e modelo inválido são estados distintos.

Cada vaga é sorteada em duas etapas: grupo conforme seus pesos no culto, depois pessoa proporcionalmente ao peso individual. Os mesmos pesos individuais valem para palavra e louvor. Antes do sorteio, o CP-SAT verifica todos os candidatos para preservar a conclusão da escala. A ordem das vagas também é embaralhada pela semente. As probabilidades são condicionadas às escolhas viáveis e ao limite de repetições; a proporção final não é uma cota garantida.

O limite de tempo é compartilhado por todas as consultas ao solver. Se o tempo acabar depois de uma solução completa ter sido encontrada, ela é devolvida com aviso de que o sorteio não foi concluído. Se a minimização não tiver sido comprovada, isso também é informado. A semente usa RNG local e um worker do solver; testes confirmam reprodução no mesmo ambiente, sem garantia entre versões ou máquinas.

Por padrão o comando imprime JSON sem publicar; --salvar-banco salva e publica em uma transação, sem alterar participações realizadas. O validador independente verifica cobertura, referências, grupos, limites semanais e funções por data antes de devolver qualquer resultado. A persistência e a consulta pelo calendário estão implementadas; consulte docs/persistence.md.

## Receber a escala anterior

```powershell
.\.venv\Scripts\python.exe -m backend.generation 2026-11-30 --semente 42 --saida data/escala-2026-11-30.json
.\.venv\Scripts\python.exe -m backend.generation 2026-12-07 --semente 42 --escala-anterior data/escala-2026-11-30.json --saida data/escala-2026-12-07.json
```

`--escala-anterior` recebe o JSON de uma geração viável, com `inicio_semana` e alocações datadas, obrigatoriamente da semana imediatamente anterior. No Python, use `PedidoGeracao.escala_anterior` com `EscalaAnterior(inicio_semana, vagas, alocacoes)`. Ela tem prioridade sobre o histórico do banco. Sem o parâmetro, o gerador usa apenas participações do histórico na semana imediatamente anterior; registros mais antigos não causam penalidade. Uma escala anterior vazia explicitamente informada desativa esse fallback.

Repetição significa a mesma pessoa em qualquer função, mesmo que troque de palavra para louvor. A preferência é flexibilizável na configuração da igreja, não uma proibição. Se a opção de flexibilização for desativada e a preferência estiver ativa, a ausência de repetições passa a ser obrigatória. Se a preferência estiver desativada, pesos continuam valendo sem minimizar repetições.

Os arquivos gerados são propostas locais; a publicação no banco ocorre somente com --salvar-banco. Os exemplos ficam em `data/`, ignorado pelo Git.
