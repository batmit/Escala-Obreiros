"""Verificação das restrições obrigatórias sem consultar o solver."""

from collections import Counter
from datetime import timedelta

from .contracts import PedidoGeracao, ResultadoGeracao, StatusGeracao


def validar_resultado(pedido: PedidoGeracao, resultado: ResultadoGeracao) -> tuple[str, ...]:
    if resultado.status not in (StatusGeracao.VIAVEL, StatusGeracao.OTIMA):
        return ('Resultado sem solução contém alocações.',) if resultado.alocacoes else ()
    erros = []
    vagas = {v.id: v for v in pedido.vagas}
    pessoas = {p.id: p for p in pedido.pessoas}
    cultos = {c.dia_semana: c for c in pedido.cultos}
    if Counter(a.vaga_id for a in resultado.alocacoes) != Counter(vagas.keys()):
        erros.append('A cobertura das vagas não é exata.')
    totais, por_data = Counter(), set()
    for alocacao in resultado.alocacoes:
        vaga, pessoa = vagas.get(alocacao.vaga_id), pessoas.get(alocacao.pessoa_id)
        if vaga is None or pessoa is None:
            erros.append('Alocação referencia vaga ou pessoa desconhecida.')
            continue
        if pessoa.grupo not in dict(cultos[vaga.data.isoweekday()].pesos_grupos):
            erros.append('Pessoa de grupo não permitido no culto.')
        totais[pessoa.id] += 1
        chave = (vaga.data, pessoa.id)
        if chave in por_data:
            erros.append('Pessoa ocupa mais de uma função na mesma data.')
        por_data.add(chave)
    if any(total > pedido.regras.maximo_participacoes_semana for total in totais.values()):
        erros.append('Limite semanal de participações excedido.')
    if pedido.regras.evitar_semanas_consecutivas and not pedido.regras.permitir_flexibilizar_consecutivas:
        if pedido.escala_anterior is not None:
            anteriores = {a.pessoa_id for a in pedido.escala_anterior.alocacoes}
        else:
            anteriores = {p.pessoa_id for p in pedido.historico if pedido.inicio_semana - timedelta(days=7) <= p.data < pedido.inicio_semana}
        if anteriores & set(totais):
            erros.append('Repetição proibida pela configuração.')
    return tuple(erros)
