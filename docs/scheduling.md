# Renovação automática semanal

O servidor inicia `AgendadorSemanal` em uma thread separada. O calendário não dispara a geração; ela funciona mesmo sem nenhuma página aberta, enquanto o processo do servidor estiver ativo.

A escala vigente corresponde à semana de segunda-feira até domingo. A transição é disparada na segunda-feira às 00:00 em `America/Sao_Paulo`. O cálculo usa fuso IANA, independentemente do fuso do computador. A geração leva alguns segundos; o horário define o disparo, não garante publicação instantânea.

## Fluxo

1. Verificar imediatamente a semana vigente ao iniciar o servidor.
2. Preservar a semana se já houver uma escala publicada.
3. Adquirir uma trava no banco para gerar a semana ausente.
4. Carregar a escala publicada da semana imediatamente anterior e passá-la como `PedidoGeracao.escala_anterior`.
5. Carregar pessoas, cultos e regras; gerar e validar com limite de solver de 10 segundos.
6. Salvar/publicar transacionalmente somente se a semana continuar ausente.
7. Liberar a trava e aguardar a próxima verificação.

O relógio é verificado a cada minuto, com espera reduzida quando a virada está a menos de um minuto. Isso também recupera suspensão e ajustes de relógio. Falhas são registradas em log e tentadas novamente em até 60 segundos. A espera é interrompida no encerramento do servidor.

Uma trava com proprietário e prazo de 120 segundos coordena processos que usam o mesmo banco. Se o processo morrer, outro poderá assumir após a expiração. A publicação condicional também impede substituir uma semana já publicada, inclusive se duas gerações terminarem. A trava é uma concessão temporária: pausas de processo superiores ao prazo podem permitir cálculo duplicado, mas não substituição automática da publicação existente.

Não se geram escalas retroativas para semanas em que o servidor permaneceu desligado. Na retomada, gera-se somente a semana atual; se faltar a semana imediatamente anterior, usa-se o histórico realizado disponível como alternativa. Sem escala anterior ou histórico, não há informação para penalizar repetição. Escalas futuras já publicadas são preservadas e passam a vigorar na sua semana.

## Executar

```powershell
.\.venv\Scripts\python.exe -m backend
.\.venv\Scripts\python.exe -m backend.server
```

O agendamento vem ativado por padrão. Para consulta sem geração automática, use `--sem-agendamento`. O computador e o processo precisam permanecer ligados na virada; ao reiniciar, a verificação inicial recupera a semana faltante. A instalação como serviço do sistema ou hospedagem contínua ainda não foi implementada.

O frontend recebe os dados novos na próxima consulta, em até um minuto enquanto visível. A navegação e o retorno à aba também atualizam a consulta. Como a geração ocorre no início da vigência, dias da próxima semana podem aparecer como “A definir” antes da virada, salvo se essa semana já tiver sido gerada manualmente.
