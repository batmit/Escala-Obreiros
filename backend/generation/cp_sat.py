"""Adaptador OR-Tools para viabilidade das restrições obrigatórias."""

from datetime import timedelta
from random import Random
from time import monotonic

from ortools.sat.python import cp_model

from .weighted_selection import escolher_pessoa

from .contracts import Alocacao, PedidoGeracao, ResultadoGeracao, StatusGeracao
from .validator import validar_resultado


def gerar_escala(pedido: PedidoGeracao) -> ResultadoGeracao:
    resultado = _gerar_escala(pedido)
    erros = validar_resultado(pedido, resultado)
    if erros:
        raise RuntimeError('O gerador produziu uma escala inválida: ' + '; '.join(erros))
    return resultado


def _gerar_escala(pedido: PedidoGeracao) -> ResultadoGeracao:
    prazo = monotonic() + pedido.limite_segundos
    rng = Random(pedido.semente)
    modelo = cp_model.CpModel()
    pessoas = sorted(pedido.pessoas, key=lambda p: p.id)
    vagas = sorted(pedido.vagas, key=lambda v: (v.data, v.funcao.value, v.id))
    cultos = {c.dia_semana: c for c in pedido.cultos}
    escolhas = {}
    for indice_vaga, vaga in enumerate(vagas):
        grupos_permitidos = {grupo for grupo, _ in cultos[vaga.data.isoweekday()].pesos_grupos}
        for indice_pessoa, pessoa in enumerate(pessoas):
            variavel = modelo.new_bool_var(f'x_{indice_pessoa}_{indice_vaga}')
            escolhas[pessoa.id, vaga.id] = variavel
            if pessoa.grupo not in grupos_permitidos:
                modelo.add(variavel == 0)
        modelo.add_exactly_one(escolhas[p.id, vaga.id] for p in pessoas)

    for pessoa in pessoas:
        modelo.add(sum(escolhas[pessoa.id, v.id] for v in vagas) <= pedido.regras.maximo_participacoes_semana)
        # Mantém funções distintas por pessoa/data mesmo se o limite semanal mudar.
        for data in {v.data for v in vagas}:
            modelo.add_at_most_one(escolhas[pessoa.id, v.id] for v in vagas if v.data == data)

    if pedido.escala_anterior is not None:
        anteriores = {a.pessoa_id for a in pedido.escala_anterior.alocacoes}
    else:
        inicio_anterior = pedido.inicio_semana - timedelta(days=7)
        anteriores = {p.pessoa_id for p in pedido.historico if inicio_anterior <= p.data < pedido.inicio_semana}
    repetidos = []
    for pessoa in pessoas:
        if pessoa.id in anteriores:
            usado = modelo.new_bool_var(f'repetido_{pessoa.id}')
            modelo.add_max_equality(usado, [escolhas[pessoa.id, v.id] for v in vagas] or [0])
            repetidos.append(usado)
    evitar = pedido.regras.evitar_semanas_consecutivas
    if evitar and not pedido.regras.permitir_flexibilizar_consecutivas:
        modelo.add(sum(repetidos) == 0)
    elif evitar:
        modelo.minimize(sum(repetidos))

    avisos = []
    erro = modelo.validate()
    if erro:
        return ResultadoGeracao(StatusGeracao.MODELO_INVALIDO, avisos=(erro,))

    def resolver():
        restante = prazo - monotonic()
        if restante <= 0:
            return cp_model.UNKNOWN, None
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = restante
        solver.parameters.random_seed = pedido.semente
        solver.parameters.num_search_workers = 1
        return solver.solve(modelo), solver

    def extrair(solver):
        return tuple(Alocacao(v.id, p.id) for v in vagas for p in pessoas if solver.boolean_value(escolhas[p.id, v.id]))

    status, solver = resolver()
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        traducao = {cp_model.INFEASIBLE: StatusGeracao.INVIAVEL, cp_model.UNKNOWN: StatusGeracao.SEM_SOLUCAO, cp_model.MODEL_INVALID: StatusGeracao.MODELO_INVALIDO}
        return ResultadoGeracao(traducao[status])
    melhor = extrair(solver)
    if evitar and pedido.regras.permitir_flexibilizar_consecutivas:
        limite_repeticoes = sum(solver.boolean_value(v) for v in repetidos)
        modelo.add(sum(repetidos) <= limite_repeticoes)
        if status != cp_model.OPTIMAL:
            avisos.append('Não foi comprovado o mínimo de repetições dentro do tempo disponível.')
    modelo.clear_objective()

    # Sorteia apenas entre pessoas cuja escolha ainda permite completar a escala.
    # A ordem aleatória evita privilegiar sistematicamente a primeira função/dia.
    ordem = list(vagas)
    rng.shuffle(ordem)
    for vaga in ordem:
        viaveis = []
        for pessoa in pessoas:
            modelo.clear_assumptions()
            modelo.add_assumption(escolhas[pessoa.id, vaga.id])
            teste, _ = resolver()
            modelo.clear_assumptions()
            if teste in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                viaveis.append(pessoa)
            elif teste == cp_model.MODEL_INVALID:
                raise RuntimeError('Modelo inválido durante a seleção ponderada.')
            elif teste != cp_model.INFEASIBLE:
                avisos.append('Tempo insuficiente para concluir o sorteio ponderado; devolvida a última solução válida.')
                return finalizar(melhor, anteriores, evitar, avisos)
        selecionada = escolher_pessoa(viaveis, dict(cultos[vaga.data.isoweekday()].pesos_grupos), rng)
        modelo.add(escolhas[selecionada.id, vaga.id] == 1)
        status, solver = resolver()
        if status in (cp_model.MODEL_INVALID, cp_model.INFEASIBLE):
            raise RuntimeError('A fixação de um candidato comprovadamente viável falhou.')
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            avisos.append('Tempo insuficiente para concluir o sorteio ponderado; devolvida a última solução válida.')
            return finalizar(melhor, anteriores, evitar, avisos)
        melhor = extrair(solver)
    return finalizar(melhor, anteriores, evitar, avisos)


def finalizar(alocacoes, anteriores, evitar, avisos):
    quantidade = len({a.pessoa_id for a in alocacoes} & anteriores)
    if evitar and quantidade:
        avisos.append(f'Preferência flexibilizada: {quantidade} pessoa(s) repetida(s) da semana anterior.')
    return ResultadoGeracao(StatusGeracao.VIAVEL, alocacoes, tuple(avisos))
