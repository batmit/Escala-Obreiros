import unittest
from dataclasses import replace
from datetime import date, timedelta
from unittest.mock import patch

from ..database import BancoIgreja
from ..models import Funcao, Participacao
from .contracts import Alocacao, EscalaAnterior, PedidoGeracao, ResultadoGeracao, StatusGeracao
from .cp_sat import gerar_escala
from .previous_schedule import ler_escala_anterior
from .slots import criar_vagas_semanais
from .validator import validar_resultado


class RegressoesTests(unittest.TestCase):
    def setUp(self):
        with BancoIgreja(':memory:') as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()
            cultos = tuple(banco.listar_cultos())
            self.pedido = PedidoGeracao(date(2026, 11, 23), tuple(banco.listar_pessoas()), cultos, criar_vagas_semanais(date(2026, 11, 23), cultos), banco.obter_regras())

    def historico(self):
        return tuple(Participacao(date(2026, 11, 16) + timedelta(days=i // 2), p.id, Funcao.PALAVRA if i % 2 else Funcao.LOUVOR) for i, p in enumerate(self.pedido.pessoas))

    def test_preferencia_desativada_e_proibicao_explicita(self):
        pedido = replace(self.pedido, historico=self.historico())
        sem_preferencia = replace(pedido, regras=replace(pedido.regras, evitar_semanas_consecutivas=False))
        resultado = gerar_escala(sem_preferencia)
        self.assertEqual(resultado.status, StatusGeracao.VIAVEL)
        self.assertFalse(resultado.avisos)
        sem_flexibilidade = replace(pedido, regras=replace(pedido.regras, permitir_flexibilizar_consecutivas=False))
        self.assertEqual(gerar_escala(sem_flexibilidade).status, StatusGeracao.INVIAVEL)

    def test_escala_anterior_explicita_prevalece_sobre_historico(self):
        vazio = EscalaAnterior(date(2026, 11, 16), (), ())
        resultado = gerar_escala(replace(self.pedido, historico=self.historico(), escala_anterior=vazio))
        self.assertFalse(resultado.avisos)
        antigo = tuple(replace(p, data=p.data - timedelta(days=7)) for p in self.historico())
        self.assertFalse(gerar_escala(replace(self.pedido, historico=antigo)).avisos)

    def test_timeout_apos_primeira_solucao_preserva_escala_valida(self):
        # Prazo suficiente no primeiro solve; esgotado antes dos testes de candidatos.
        with patch('backend.generation.cp_sat.monotonic', side_effect=[0, 0, 11]):
            resultado = gerar_escala(self.pedido)
        self.assertEqual(resultado.status, StatusGeracao.VIAVEL)
        self.assertFalse(validar_resultado(self.pedido, resultado))
        self.assertTrue(any('sorteio' in aviso for aviso in resultado.avisos))

    def test_validador_rejeita_ausencia_desconhecidos_repeticao_e_grupo_errado(self):
        real = gerar_escala(self.pedido)
        self.assertTrue(validar_resultado(self.pedido, replace(real, alocacoes=real.alocacoes[:-1])))
        self.assertTrue(validar_resultado(self.pedido, replace(real, alocacoes=(Alocacao('inexistente', 'ninguem'),))))
        todas_daniel = tuple(Alocacao(v.id, 'daniel') for v in self.pedido.vagas)
        erros = validar_resultado(self.pedido, ResultadoGeracao(StatusGeracao.VIAVEL, todas_daniel))
        self.assertIn('Pessoa de grupo não permitido no culto.', erros)
        self.assertIn('Limite semanal de participações excedido.', erros)
        self.assertIn('Pessoa ocupa mais de uma função na mesma data.', erros)
        restrito = replace(self.pedido, historico=self.historico(), regras=replace(self.pedido.regras, permitir_flexibilizar_consecutivas=False))
        self.assertIn('Repetição proibida pela configuração.', validar_resultado(restrito, real))

    def test_json_anterior_malformado(self):
        for dados in (None, [], {}, {'status': 'viavel', 'inicio_semana': '2026-11-16', 'alocacoes': None}, {'status': 'viavel', 'inicio_semana': '2026-11-16', 'alocacoes': [None]}):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                ler_escala_anterior(dados)

    def test_doze_semanas_encadeadas_com_validador_independente(self):
        anterior = None
        for semana in range(12):
            inicio = self.pedido.inicio_semana + timedelta(days=7 * semana)
            pedido = replace(self.pedido, inicio_semana=inicio, vagas=criar_vagas_semanais(inicio, self.pedido.cultos), escala_anterior=anterior, semente=semana)
            resultado = gerar_escala(pedido)
            self.assertEqual(resultado.status, StatusGeracao.VIAVEL)
            self.assertFalse(validar_resultado(pedido, resultado))
            if anterior:
                self.assertEqual(len({a.pessoa_id for a in anterior.alocacoes} & {a.pessoa_id for a in resultado.alocacoes}), 6)
            anterior = EscalaAnterior(inicio, pedido.vagas, resultado.alocacoes)
