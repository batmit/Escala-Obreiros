import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from .bootstrap import preparar_banco
from .hosted_wsgi import criar_wsgi
from .on_access import RenovacaoPorAcesso
from .scheduler import garantir_semana_vigente
from .webapp import criar_aplicacao


class AcessoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.banco = Path(self.temp.name) / 'igreja.sqlite3'
        preparar_banco(self.banco)
        self.agora = [datetime(2026, 11, 24, 15, tzinfo=timezone.utc)]

    def solicitar(self, app, path='/api/escalas', query='inicio=2026-11-24&fim=2026-11-30', method='GET'):
        response = {}
        def start(status, headers):
            response['status'] = int(status.split()[0])
        body = b''.join(app({'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': query, 'wsgi.input': io.BytesIO()}, start))
        return response['status'], json.loads(body) if body and path.startswith('/api/') else body

    def test_primeiro_acesso_gera_outros_consultam_e_virada_envia_anterior(self):
        with patch('backend.on_access.garantir_semana_vigente', wraps=garantir_semana_vigente) as gerar:
            manter = RenovacaoPorAcesso(self.banco, Path(self.temp.name) / 'backups', relogio=lambda: self.agora[0])
            app = criar_aplicacao(self.banco, ao_consultar=manter)
            for _ in range(3):
                status, dados = self.solicitar(app)
                self.assertEqual(status, 200)
                self.assertTrue(dados['cultos'])
            self.assertEqual(gerar.call_count, 1)
            self.agora[0] = datetime(2026, 11, 30, 3, tzinfo=timezone.utc)
            self.assertEqual(self.solicitar(app)[0], 200)
            self.assertEqual(gerar.call_count, 2)
        with closing(sqlite3.connect(self.banco)) as connection:
            rows = connection.execute('SELECT inicio_semana, parametros_json FROM escalas ORDER BY inicio_semana').fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(json.loads(rows[1][1])['escala_anterior']['inicio_semana'], '2026-11-23')
            self.assertEqual(connection.execute('SELECT count(*) FROM participacoes').fetchone()[0], 0)

    def test_reinicio_wsgi_preserva_escala_e_nao_gera_futuro_por_navegacao(self):
        manter = RenovacaoPorAcesso(self.banco, Path(self.temp.name) / 'backups', relogio=lambda: self.agora[0])
        app = criar_aplicacao(self.banco, ao_consultar=manter)
        self.solicitar(app)
        # Nova factory de manutenção não guarda o controle semanal em memória.
        outro = RenovacaoPorAcesso(self.banco, Path(self.temp.name) / 'backups', relogio=lambda: self.agora[0], gerar=lambda *_: self.fail('Não deveria gerar novamente'))
        app = criar_aplicacao(self.banco, ao_consultar=outro)
        status, dados = self.solicitar(app, query='inicio=2027-01-04&fim=2027-01-10')
        self.assertEqual(status, 200)
        self.assertEqual(dados['cultos'], [])

    def test_health_head_static_e_consulta_invalida_nao_geram(self):
        def proibido():
            self.fail('Não deveria disparar geração')
        app = criar_aplicacao(self.banco, ao_consultar=proibido)
        self.assertEqual(self.solicitar(app, '/healthz')[0], 200)
        self.assertEqual(self.solicitar(app, '/')[0], 200)
        self.assertEqual(self.solicitar(app, method='HEAD')[0], 200)
        self.assertEqual(self.solicitar(app, query='inicio=errado&fim=2026-11-30')[0], 400)

    def test_falha_retorna_503_sem_publicar(self):
        def falhar(*_):
            raise ValueError('Falha simulada')
        manter = RenovacaoPorAcesso(self.banco, Path(self.temp.name) / 'backups', relogio=lambda: self.agora[0], gerar=falhar)
        with self.assertLogs('backend.webapp', level='ERROR'):
            self.assertEqual(self.solicitar(criar_aplicacao(self.banco, ao_consultar=manter))[0], 503)

    def test_falha_de_backup_nao_oculta_escala_publicada(self):
        def falhar(*args, **kwargs):
            raise OSError('Disco indisponível')
        manter = RenovacaoPorAcesso(self.banco, Path(self.temp.name) / 'backups', relogio=lambda: self.agora[0], copiar=falhar)
        with self.assertLogs('backend.on_access', level='ERROR'):
            self.assertEqual(self.solicitar(criar_aplicacao(self.banco, ao_consultar=manter))[0], 200)

    def test_factory_gratuita_nao_inicia_workers(self):
        novo = Path(self.temp.name) / 'novo/igreja.sqlite3'
        with patch('threading.Thread.start', side_effect=AssertionError('Thread não permitida')):
            app = criar_wsgi(novo)
            self.assertEqual(self.solicitar(app, '/healthz')[0], 200)
