import io
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from waitress import create_server

from .production import executar, preparar_banco
from .webapp import criar_aplicacao


class ProducaoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.banco = Path(self.temp.name) / 'dados/igreja.sqlite3'
        preparar_banco(self.banco)

    def requisitar(self, path, method='GET', query=''):
        response = {}
        def start(status, headers):
            response.update(status=int(status.split()[0]), headers=dict(headers))
        body = criar_aplicacao(self.banco)({'REQUEST_METHOD': method, 'PATH_INFO': path,
            'QUERY_STRING': query, 'wsgi.input': io.BytesIO()}, start)
        return response, b''.join(body)

    def test_wsgi_api_head_e_bloqueio_de_arquivos_internos(self):
        response, body = self.requisitar('/healthz')
        self.assertEqual(response['status'], 200)
        self.assertEqual(json.loads(body)['status'], 'ok')
        self.assertEqual(self.requisitar('/api/escalas', query='inicio=&fim=2026-11-30')[0]['status'], 400)
        for path in ('/../backend/schema.sql', '/calendar.test.cjs', '/data/igreja.sqlite3', '/.env'):
            self.assertEqual(self.requisitar(path)[0]['status'], 404)
        self.assertEqual(self.requisitar('/', 'POST')[0]['status'], 405)
        response, body = self.requisitar('/', 'HEAD')
        self.assertEqual(response['status'], 200)
        self.assertEqual(body, b'')
        self.assertGreater(int(response['headers']['Content-Length']), 0)

    def test_inicializacao_preserva_dados_existentes(self):
        with closing(sqlite3.connect(self.banco)) as connection:
            connection.execute("UPDATE pessoas SET nome='Nome preservado' WHERE id='daniel'")
            connection.commit()
        preparar_banco(self.banco)
        with closing(sqlite3.connect(self.banco)) as connection:
            self.assertEqual(connection.execute("SELECT nome FROM pessoas WHERE id='daniel'").fetchone()[0], 'Nome preservado')

    def test_waitress_workers_reinicio_e_encerramento_reais(self):
        for reinicio in range(2):
            parada, criado = threading.Event(), threading.Event()
            estado = {}
            def criar(*args, **kwargs):
                servidor = create_server(*args, **kwargs)
                estado['porta'] = servidor.effective_port
                criado.set()
                return servidor
            def rodar():
                try:
                    executar(self.banco, '127.0.0.1', 0, self.banco.parent / 'backups', parar=parada)
                except Exception as erro:
                    estado['erro'] = erro
            with patch('backend.production.create_server', side_effect=criar):
                thread = threading.Thread(target=rodar, daemon=True)
                thread.start()
                try:
                    self.assertTrue(criado.wait(5))
                    prazo = time.monotonic() + 15
                    # Espera a geração sem nenhuma requisição HTTP.
                    while True:
                        with closing(sqlite3.connect(self.banco)) as connection:
                            total = connection.execute('SELECT count(*) FROM escalas').fetchone()[0]
                        if total or time.monotonic() > prazo:
                            break
                        time.sleep(0.05)
                    self.assertEqual(total, 1)
                    with urlopen(f"http://127.0.0.1:{estado['porta']}/healthz", timeout=5) as response:
                        self.assertEqual(json.load(response)['workers'], {'agendador': 'ativo', 'backups': 'ativo'})
                finally:
                    parada.set()
                    thread.join(timeout=55)
                self.assertFalse(thread.is_alive(), f'Processo não encerrou no ciclo {reinicio}')
                self.assertNotIn('erro', estado)
