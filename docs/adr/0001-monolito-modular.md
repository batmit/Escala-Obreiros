# ADR 0001 — Monólito modular para o MVP

Status: proposta para uma etapa futura; a implementação atual está limitada ao frontend.

## Contexto

O produto atende uma igreja de teste e publica escalas automaticamente em um calendário web. Não há necessidade inicial de cadastro ou de serviços distribuídos.

## Decisão

Separar o backend em domínio, aplicação, infraestrutura e interfaces. Manter regras específicas explícitas e versionadas. Usar CP-SAT como adaptador e PostgreSQL para escalas publicadas e histórico. Compartilhar os casos de uso entre a API e a execução agendada.

## Consequências

As regras podem ser testadas isoladamente dos frameworks. API e agendador precisam evoluir com versões compatíveis do esquema. A operação inicial permanece concentrada em poucos componentes; fila e serviços adicionais só serão introduzidos se medições justificarem.
