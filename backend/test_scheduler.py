import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from .database import BancoIgreja
from .generation.contracts import ResultadoGeracao, StatusGeracao
from .generation.cp_sat import gerar_escala
from .schedule_repository import RepositorioEscalas
from .scheduler import AgendadorSemanal, garantir_semana_vigente, limites_semana


class AgendamentoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'igreja.sqlite3'
        with BancoIgreja(self.path) as banco:
            banco.inicializar()
            banco.carregar_dados_iniciais()
        self.repo = RepositorioEscalas(self.path)

    def test_virada_de_segunda_em_brasilia(self):
        antes = datetime(2026, 11, 30, 2, 59, 59, tzinfo=timezone.utc)
        depois = datetime(2026, 11, 30, 3, 0, tzinfo=timezone.utc)
        self.assertEqual(limites_semana(antes)[0], date(2026, 11, 23))
        self.assertEqual(limites_semana(depois)[0], date(2026, 11, 30))
        agendador = AgendadorSemanal(self.path, relogio=lambda: antes, executar=lambda *_: None)
        self.assertEqual(agendador.verificar(), 1)
        with self.assertRaises(ValueError):
            limites_semana(datetime(2026, 11, 30))

    def test_gera_na_virada_passando_escala_vigente_e_nao_duplicando(self):
        antes = datetime(2026, 11, 29, 23, 0, tzinfo=timezone.utc)
        self.assertTrue(garantir_semana_vigente(self.path, antes))
        anterior = self.repo.obter_anterior(date(2026, 11, 23))
        with patch('backend.scheduler.gerar_escala', wraps=gerar_escala) as gerar:
            self.assertTrue(garantir_semana_vigente(self.path, datetime(2026, 11, 30, 3, 0, tzinfo=timezone.utc)))
            self.assertEqual(gerar.call_args.args[0].escala_anterior, anterior)
            self.assertFalse(garantir_semana_vigente(self.path, datetime(2026, 12, 1, tzinfo=timezone.utc)))
            self.assertEqual(gerar.call_count, 1)
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM escalas').fetchone()[0], 2)
            self.assertEqual(connection.execute('SELECT count(*) FROM participacoes').fetchone()[0], 0)

    def test_reinicio_no_meio_da_semana_gera_semana_atual(self):
        agora = datetime(2027, 1, 1, 15, tzinfo=timezone.utc)
        self.assertTrue(garantir_semana_vigente(self.path, agora))
        self.assertIsNotNone(self.repo.obter_anterior(date(2026, 12, 28)))

    def test_trava_exclui_concorrentes_e_expira(self):
        semana = date(2026, 11, 23)
        self.assertTrue(self.repo.adquirir_geracao(semana, 'a', agora=100))
        self.assertFalse(self.repo.adquirir_geracao(semana, 'b', agora=101))
        self.repo.liberar_geracao(semana, 'b')
        self.assertFalse(self.repo.adquirir_geracao(semana, 'b', agora=102))
        self.assertTrue(self.repo.adquirir_geracao(semana, 'b', agora=220))

    def test_falha_preserva_publicada_e_libera_trava_para_repetir(self):
        garantir_semana_vigente(self.path, datetime(2026, 11, 24, tzinfo=timezone.utc))
        with patch('backend.scheduler.gerar_escala', return_value=ResultadoGeracao(StatusGeracao.INVIAVEL)):
            with self.assertRaises(ValueError):
                garantir_semana_vigente(self.path, datetime(2026, 12, 1, tzinfo=timezone.utc))
        self.assertIsNotNone(self.repo.obter_anterior(date(2026, 11, 23)))
        self.assertIsNone(self.repo.obter_anterior(date(2026, 11, 30)))
        self.assertTrue(garantir_semana_vigente(self.path, datetime(2026, 12, 1, tzinfo=timezone.utc)))

    def test_loop_nao_morre_com_falha(self):
        agora = datetime(2026, 12, 1, 15, tzinfo=timezone.utc)
        def falhar(*_):
            raise ValueError('Falha simulada')
        agendador = AgendadorSemanal(self.path, relogio=lambda: agora, executar=falhar)
        with self.assertLogs('backend.scheduler', level='ERROR'):
            self.assertEqual(agendador.verificar(), 60)
