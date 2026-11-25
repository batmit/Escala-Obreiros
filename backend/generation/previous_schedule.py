"""Leitura do JSON de uma proposta anterior, sem dependência do solver."""

from datetime import date

from ..models import Funcao
from .contracts import Alocacao, EscalaAnterior, Vaga


def ler_escala_anterior(dados: dict) -> EscalaAnterior:
    try:
        if dados['status'] not in ('viavel', 'otima'):
            raise ValueError('A escala anterior precisa ter solução válida.')
        inicio = date.fromisoformat(dados['inicio_semana'])
        vagas, alocacoes = [], []
        for item in dados['alocacoes']:
            vagas.append(Vaga(item['vaga_id'], date.fromisoformat(item['data']), Funcao(item['funcao'])))
            alocacoes.append(Alocacao(item['vaga_id'], item['pessoa_id']))
        return EscalaAnterior(inicio, tuple(vagas), tuple(alocacoes))
    except (KeyError, TypeError, AttributeError) as erro:
        raise ValueError('Formato inválido de escala anterior.') from erro
