import unittest
from collections import Counter
from random import Random

from ..models import Pessoa
from .weighted_selection import escolher_pessoa


class PesosTests(unittest.TestCase):
    def test_probabilidade_grupo_independe_do_total_dos_pesos_individuais(self):
        pessoas = [Pessoa('a', 'A', 1, 'obreiro', 1), Pessoa('b', 'B', 2, 'diácono', 2), Pessoa('c', 'C', 2, 'pastor', 3)]
        rng = Random(42)
        contagem = Counter(escolher_pessoa(pessoas, {1: 2, 2: 1}, rng).id for _ in range(20000))
        self.assertTrue(0.64 < contagem['a'] / 20000 < 0.69)
        self.assertTrue(1.35 < contagem['c'] / contagem['b'] < 1.65)

    def test_peso_maior_aumenta_chance_no_mesmo_grupo(self):
        pessoas = [Pessoa('a', 'A', 2, 'obreiro', 1), Pessoa('b', 'B', 2, 'pastor', 3)]
        rng = Random(123)
        contagem = Counter(escolher_pessoa(pessoas, {2: 1}, rng).id for _ in range(10000))
        self.assertTrue(0.72 < contagem['b'] / 10000 < 0.78)
