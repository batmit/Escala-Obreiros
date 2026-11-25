import unittest
from datetime import date

from ..models import Culto, Funcao, Participacao, Pessoa, Regras
from .contracts import Alocacao, PedidoGeracao, ResultadoGeracao, StatusGeracao, Vaga


class ContratosTests(unittest.TestCase):
    def pedido(self, **changes):
        dados = dict(
            inicio_semana=date(2026, 11, 23),
            pessoas=(Pessoa('daniel', 'Daniel', 1, 'obreiro', 1),),
            cultos=(Culto(1, ('palavra',), ((1, 2), (2, 1))),),
            vagas=(Vaga('segunda-palavra', date(2026, 11, 23), Funcao.PALAVRA),),
            regras=Regras(1, True, True),
        )
        dados.update(changes)
        return PedidoGeracao(**dados)

    def test_contrato_aceita_historico_de_louvor(self):
        pedido = self.pedido(historico=[Participacao(date(2026, 11, 17), 'daniel', Funcao.LOUVOR)])
        self.assertIsInstance(pedido.historico, tuple)
        resultado = ResultadoGeracao(StatusGeracao.VIAVEL, [Alocacao('segunda-palavra', 'daniel')])
        self.assertEqual(resultado.alocacoes[0].pessoa_id, 'daniel')

    def test_rejeita_semana_vaga_e_historico_inconsistentes(self):
        casos = [
            dict(inicio_semana=date(2026, 11, 24)),
            dict(vagas=(Vaga('fora', date(2026, 11, 30), Funcao.PALAVRA),)),
            dict(vagas=(Vaga('funcao', date(2026, 11, 23), Funcao.LOUVOR),)),
            dict(historico=(Participacao(date(2026, 11, 23), 'daniel', Funcao.PALAVRA),)),
            dict(historico=(Participacao(date(2026, 11, 17), 'ausente', Funcao.PALAVRA),)),
            dict(limite_segundos=float('nan')),
            dict(limite_segundos=0),
        ]
        for caso in casos:
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                self.pedido(**caso)

    def test_resultado_sem_solucao_nao_aceita_alocacoes(self):
        with self.assertRaises(ValueError):
            ResultadoGeracao(StatusGeracao.INVIAVEL, (Alocacao('vaga', 'daniel'),))

    def test_rejeita_ids_repetidos_e_historico_conflitante(self):
        pessoa = Pessoa('daniel', 'Daniel', 1, 'obreiro', 1)
        vaga = Vaga('segunda-palavra', date(2026, 11, 23), Funcao.PALAVRA)
        participacao = Participacao(date(2026, 11, 17), 'daniel', Funcao.PALAVRA)
        for caso in (dict(pessoas=(pessoa, pessoa)), dict(vagas=(vaga, vaga)), dict(historico=(participacao, participacao)), dict(limite_segundos='10'), dict(limite_segundos=True)):
            with self.subTest(caso=caso), self.assertRaises(ValueError):
                self.pedido(**caso)
        with self.assertRaises(ValueError):
            ResultadoGeracao(StatusGeracao.VIAVEL, (Alocacao('vaga', 'daniel'), Alocacao('vaga', 'hugo')))


if __name__ == '__main__':
    unittest.main()
