"""Sorteio em dois níveis, independente do solver e da persistência."""

from random import Random
from collections.abc import Sequence

from ..models import Pessoa


def escolher_pessoa(candidatos: Sequence[Pessoa], pesos_grupos: dict[int, int], rng: Random) -> Pessoa:
    if not candidatos:
        raise ValueError('Não existem candidatos viáveis.')
    grupos = sorted({p.grupo for p in candidatos})
    grupo = rng.choices(grupos, weights=[pesos_grupos[g] for g in grupos], k=1)[0]
    pessoas = sorted((p for p in candidatos if p.grupo == grupo), key=lambda p: p.id)
    return rng.choices(pessoas, weights=[p.peso for p in pessoas], k=1)[0]
