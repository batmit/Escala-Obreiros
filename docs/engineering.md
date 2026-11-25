# Práticas de engenharia

**Estado vigente:** adaptação Render + Neon concluída no código, ainda sem deploy remoto. Validação com 68 testes Python e 5 JavaScript; migração ensaiada preservando os dados. Veja a seção “Estado atual: preparação Render + Neon” neste arquivo e o [guia de migração](render-neon.md). As revisões intermediárias abaixo são históricas.

## Definição de pronto

- Critérios de aceite atendidos e revisão de código realizada.
- Testes relevantes e verificações estáticas aprovados.
- Regras obrigatórias verificadas antes da publicação.
- Documentação e migrações atualizadas quando aplicável.
- Falhas tratadas e funcionalidade validada em homologação.

## Validação

Testes unitários devem cobrir regras reais, incluindo limites de datas, indisponibilidade e conflitos. Testes de integração devem cobrir banco e solver. O fluxo completo deve demonstrar que uma falha preserva a última versão publicada.

Um verificador independente deve avaliar as alocações retornadas. Não exigir uma combinação específica de pessoas quando várias soluções forem válidas.

## Entrega e operação

Configurar formatação, lint, análise de tipos, testes e build no pipeline durante a implementação. Fixar dependências e versionar migrações. Documentar deploy e rollback.

Proteger operações administrativas; manter segredos fora do Git. Logs estruturados devem registrar identificador da execução, status e duração sem payloads ou dados pessoais. Implementar métricas, alertas, backups e teste de restauração antes de produção.

O pipeline de testes e sintaxe está configurado em .github/workflows/ci.yml. Formatação, lint e análise de tipos continuam pendentes.

## Revisão do incremento atual

Verificações executáveis:

```sh
python -m unittest discover -s backend -t . -v
node --test frontend/calendar.test.cjs
node --check frontend/calendar.js
git diff --check
```

A revisão passou com 56 testes Python e 5 testes JavaScript. Cobertura comportamental: contratos e validações de entrada, isolamento de coleções, persistência, duplicações e conflitos, limites do histórico, migração idempotente e rollback sem perda do legado, configuração de domingo, navegação, virada de data em Brasília e falha de carregamento da configuração.

Os testes JavaScript usam um DOM mínimo em memória. Não verificam layout, acessibilidade no navegador ou renderização real. Não foi medida uma porcentagem de cobertura. Testes aprovados não demonstram ausência de defeitos.

Baixo acoplamento: modelos e contratos não importam SQLite, frontend ou solver. A configuração pública sai do banco por exportação JSON. Há separação entre participação realizada e alocação planejada. Coleções recebidas nos modelos e atribuições recebidas pelo frontend não mantêm referências mutáveis do chamador.

Pendências: separar a carga específica da igreja do adaptador SQLite; extrair e versionar formalmente as migrações; configurar formatação, lint, análise de tipos e integração contínua; automatizar testes em navegador. O JavaScript ainda reúne relógio, carregamento e renderização em um módulo. Avaliar sua separação ao integrar a API. Há solver, seleção ponderada e validador independente das restrições obrigatórias implementadas; ainda não há publicação ou ambiente de homologação; seus critérios serão verificados quando implementados. A definição de pronto para produção ainda não foi atendida.


## Revisão após seleção ponderada

Foram adicionados seis testes de regressão: preferências desativadas e não flexibilizáveis, precedência da escala anterior explícita, exclusão de histórico antigo da penalidade, timeout após uma solução completa, JSON anterior inválido, rejeição independente de soluções corrompidas e doze semanas encadeadas. Os cenários estão agrupados em seis métodos de teste. Em cada transição das doze semanas, o teste confirmou seis pessoas repetidas, o mínimo possível com oito vagas e dez participantes.

O validador não importa OR-Tools. O gerador passa seus resultados por ele antes de devolvê-los. Falhas internas durante fixação de escolhas são diferenciadas de timeout. O orçamento de tempo ainda é um limite cooperativo de consultas ao solver, não um prazo rígido de processo.

Limitações da evidência: simulações usam sementes fixas e cenários pequenos; não demonstram desempenho sob concorrência. Os testes de probabilidades isolam situações com candidatos elegíveis e não garantem proporções marginais de 2:1 em escalas completas. Viabilidade e minimização de repetições condicionam as chances. Não foram executados testes em navegador real ou homologação.

### Próximas entregas, em ordem

1. Persistir propostas de escala e suas versões, separadas de participações realizadas; guardar semente, período e parâmetros de geração.
2. Publicar uma versão de forma transacional e idempotente; preservar a última escala válida se uma geração falhar.
3. Criar API de consulta por período e adaptador para o frontend, incluindo nomes e data de atualização.
4. Definir congelamento de alocações e executar geração agendada sem concorrência ou duplicação.
5. Configurar pipeline, formatação, lint e análise de tipos; separar carga inicial do adaptador SQLite e formalizar migrações versionadas.
6. Realizar testes de navegador, carga e recuperação; configurar autenticação das operações administrativas, logs, alertas, backup e hospedagem.

