"""Expansão pura de cultos recorrentes para vagas de uma semana."""

from datetime import date, timedelta
from collections.abc import Iterable

from ..models import Culto, Funcao
from .contracts import Vaga


def criar_vagas_semanais(inicio_semana: date, cultos: Iterable[Culto]) -> tuple[Vaga, ...]:
    if type(inicio_semana) is not date or inicio_semana.weekday() != 0:
        raise ValueError('A semana deve começar em uma segunda-feira.')
    configuracao = tuple(cultos)
    if len({c.dia_semana for c in configuracao}) != len(configuracao):
        raise ValueError('Configuração duplicada de dia de culto.')
    vagas = []
    for culto in sorted(configuracao, key=lambda c: c.dia_semana):
        data = inicio_semana + timedelta(days=culto.dia_semana - 1)
        for funcao in sorted(culto.funcoes):
            vagas.append(Vaga(f'{data.isoformat()}-{funcao}', data, Funcao(funcao)))
    return tuple(vagas)
