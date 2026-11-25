import unittest
from datetime import date

from .models import Culto, Participacao, Pessoa, Regras


class ModelosTests(unittest.TestCase):
    def test_culto_isola_colecoes_recebidas(self):
        funcoes, pesos = ['palavra'], [[1, 2], [2, 1]]
        culto = Culto(1, funcoes, pesos)
        funcoes.append('louvor')
        pesos[0][1] = 999
        self.assertEqual(culto.funcoes, ('palavra',))
        self.assertEqual(culto.pesos_grupos, ((1, 2), (2, 1)))

    def test_rejeita_valores_invalidos(self):
        casos = [
            lambda: Pessoa('', 'Daniel', 1, 'obreiro', 1),
            lambda: Pessoa('daniel', 'Daniel', 3, 'obreiro', 1),
            lambda: Pessoa('daniel', 'Daniel', 1, 'obreiro', 0),
            lambda: Culto(0, ('palavra',), ((1, 1),)),
            lambda: Culto(1, ('palavra', 'palavra'), ((1, 1),)),
            lambda: Culto(1, ('palavra',), ((1, 0),)),
            lambda: Culto(1, ('palavra',), ((1, 1), (1, 2))),
            lambda: Regras(0, True, True),
            lambda: Regras(1, 1, True),
            lambda: Participacao(date(2026, 11, 23), None, 'palavra'),
        ]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                caso()