A arquitetura mantém contratos/modelos isolados de infraestrutura, mas cp_sat.py ainda reúne otimização, sondagens e coordenação do sorteio. Separar essas responsabilidades antes de acrescentar políticas complexas; evitar uma refatoração ampla sem necessidade. O JSON de configuração do frontend é uma exportação e pode ficar desatualizado até nova exportação. A situação atual é adequada para desenvolvimento local; os critérios de operação em produção continuam pendentes.

## Incremento de persistência

Implementadas versões de escala, publicação transacional e idempotência, sem alterar o histórico realizado. API local de consulta e integração do calendário verificadas por HTTP real e visualmente no navegador, com nomes provenientes do banco. Testes adicionais cobrem rollback da gravação, consulta entre semanas e respostas antigas no frontend. Os itens 1 a 3 da lista anterior têm uma primeira implementação local; aprovação de rascunhos, rollback operacional, agendamento, autenticação administrativa remota e hospedagem seguem pendentes.

## Agendamento semanal

Implementado no servidor, com fuso America/Sao_Paulo, verificação na inicialização, retomada após falhas, trava temporária no SQLite e publicação condicional para preservar semanas existentes. Seis testes do agendador e um de publicação condicional foram adicionados. A suíte completa passou com 41 testes Python. A operação contínua ainda depende do processo do servidor ligado; instalação como serviço e hospedagem são etapas futuras.

## Pipeline de integração contínua

Criado workflow GitHub Actions com jobs independentes de backend (Windows x64/Python 3.13) e frontend (Linux/Node 24). Instalação fixada, verificação de dependências, sintaxe e testes. Permissões somente de leitura e sem segredos ou deploy. A execução remota depende do envio dos arquivos ao GitHub; branch protection não foi alterada. Consulte ci.md.

## Backup e execução contínua

Backup online com retenção configurável, verificação de integridade e restauração em arquivo novo implementados. Seis testes cobrem cópia com conexão aberta/WAL, retenção, falhas, banco inválido, periodicidade e início/encerramento real dos workers sem tráfego HTTP. A suíte completa passou com 47 testes Python e 5 JavaScript. Um backup do banco local foi restaurado em data/restauracoes e comparado com o original (pessoas, escalas, alocações e participações). O servidor foi reiniciado e registrou o backup inicial.

A geração hospedada depende de processo contínuo, volume persistente e um serviço sem suspensão por inatividade. Foram adicionados HOST/PORT/DATABASE_PATH/BACKUP_DIR e /healthz, mas não foi realizado deploy. Cópia externa e supervisão no provedor continuam pendentes; ver backup-and-hosting.md.

## Preparação para hospedagem

Adicionado entrypoint de produção Waitress e aplicação WSGI compartilhada com a API local. Testes de produção verificam inicialização preservando dados, arquivos permitidos, métodos HTTP e dois ciclos reais de início/parada dos workers. Docker/Compose com volume e restart preparados; Blueprint Render com deploy automático desligado e disco persistente. CI recebeu validação Linux e smoke test de reinício/volume. Docker Engine local não estava ativo; a construção Linux e o deploy seguem pendentes. Consulte deployment.md.

## Modo gratuito por acesso

Adicionada factory WSGI sem workers e caso de uso síncrono que consulta a publicação vigente antes de chamar o gerador. A escala persistida controla a idempotência entre recargas; navegação não gera futuro. Seis testes adicionais cobrem primeiro acesso, repetição, virada semanal, preservação após nova factory, erros e ausência de threads. Backup oportunista mantém três cópias após 24h; falhas não bloqueiam uma escala já disponível. A suíte passou com 56 testes Python e 5 JavaScript. PythonAnywhere foi documentado como candidato gratuito; OR-Tools e uso de quota ainda precisam ser homologados na conta do provedor.
# Estado atual: preparação Render + Neon

Esta seção substitui os estados históricos abaixo. Foram implementados adaptadores PostgreSQL, migrações versionadas com checksum, carga inicial compartilhada, publicação transacional, reserva concorrente e geração por acesso. O runtime PostgreSQL não executa migrações nem seed no startup. A exportação/restauração verifica todos os registros e recusa destinos preenchidos.

A validação atual inclui 68 testes Python com PostgreSQL real local e 5 testes JavaScript. O ensaio de migração preservou 10 pessoas, 2 escalas e 16 alocações. O ensaio de container sem volume confirmou geração por acesso e preservação da mesma escala após reinício. O SQLite original não foi alterado.

CI tem quatro jobs; backup PostgreSQL cifrado tem workflow separado, desativado até configurar segredos e variável. Ainda dependem do ambiente remoto: criação dos serviços, permissões e segredos, importação definitiva, ativação/verificação dos backups e homologação. Formatação, lint, análise de tipos e testes automatizados de navegador continuam pendentes. Testes aprovados não equivalem a homologação em produção. Consulte [render-neon.md](render-neon.md).

