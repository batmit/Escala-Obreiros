import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from dataclasses import replace
from datetime import date
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from .database import BancoIgreja
from .generation.contracts import PedidoGeracao, ResultadoGeracao, StatusGeracao
from .generation.cp_sat import gerar_escala
from .generation.slots import criar_vagas_semanais
from .schedule_repository import RepositorioEscalas
from .server import CalendarHandler


class EscalasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'igreja.sqlite3'
        with BancoIgreja(self.path) as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()
            cultos = tuple(banco.listar_cultos())
            self.pedido = PedidoGeracao(date(2026, 11, 23), tuple(banco.listar_pessoas()), cultos,
                criar_vagas_semanais(date(2026, 11, 23), cultos), banco.obter_regras())
        self.repo = RepositorioEscalas(self.path)
        self.resultado = gerar_escala(self.pedido)

    def test_salva_reabre_sem_duplicar_nem_alterar_historico(self):
        identificador = self.repo.salvar_e_publicar(self.pedido, self.resultado)
        self.assertEqual(identificador, self.repo.salvar_e_publicar(self.pedido, self.resultado))
        anterior = RepositorioEscalas(self.path).obter_anterior(self.pedido.inicio_semana)
        self.assertEqual(set(anterior.alocacoes), set(self.resultado.alocacoes))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM escalas').fetchone()[0], 1)
            self.assertEqual(connection.execute('SELECT count(*) FROM participacoes').fetchone()[0], 0)
        consulta = self.repo.consultar_periodo(date(2026, 11, 23), date(2026, 11, 29))
        self.assertEqual(sum(len(c['atribuicoes']) for c in consulta['cultos']), 8)
        self.assertTrue(consulta['atualizada_em'])

    def test_nova_versao_e_falha_transacional_preservam_publicada(self):
        self.repo.salvar_e_publicar(self.pedido, self.resultado)
        novo = replace(self.pedido, semente=42)
        resultado = gerar_escala(novo)
        segunda = self.repo.salvar_e_publicar(novo, resultado)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT versao FROM escalas WHERE publicada=1').fetchone()[0], 2)
            connection.execute("CREATE TRIGGER falhar_alocacao BEFORE INSERT ON alocacoes_escala BEGIN SELECT RAISE(ABORT, 'falha simulada'); END")
            connection.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.salvar_e_publicar(replace(novo, semente=43), gerar_escala(replace(novo, semente=43)))
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM escalas').fetchone()[0], 2)
            self.assertEqual(connection.execute('SELECT id FROM escalas WHERE publicada=1').fetchone()[0], segunda)

    def test_rejeita_resultado_inviavel_ou_incompleto(self):
        for resultado in (ResultadoGeracao(StatusGeracao.INVIAVEL), replace(self.resultado, alocacoes=self.resultado.alocacoes[:-1])):
            with self.assertRaises(ValueError):
                self.repo.salvar_e_publicar(self.pedido, resultado)

    def test_publicacao_automatica_nao_substitui_semana_ja_publicada(self):
        primeira = self.repo.salvar_e_publicar(self.pedido, self.resultado)
        novo = replace(self.pedido, semente=89)
        self.assertEqual(self.repo.salvar_e_publicar(novo, gerar_escala(novo), somente_se_ausente=True), primeira)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM escalas').fetchone()[0], 1)

    def test_consulta_atravessa_semanas_sem_misturar_versoes(self):
        self.repo.salvar_e_publicar(self.pedido, self.resultado)
        novo = replace(self.pedido, inicio_semana=date(2026, 11, 30), vagas=criar_vagas_semanais(date(2026, 11, 30), self.pedido.cultos))
        self.repo.salvar_e_publicar(novo, gerar_escala(novo))
        consulta = self.repo.consultar_periodo(date(2026, 11, 28), date(2026, 12, 1))
        self.assertEqual([c['data'] for c in consulta['cultos']], ['2026-11-28', '2026-11-29', '2026-11-30', '2026-12-01'])
        self.assertEqual(self.repo.consultar_periodo(date(2027, 1, 1), date(2027, 1, 7))['cultos'], [])
        with self.assertRaises(ValueError):
            self.repo.consultar_periodo(date(2026, 12, 1), date(2026, 11, 30))

    def test_http_consulta_banco_e_serve_frontend(self):
        self.repo.salvar_e_publicar(self.pedido, self.resultado)
        server = ThreadingHTTPServer(('127.0.0.1', 0), partial(CalendarHandler, banco=self.path))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            with urlopen(base + '/healthz', timeout=5) as response:
                self.assertEqual(json.load(response)['status'], 'ok')
            with urlopen(base + '/api/escalas?inicio=2026-11-23&fim=2026-11-29', timeout=5) as response:
                dados = json.load(response)
            self.assertEqual(sum(len(c['atribuicoes']) for c in dados['cultos']), 8)
            with urlopen(base + '/cultos.json', timeout=5) as response:
                domingo = next(c for c in json.load(response) if c['diaSemana'] == 7)
                self.assertEqual(domingo['titulo'], 'Culto · noite')
            with urlopen(base + '/', timeout=5) as response:
                self.assertIn(b'api.js', response.read())
            with self.assertRaises(HTTPError) as erro:
                urlopen(base + '/api/escalas?inicio=invalido&fim=2026-11-29', timeout=5)
            self.assertEqual(erro.exception.code, 400)
            erro.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
