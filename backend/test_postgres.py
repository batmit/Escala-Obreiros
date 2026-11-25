"""Integração real, isolada em schemas aleatórios de um PostgreSQL local de teste."""

import gzip
import io
import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4
from unittest.mock import patch

import psycopg
from psycopg import sql

from .database import BancoIgreja
from .generation.contracts import PedidoGeracao
from .generation.cp_sat import gerar_escala
from .generation.slots import criar_vagas_semanais
from .models import Funcao, Participacao
from .on_access import RenovacaoPorAcesso
from .postgres import BancoPostgres, RepositorioPostgres, conectar, migrar_schema
from .transfer import exportar, restaurar_postgres
from .webapp import criar_aplicacao

BASE = os.environ.get('TEST_DATABASE_URL')


@unittest.skipUnless(BASE, 'Defina TEST_DATABASE_URL para executar integração PostgreSQL real.')
class PostgresTests(unittest.TestCase):
    def setUp(self):
        if urlsplit(BASE).hostname not in ('localhost', '127.0.0.1', '::1', 'postgres'):
            self.fail('TEST_DATABASE_URL deve apontar para PostgreSQL local isolado, nunca Neon.')
        self.schemas = []
        self.roles = []
        self.addCleanup(self.limpar)
        self.url = self.novo_destino()

    def novo_destino(self):
        nome = 'teste_' + uuid4().hex
        with conectar(BASE) as connection:
            connection.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(nome)))
        self.schemas.append(nome)
        partes = urlsplit(BASE)
        query = dict(parse_qsl(partes.query))
        query['options'] = '-csearch_path=' + nome
        url = urlunsplit(partes._replace(query=urlencode(query)))
        migrar_schema(url)
        return url

    def limpar(self):
        with conectar(BASE) as connection:
            for nome in self.schemas:
                connection.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(nome)))
            for nome in self.roles:
                connection.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(nome)))

    def pedido(self):
        with BancoPostgres(self.url) as banco:
            banco.carregar_dados_iniciais()
            cultos = tuple(banco.listar_cultos())
            return PedidoGeracao(date(2026, 11, 23), tuple(banco.listar_pessoas()), cultos,
                criar_vagas_semanais(date(2026, 11, 23), cultos), banco.obter_regras())

    def test_schema_seed_historico_e_restricoes(self):
        self.pedido()
        migrar_schema(self.url)
        with BancoPostgres(self.url) as banco:
            banco.carregar_dados_iniciais()
            self.assertEqual(len(banco.listar_pessoas()), 10)
            self.assertEqual(next(c.periodo for c in banco.listar_cultos() if c.dia_semana == 7), 'noite')
            p = Participacao(date(2026, 11, 17), 'hugo', Funcao.LOUVOR)
            banco.registrar_participacao(p)
            banco.registrar_participacao(p)
            self.assertEqual(banco.listar_participacoes_ultimas_duas_semanas(date(2026, 11, 24)), [p])
            with self.assertRaises(psycopg.IntegrityError):
                banco.registrar_participacao(replace(p, funcao=Funcao.PALAVRA))
            with self.assertRaises(ValueError):
                banco.registrar_participacao(replace(p, pessoa_id='juninho'))
        with conectar(self.url) as connection:
            self.assertEqual(connection.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n'], 1)

    def test_publicacao_concorrente_idempotente_e_reabertura(self):
        pedido = self.pedido()
        resultado = gerar_escala(pedido)
        def salvar(_):
            return RepositorioPostgres(self.url).salvar_e_publicar(pedido, resultado, somente_se_ausente=True)
        with ThreadPoolExecutor(max_workers=4) as executor:
            ids = list(executor.map(salvar, range(8)))
        self.assertEqual(len(set(ids)), 1)
        repo = RepositorioPostgres(self.url)
        self.assertEqual(len(repo.obter_anterior(pedido.inicio_semana).alocacoes), 8)
        self.assertEqual(sum(len(c['atribuicoes']) for c in repo.consultar_periodo(date(2026, 11, 23), date(2026, 11, 29))['cultos']), 8)
        with conectar(self.url) as connection:
            self.assertEqual(connection.execute('SELECT count(*) AS n FROM escalas').fetchone()['n'], 1)

    def test_falha_transacional_preserva_publicacao(self):
        pedido = self.pedido()
        repo = RepositorioPostgres(self.url)
        resultado = gerar_escala(pedido)
        original = repo.salvar_e_publicar(pedido, resultado)
        with conectar(self.url) as connection:
            connection.execute("CREATE FUNCTION falha() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'falha simulada'; END; $$")
            connection.execute('CREATE TRIGGER falhar BEFORE INSERT ON alocacoes_escala FOR EACH ROW EXECUTE FUNCTION falha()')
        with self.assertRaises(psycopg.Error):
            repo.salvar_e_publicar(replace(pedido, semente=42), resultado)
        with conectar(self.url) as connection:
            self.assertEqual(connection.execute('SELECT id FROM escalas WHERE publicada').fetchone()['id'], original)
            self.assertEqual(connection.execute('SELECT count(*) AS n FROM escalas').fetchone()['n'], 1)

    def test_trava_concorrente_com_expiracao(self):
        repo = RepositorioPostgres(self.url)
        with ThreadPoolExecutor(max_workers=4) as executor:
            respostas = list(executor.map(lambda i: repo.adquirir_geracao(date(2026, 11, 23), str(i), agora=100), range(8)))
        self.assertEqual(sum(respostas), 1)
        self.assertTrue(repo.adquirir_geracao(date(2026, 11, 23), 'novo', agora=220))
        repo.liberar_geracao(date(2026, 11, 23), 'invasor')
        self.assertFalse(repo.adquirir_geracao(date(2026, 11, 23), 'outro', agora=221))

    def test_migracao_sqlite_preserva_dados_e_nao_sobrescreve(self):
        with tempfile.TemporaryDirectory() as pasta:
            origem, arquivo = Path(pasta)/'origem.sqlite3', Path(pasta)/'snapshot.json.gz'
            with BancoIgreja(origem) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
                cultos = tuple(banco.listar_cultos())
                pedido = PedidoGeracao(date(2026, 11, 23), tuple(banco.listar_pessoas()), cultos,
                    criar_vagas_semanais(date(2026, 11, 23), cultos), banco.obter_regras())
            from .schedule_repository import RepositorioEscalas
            id_original = RepositorioEscalas(origem).salvar_e_publicar(pedido, gerar_escala(pedido))
            contagens = exportar(origem, arquivo)
            self.assertEqual(restaurar_postgres(arquivo, self.url), contagens)
            with conectar(self.url) as connection:
                self.assertEqual(connection.execute('SELECT id FROM escalas').fetchone()['id'], id_original)
                self.assertEqual(connection.execute('SELECT count(*) AS n FROM geracoes_em_andamento').fetchone()['n'], 0)
            with self.assertRaises(ValueError):
                restaurar_postgres(arquivo, self.url)
            backup_pg = Path(pasta)/'pg.json.gz'
            self.assertEqual(exportar(self.url, backup_pg), contagens)
            self.assertEqual(restaurar_postgres(backup_pg, self.novo_destino()), contagens)

    def test_importacao_invalida_reverte_todas_as_tabelas(self):
        from .transfer import canonico
        import hashlib
        with tempfile.TemporaryDirectory() as pasta:
            origem, arquivo = Path(pasta)/'origem.sqlite3', Path(pasta)/'snapshot.json.gz'
            with BancoIgreja(origem) as banco:
                banco.inicializar()
                banco.carregar_dados_iniciais()
            exportar(origem, arquivo)
            with gzip.open(arquivo, 'rt', encoding='utf-8') as stream:
                payload = json.load(stream)
            payload['tabelas']['pessoas'][0]['grupo_id'] = 99
            payload['sha256'] = hashlib.sha256(canonico(payload['tabelas']).encode()).hexdigest()
            with gzip.open(arquivo, 'wt', encoding='utf-8') as stream:
                json.dump(payload, stream)
            with self.assertRaises(psycopg.IntegrityError):
                restaurar_postgres(arquivo, self.url)
            with conectar(self.url) as connection:
                self.assertEqual(connection.execute('SELECT count(*) AS n FROM grupos').fetchone()['n'], 0)

    def test_acesso_neon_nao_repete_nem_cria_backup_local(self):
        self.pedido()
        manter = RenovacaoPorAcesso(self.url, None, relogio=lambda: datetime(2026, 11, 24, 15, tzinfo=timezone.utc))
        manter()
        manter()
        with conectar(self.url) as connection:
            self.assertEqual(connection.execute('SELECT count(*) AS n FROM escalas').fetchone()['n'], 1)
        app = criar_aplicacao(self.url)
        response = {}
        def start(status, headers):
            response['status'] = status
        with patch('backend.webapp.banco_igreja', side_effect=AssertionError('healthcheck não deve acordar Neon')):
            body = b''.join(app({'PATH_INFO': '/healthz', 'REQUEST_METHOD': 'GET', 'wsgi.input': io.BytesIO()}, start))
        self.assertEqual(json.loads(body)['status'], 'ok')

    def test_papeis_runtime_e_backup_sem_permissoes_administrativas(self):
        self.pedido()
        runtime, backup = 'runtime_' + uuid4().hex, 'backup_' + uuid4().hex
        self.roles.extend((runtime, backup))
        with conectar(BASE) as connection:
            for role in (runtime, backup):
                connection.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(sql.Identifier(role), sql.Literal('somente_teste_local')))
        grants = (Path(__file__).parent.parent / 'deploy/postgres_roles.sql').read_text(encoding='utf-8')
        grants = grants.replace('escala_runtime', runtime).replace('escala_backup', backup).replace('SCHEMA public', f'SCHEMA {self.schemas[0]}')
        with conectar(self.url) as connection:
            connection.execute(grants, prepare=False)
        def credencial(role):
            partes = urlsplit(self.url)
            return urlunsplit(partes._replace(netloc=f'{role}:somente_teste_local@{partes.hostname}:{partes.port}'))
        manter = RenovacaoPorAcesso(credencial(runtime), None, relogio=lambda: datetime(2026, 11, 24, 15, tzinfo=timezone.utc))
        manter()
        with conectar(credencial(runtime)) as connection, self.assertRaises(psycopg.errors.InsufficientPrivilege):
            connection.execute('CREATE TABLE nao_permitido (id INTEGER)')
        with tempfile.TemporaryDirectory() as pasta:
            contagens = exportar(credencial(backup), Path(pasta) / 'backup.json.gz')
            self.assertEqual(contagens['alocacoes_escala'], 8)
        with conectar(credencial(backup)) as connection, self.assertRaises(psycopg.errors.InsufficientPrivilege):
            connection.execute('DELETE FROM escalas')
