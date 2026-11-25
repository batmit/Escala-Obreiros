"""Dados de entrada e saída para o futuro mecanismo de geração."""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from math import isfinite

from ..models import Culto, Funcao, Participacao, Pessoa, Regras, validar_identificador


@dataclass(frozen=True, slots=True)
class Vaga:
    id: str
    data: date
    funcao: Funcao

    def __post_init__(self):
        validar_identificador(self.id)
        if type(self.data) is not date:
            raise ValueError('Vaga exige ID e uma data válida.')
        object.__setattr__(self, 'funcao', Funcao(self.funcao))


@dataclass(frozen=True, slots=True)
class Alocacao:
    vaga_id: str
    pessoa_id: str

    def __post_init__(self):
        validar_identificador(self.vaga_id)
        validar_identificador(self.pessoa_id)


@dataclass(frozen=True, slots=True)
class EscalaAnterior:
    inicio_semana: date
    vagas: tuple[Vaga, ...]
    alocacoes: tuple[Alocacao, ...]

    def __post_init__(self):
        if type(self.inicio_semana) is not date or self.inicio_semana.weekday() != 0:
            raise ValueError('Escala anterior deve começar em segunda-feira.')
        object.__setattr__(self, 'vagas', tuple(self.vagas))
        object.__setattr__(self, 'alocacoes', tuple(self.alocacoes))
        ids = {v.id for v in self.vagas}
        if len(ids) != len(self.vagas) or len({a.vaga_id for a in self.alocacoes}) != len(self.alocacoes):
            raise ValueError('Escala anterior contém vagas duplicadas.')
        if {a.vaga_id for a in self.alocacoes} != ids:
            raise ValueError('Alocações da escala anterior devem cobrir suas vagas.')
        if any(not 0 <= (v.data - self.inicio_semana).days < 7 for v in self.vagas):
            raise ValueError('Vaga fora da semana anterior.')
        if len({(v.data, v.funcao) for v in self.vagas}) != len(self.vagas):
            raise ValueError('Escala anterior contém função duplicada na mesma data.')
        por_id = {v.id: v for v in self.vagas}
        if len({(por_id[a.vaga_id].data, a.pessoa_id) for a in self.alocacoes}) != len(self.alocacoes):
            raise ValueError('Uma pessoa não pode ocupar duas funções na mesma data anterior.')


@dataclass(frozen=True, slots=True)
class PedidoGeracao:
    inicio_semana: date
    pessoas: tuple[Pessoa, ...]
    cultos: tuple[Culto, ...]
    vagas: tuple[Vaga, ...]
    regras: Regras
    historico: tuple[Participacao, ...] = ()
    semente: int = 0
    limite_segundos: float = 10.0
    escala_anterior: EscalaAnterior | None = None

    def __post_init__(self):
        if type(self.inicio_semana) is not date or self.inicio_semana.weekday() != 0:
            raise ValueError('A semana deve começar em uma segunda-feira.')
        if type(self.semente) is not int or not 0 <= self.semente <= 2**31 - 1:
            raise ValueError('A semente deve ser inteira entre 0 e 2147483647.')
        if type(self.limite_segundos) not in (int, float) or not isfinite(self.limite_segundos) or self.limite_segundos <= 0:
            raise ValueError('O limite de execução deve ser positivo e finito.')
        for campo in ('pessoas', 'cultos', 'vagas', 'historico'):
            object.__setattr__(self, campo, tuple(getattr(self, campo)))
        ids = {p.id for p in self.pessoas}
        if self.escala_anterior is not None:
            if self.escala_anterior.inicio_semana != self.inicio_semana - timedelta(days=7):
                raise ValueError('Escala anterior deve ser da semana imediatamente anterior.')
            if any(a.pessoa_id not in ids for a in self.escala_anterior.alocacoes):
                raise ValueError('Escala anterior contém pessoa desconhecida.')
        if len(ids) != len(self.pessoas) or len({v.id for v in self.vagas}) != len(self.vagas):
            raise ValueError('IDs de pessoas e vagas devem ser únicos.')
        if len({c.dia_semana for c in self.cultos}) != len(self.cultos):
            raise ValueError('Configuração duplicada de dia de culto.')
        por_dia = {c.dia_semana: c for c in self.cultos}
        ocorrencias = set()
        for vaga in self.vagas:
            if not 0 <= (vaga.data - self.inicio_semana).days < 7:
                raise ValueError('Vaga fora da semana solicitada.')
            culto = por_dia.get(vaga.data.isoweekday())
            if culto is None or vaga.funcao.value not in culto.funcoes:
                raise ValueError('Vaga sem função de culto configurada.')
            chave = (vaga.data, vaga.funcao)
            if chave in ocorrencias:
                raise ValueError('Função duplicada na mesma data.')
            ocorrencias.add(chave)
        esperadas = {(c.dia_semana, Funcao(f)) for c in self.cultos for f in c.funcoes}
        recebidas = {(v.data.isoweekday(), v.funcao) for v in self.vagas}
        if recebidas != esperadas:
            raise ValueError('As vagas devem cobrir todas as funções dos cultos da semana.')
        chaves_historico = set()
        pessoas_por_data = set()
        for participacao in self.historico:
            if participacao.pessoa_id not in ids or participacao.data >= self.inicio_semana:
                raise ValueError('Histórico exige pessoa conhecida e data anterior à semana.')
            chave = (participacao.data, participacao.funcao)
            pessoa_data = (participacao.data, participacao.pessoa_id)
            if chave in chaves_historico or pessoa_data in pessoas_por_data:
                raise ValueError('Histórico contém participações duplicadas ou conflitantes.')
            chaves_historico.add(chave)
            pessoas_por_data.add(pessoa_data)


class StatusGeracao(str, Enum):
    OTIMA = 'otima'
    VIAVEL = 'viavel'
    INVIAVEL = 'inviavel'
    SEM_SOLUCAO = 'sem_solucao'  # Não implica inviabilidade comprovada.
    MODELO_INVALIDO = 'modelo_invalido'


@dataclass(frozen=True, slots=True)
class ResultadoGeracao:
    status: StatusGeracao
    alocacoes: tuple[Alocacao, ...] = ()
    avisos: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'status', StatusGeracao(self.status))
        object.__setattr__(self, 'alocacoes', tuple(self.alocacoes))
        object.__setattr__(self, 'avisos', tuple(self.avisos))
        if self.alocacoes and self.status not in (StatusGeracao.OTIMA, StatusGeracao.VIAVEL):
            raise ValueError('Resultado sem solução não pode conter alocações.')
        if len({a.vaga_id for a in self.alocacoes}) != len(self.alocacoes):
            raise ValueError('Uma vaga não pode ter duas alocações.')
