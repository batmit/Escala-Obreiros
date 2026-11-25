"""Estruturas de dados sem dependências de armazenamento."""

from dataclasses import dataclass
from datetime import date
from enum import Enum


class Funcao(str, Enum):
    PALAVRA = 'palavra'
    LOUVOR = 'louvor'


def validar_identificador(valor: str) -> None:
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError('Identificador deve ser um texto não vazio.')


@dataclass(frozen=True, slots=True)
class Participacao:
    """Participação efetivamente realizada, distinta de uma alocação planejada."""

    data: date
    pessoa_id: str
    funcao: Funcao

    def __post_init__(self):
        if type(self.data) is not date:
            raise ValueError('A data deve ser datetime.date.')
        validar_identificador(self.pessoa_id)
        object.__setattr__(self, 'funcao', Funcao(self.funcao))


@dataclass(frozen=True, slots=True)
class Pessoa:
    id: str
    nome: str
    grupo: int
    cargo: str
    peso: int

    def __post_init__(self):
        validar_identificador(self.id)
        validar_identificador(self.nome)
        validar_identificador(self.cargo)
        if type(self.grupo) is not int or self.grupo not in (1, 2):
            raise ValueError('Grupo deve ser 1 ou 2.')
        if type(self.peso) is not int or self.peso <= 0:
            raise ValueError('Peso deve ser inteiro positivo.')


@dataclass(frozen=True, slots=True)
class Culto:
    dia_semana: int  # ISO: segunda=1, domingo=7
    funcoes: tuple[str, ...]
    pesos_grupos: tuple[tuple[int, int], ...]
    periodo: str = 'não informado'

    def __post_init__(self):
        if type(self.dia_semana) is not int or not 1 <= self.dia_semana <= 7:
            raise ValueError('Dia da semana deve estar entre 1 e 7.')
        funcoes = tuple(Funcao(f).value for f in self.funcoes)
        pesos = tuple(tuple(par) for par in self.pesos_grupos)
        if not funcoes or len(set(funcoes)) != len(funcoes):
            raise ValueError('Culto exige funções únicas.')
        if not pesos or any(len(par) != 2 or type(par[0]) is not int or par[0] not in (1, 2) or type(par[1]) is not int or par[1] <= 0 for par in pesos):
            raise ValueError('Pesos exigem grupo válido e inteiro positivo.')
        if len({par[0] for par in pesos}) != len(pesos):
            raise ValueError('Grupo duplicado no culto.')
        if self.periodo not in ('manhã', 'tarde', 'noite', 'não informado'):
            raise ValueError('Período inválido.')
        object.__setattr__(self, 'funcoes', funcoes)
        object.__setattr__(self, 'pesos_grupos', pesos)


@dataclass(frozen=True, slots=True)
class Pregacao:
    data: date
    pessoa_id: str


@dataclass(frozen=True, slots=True)
class Regras:
    maximo_participacoes_semana: int
    evitar_semanas_consecutivas: bool
    permitir_flexibilizar_consecutivas: bool

    def __post_init__(self):
        if type(self.maximo_participacoes_semana) is not int or self.maximo_participacoes_semana <= 0:
            raise ValueError('Máximo semanal deve ser inteiro positivo.')
        if type(self.evitar_semanas_consecutivas) is not bool or type(self.permitir_flexibilizar_consecutivas) is not bool:
            raise ValueError('Preferências devem ser booleanas.')
