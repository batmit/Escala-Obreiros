import unittest
from dataclasses import replace
from datetime import date

from ..database import BancoIgreja
from ..models import Culto, Funcao, Participacao, Pessoa
from .contracts import EscalaAnterior, PedidoGeracao, StatusGeracao
from .previous_schedule import ler_escala_anterior
from .cp_sat import gerar_escala
from .slots import criar_vagas_semanais


class GeracaoTests(unittest.TestCase):
    def setUp(self):
        with BancoIgreja(':memory:') as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()
            cultos = tuple(banco.listar_cultos())
            self.pedido = PedidoGeracao(
                date(2026, 11, 23), tuple(banco.listar_pessoas()), cultos,
                criar_vagas_semanais(date(2026, 11, 23), cultos), banco.obter_regras(),
            )

    def test_expansao_oito_vagas_inclui_domingo_duas_funcoes(self):
        vagas = self.pedido.vagas
        self.assertEqual(len(vagas), 8)
        self.assertEqual(len({v.id for v in vagas}), 8)
        self.assertEqual({v.data.isoweekday() for v in vagas}, {1, 2, 4, 6, 7})
        self.assertEqual({v.funcao for v in vagas if v.data == date(2026, 11, 29)}, {Funcao.PALAVRA, Funcao.LOUVOR})
        virada = criar_vagas_semanais(date(2026, 12, 28), reversed(self.pedido.cultos))
        self.assertEqual(virada[-1].data, date(2027, 1, 3))
        with self.assertRaises(ValueError):
            criar_vagas_semanais(date(2026, 11, 24), self.pedido.cultos)

    def test_contrato_rejeita_cobertura_incompleta(self):
        with self.assertRaises(ValueError):
            replace(self.pedido, vagas=self.pedido.vagas[:-1])
        with self.assertRaises(ValueError):
            replace(self.pedido, semente=2**31)

    def test_escala_cobre_vagas_sem_repeticao_e_domingo_grupo_dois(self):
        pessoas = {p.id: p for p in self.pedido.pessoas}
        vagas = {v.id: v for v in self.pedido.vagas}
        for semente in (0, 42, 123):
            with self.subTest(semente=semente):
                resultado = gerar_escala(replace(self.pedido, semente=semente))
                self.assertEqual(resultado.status, StatusGeracao.VIAVEL)
                self.assertEqual({a.vaga_id for a in resultado.alocacoes}, set(vagas))
                self.assertEqual(len(resultado.alocacoes), 8)
                self.assertEqual(len({a.pessoa_id for a in resultado.alocacoes}), 8)
                for alocacao in resultado.alocacoes:
                    self.assertIn(alocacao.pessoa_id, pessoas)
                    if vagas[alocacao.vaga_id].data.isoweekday() == 7:
                        self.assertEqual(pessoas[alocacao.pessoa_id].grupo, 2)

    def test_poucas_pessoas_retorna_inviavel_sem_alocacoes(self):
        for pessoas in ((), self.pedido.pessoas[:7]):
            resultado = gerar_escala(replace(self.pedido, pessoas=pessoas))
            self.assertEqual(resultado.status, StatusGeracao.INVIAVEL)
            self.assertFalse(resultado.alocacoes)

    def test_sem_pessoas_suficientes_no_grupo_dois_para_domingo(self):
        # Mesmo com limite semanal maior, uma pessoa não pode fazer ambas as funções.
        pessoas = tuple(p for p in self.pedido.pessoas if p.grupo == 1) + (next(p for p in self.pedido.pessoas if p.grupo == 2),)
        pedido = replace(self.pedido, pessoas=pessoas, regras=replace(self.pedido.regras, maximo_participacoes_semana=2))
        self.assertEqual(gerar_escala(pedido).status, StatusGeracao.INVIAVEL)

    def test_historico_nao_proibe_repeticao_entre_semanas(self):
        historico = tuple(Participacao(date(2026, 11, 16 + indice // 2), p.id, Funcao.PALAVRA if indice % 2 else Funcao.LOUVOR) for indice, p in enumerate(self.pedido.pessoas))
        resultado = gerar_escala(replace(self.pedido, historico=historico))
        self.assertEqual(resultado.status, StatusGeracao.VIAVEL)
        self.assertTrue(resultado.avisos)

    def test_limite_muito_curto_nao_significa_inviabilidade(self):
        resultado = gerar_escala(replace(self.pedido, limite_segundos=1e-9))
        self.assertIn(resultado.status, (StatusGeracao.SEM_SOLUCAO, StatusGeracao.VIAVEL))

    def test_escala_anterior_minimiza_repeticao_sem_proibir(self):
        vagas_anteriores = criar_vagas_semanais(date(2026, 11, 16), self.pedido.cultos)
        pedido_anterior = replace(self.pedido, inicio_semana=date(2026, 11, 16), vagas=vagas_anteriores)
        primeira = gerar_escala(pedido_anterior)
        anterior = EscalaAnterior(pedido_anterior.inicio_semana, vagas_anteriores, primeira.alocacoes)
        segunda = gerar_escala(replace(self.pedido, escala_anterior=anterior))
        self.assertEqual(segunda.status, StatusGeracao.VIAVEL)
        usados = {a.pessoa_id for a in primeira.alocacoes}
        self.assertEqual(len(usados & {a.pessoa_id for a in segunda.alocacoes}), 6)
        self.assertTrue(any('6 pessoa' in aviso for aviso in segunda.avisos))
        self.assertEqual(segunda, gerar_escala(replace(self.pedido, escala_anterior=anterior)))

    def test_arquivo_anterior_e_semana_incorreta(self):
        dados = {'inicio_semana': '2026-11-09', 'status': 'viavel', 'alocacoes': []}
        anterior = ler_escala_anterior(dados)
        with self.assertRaises(ValueError):
            replace(self.pedido, escala_anterior=anterior)
        with self.assertRaises(ValueError):
            ler_escala_anterior({'status': 'inviavel'})

    def test_solver_aplica_peso_individual_em_ambas_as_funcoes(self):
        for funcao in (Funcao.PALAVRA, Funcao.LOUVOR):
            culto = Culto(2, (funcao.value,), ((2, 1),))
            pedido = replace(self.pedido,
                pessoas=(Pessoa('leve', 'Leve', 2, 'obreiro', 1), Pessoa('pesado', 'Pesado', 2, 'pastor', 3)),
                cultos=(culto,), vagas=criar_vagas_semanais(self.pedido.inicio_semana, (culto,)))
            pesados = sum(gerar_escala(replace(pedido, semente=seed)).alocacoes[0].pessoa_id == 'pesado' for seed in range(160))
            self.assertTrue(95 < pesados < 145, (funcao, pesados))
